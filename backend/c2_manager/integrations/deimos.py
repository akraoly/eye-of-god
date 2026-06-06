"""
DeimosC2 — gRPC mTLS + web UI REST (port 8443).

DeimosC2 (github.com/DeimosC2/DeimosC2) — C2 Go open-source, gRPC + web.
Port gRPC  : 50051 (mTLS, configurable)
Port web   : 8443  (HTTPS management panel, configurable)
Auth       : mTLS côté gRPC, JWT côté web API

Protocole gRPC (proto DeimosC2) :
  AgentService   — create, list, get, delete agents
  ListenerService — create, list, delete listeners
  TaskService    — task creation, list, get, stream
  FileService    — upload/download

Web API REST (si web UI activée) :
  POST /api/v1/users/login     → JWT token
  GET  /api/v1/agents          → liste agents
  GET  /api/v1/listeners       → liste listeners
  POST /api/v1/listeners       → créer listener
  POST /api/v1/agents/{id}/tasks → créer tâche
  GET  /api/v1/agents/{id}/tasks → historique tâches
  GET  /api/v1/files/download/{id} → télécharger fichier

Modes (config.extra["mode"]) :
  "grpc"  — connexion gRPC mTLS (défaut si ca_cert configuré)
  "rest"  — web API REST uniquement
"""
from __future__ import annotations

import logging
import uuid
from base64 import b64decode
from datetime import datetime
from typing import Any

import httpx

from c2_manager.interfaces import GrpcC2Interface, C2AuthError, C2ConnectionError
from c2_manager.models import C2Config, C2Status, Listener, Implant, Task, PayloadConfig

logger = logging.getLogger(__name__)


class DeimosC2(GrpcC2Interface):
    """
    DeimosC2 — gRPC mTLS + REST API management.

    Paramètres extra (config.extra) :
      mode         : "grpc" | "rest"   (défaut: "rest" sauf si ca_cert fourni)
      grpc_port    : int   — port gRPC  (défaut: 50051)
      web_port     : int   — port web   (défaut: 8443)
      ca_cert      : str   — PEM CA (chemin ou contenu base64)
      client_cert  : str   — PEM cert client
      client_key   : str   — PEM clé privée client
      verify_ssl   : bool  (défaut: False pour REST)
    """

    CAPABILITIES = [
        "list_agents", "send_task", "create_listener", "remove_listener",
        "generate_payload", "file_upload", "file_download",
        "screenshot", "shell", "powershell", "persistence",
        "lateral_movement", "pivot",
    ]

    def __init__(self) -> None:
        super().__init__()
        self._mode:       str = "rest"
        self._rest_client: httpx.AsyncClient | None = None
        self._jwt_token:  str = ""

    # ── Connexion ─────────────────────────────────────────────────────────────

    async def connect(self, config: C2Config) -> bool:
        self._config = config

        ca_cert     = config.extra.get("ca_cert", "")
        mode        = config.extra.get("mode", "grpc" if ca_cert else "rest")
        self._mode  = mode

        if mode == "grpc":
            return await self._connect_grpc(config)
        return await self._connect_rest(config)

    async def _connect_grpc(self, config: C2Config) -> bool:
        grpc_port   = int(config.extra.get("grpc_port", 50051))
        ca_cert_raw = config.extra.get("ca_cert", "")
        cl_cert_raw = config.extra.get("client_cert", "")
        cl_key_raw  = config.extra.get("client_key", "")

        def _pem(s: str) -> bytes:
            if s.startswith("-----"):
                return s.encode()
            import base64
            try:
                return base64.b64decode(s)
            except Exception:
                return s.encode()

        ca_cert    = _pem(ca_cert_raw) if ca_cert_raw else None
        cl_cert    = _pem(cl_cert_raw) if cl_cert_raw else None
        cl_key     = _pem(cl_key_raw)  if cl_key_raw  else None

        if not all([ca_cert, cl_cert, cl_key]):
            raise C2ConnectionError("DeimosC2 gRPC : ca_cert, client_cert, client_key requis")

        self._channel = self._build_grpc_channel(
            config.host, grpc_port, ca_cert, cl_cert, cl_key
        )

        # Créer les stubs depuis les protobuf générés
        try:
            from deimos_pb2_grpc import (  # type: ignore
                AgentServiceStub, ListenerServiceStub, TaskServiceStub
            )
            self._stub = {
                "agents":    AgentServiceStub(self._channel),
                "listeners": ListenerServiceStub(self._channel),
                "tasks":     TaskServiceStub(self._channel),
            }
        except ImportError:
            # Stubs proto non disponibles — utiliser REST en fallback
            logger.warning("DeimosC2 : proto stubs absents, fallback REST")
            await self._channel.close()
            self._channel = None
            self._mode    = "rest"
            return await self._connect_rest(config)

        self._status = C2Status.CONNECTED
        logger.info("DeimosC2 : connecté gRPC → %s:%d", config.host, grpc_port)
        return True

    async def _connect_rest(self, config: C2Config) -> bool:
        web_port = int(config.extra.get("web_port", 8443))
        scheme   = "https" if config.ssl else "http"
        base_url = f"{scheme}://{config.host}:{web_port}"

        self._rest_client = httpx.AsyncClient(
            base_url=base_url,
            verify=config.extra.get("verify_ssl", False),
            timeout=30.0,
        )

        # Authentification JWT
        try:
            resp = await self._rest_client.post(
                "/api/v1/users/login",
                json={
                    "username": config.username or "admin",
                    "password": config.password or "",
                },
            )
            if resp.status_code not in (200, 201):
                raise C2AuthError(f"DeimosC2 auth échouée [{resp.status_code}]: {resp.text[:200]}")
            data = resp.json()
            self._jwt_token = (
                data.get("token")
                or data.get("access_token")
                or (data.get("data") or {}).get("token", "")
            )
            if not self._jwt_token:
                raise C2AuthError(f"Token DeimosC2 absent : {data}")
            self._rest_client.headers.update({"Authorization": f"Bearer {self._jwt_token}"})
        except httpx.ConnectError as exc:
            raise C2ConnectionError(f"DeimosC2 web UI inaccessible : {exc}") from exc

        self._status = C2Status.CONNECTED
        logger.info("DeimosC2 : connecté REST → %s", base_url)
        return True

    async def disconnect(self) -> None:
        await self.stop_healthcheck()
        if self._rest_client:
            await self._rest_client.aclose()
            self._rest_client = None
        await super().disconnect()

    async def get_status(self) -> C2Status:
        if self._mode == "grpc":
            return await super().get_status()
        if not self._rest_client:
            return C2Status.DISCONNECTED
        try:
            resp = await self._rest_client.get("/api/v1/agents", timeout=5.0)
            return C2Status.CONNECTED if resp.status_code == 200 else C2Status.ERROR
        except Exception:
            return C2Status.ERROR

    # ── Helpers REST ──────────────────────────────────────────────────────────

    async def _rest_get(self, path: str, **kwargs: Any) -> Any:
        if not self._rest_client:
            raise C2ConnectionError("DeimosC2 REST client non initialisé")
        resp = await self._rest_client.get(path, **kwargs)
        resp.raise_for_status()
        return resp.json()

    async def _rest_post(self, path: str, **kwargs: Any) -> Any:
        if not self._rest_client:
            raise C2ConnectionError("DeimosC2 REST client non initialisé")
        resp = await self._rest_client.post(path, **kwargs)
        resp.raise_for_status()
        return resp.json()

    async def _rest_delete(self, path: str) -> None:
        if not self._rest_client:
            raise C2ConnectionError("DeimosC2 REST client non initialisé")
        resp = await self._rest_client.delete(path)
        resp.raise_for_status()

    # ── Listeners ─────────────────────────────────────────────────────────────

    _LISTENER_TYPES = ["http", "https", "tcp", "smb", "dnscrypt"]

    async def create_listener(self, config: dict[str, Any]) -> Listener:
        self._require_connected()
        protocol = config.get("protocol", "https").lower()
        host     = config.get("bind_host", "0.0.0.0")
        port     = int(config.get("bind_port", 443))
        name     = config.get("name", f"deimos-{protocol}-{port}")

        body = {
            "name":     name,
            "type":     protocol,
            "host":     host,
            "port":     port,
            "ssl":      protocol in ("https",),
            "domains":  config.get("domains", []),
            "headers":  config.get("headers", {}),
            "user_agent": config.get("user_agent", "Mozilla/5.0"),
            "sleep":    config.get("sleep", 5),
            "jitter":   config.get("jitter", 0),
        }

        if self._mode == "grpc" and self._stub:
            try:
                from deimos_pb2 import CreateListenerRequest  # type: ignore
                req  = CreateListenerRequest(**body)
                resp = await self._stub["listeners"].CreateListener(req)
                return Listener(
                    id=str(resp.id),
                    name=name, c2_type=self._config.c2_type,
                    bind_host=host, bind_port=port, protocol=protocol,
                    status="running" if resp.active else "stopped",
                )
            except Exception as exc:
                logger.warning("DeimosC2 gRPC CreateListener échouée : %s", exc)

        data = await self._rest_post("/api/v1/listeners", json=body)
        lid  = str(data.get("id") or data.get("listener_id") or uuid.uuid4())
        return Listener(
            id=lid, name=name, c2_type=self._config.c2_type,
            bind_host=host, bind_port=port, protocol=protocol,
            status="running" if data.get("active", True) else "stopped",
            meta={"domains": config.get("domains", [])},
        )

    async def remove_listener(self, listener_id: str) -> bool:
        self._require_connected()
        try:
            await self._rest_delete(f"/api/v1/listeners/{listener_id}")
            return True
        except Exception as exc:
            logger.error("DeimosC2 remove listener : %s", exc)
            return False

    async def list_listeners(self) -> list[Listener]:
        self._require_connected()
        data  = await self._rest_get("/api/v1/listeners")
        items = data if isinstance(data, list) else data.get("listeners", data.get("data", []))
        return [
            Listener(
                id=str(l.get("id") or uuid.uuid4()),
                name=l.get("name", ""),
                c2_type=self._config.c2_type,
                bind_host=l.get("host", "0.0.0.0"),
                bind_port=int(l.get("port", 443)),
                protocol=l.get("type") or l.get("protocol", "https"),
                status="running" if l.get("active", True) else "stopped",
            )
            for l in items
        ]

    # ── Agents ────────────────────────────────────────────────────────────────

    async def list_agents(self) -> list[Implant]:
        self._require_connected()
        data  = await self._rest_get("/api/v1/agents")
        items = data if isinstance(data, list) else data.get("agents", data.get("data", []))
        return [self._parse_agent(a) for a in items]

    def _parse_agent(self, a: dict[str, Any]) -> Implant:
        aid = str(a.get("id") or a.get("agent_id") or uuid.uuid4())

        def _dt(v: Any) -> datetime:
            if isinstance(v, (int, float)):
                try:
                    return datetime.utcfromtimestamp(v / 1000 if v > 1e10 else v)
                except Exception:
                    return datetime.utcnow()
            if isinstance(v, str):
                for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
                    try:
                        return datetime.strptime(v[:19].rstrip("Z"), fmt.rstrip("Z"))
                    except ValueError:
                        continue
            return datetime.utcnow()

        priv = a.get("privilege") or a.get("integrity") or ""
        if isinstance(priv, str):
            priv_upper = priv.upper()
            if "SYSTEM" in priv_upper:
                integrity = "SYSTEM"
            elif "ADMIN" in priv_upper or "ROOT" in priv_upper:
                integrity = "ADMIN"
            else:
                integrity = "USER"
        else:
            integrity = "ADMIN" if priv else "USER"

        return Implant(
            id=aid,
            name=a.get("hostname") or aid,
            c2_type=self._config.c2_type,
            listener_id=str(a.get("listener_id") or a.get("listener", "")),
            external_ip=a.get("external_ip") or a.get("ip", ""),
            internal_ip=a.get("internal_ip") or a.get("local_ip", ""),
            hostname=a.get("hostname", ""),
            username=a.get("username") or a.get("user", ""),
            os=a.get("os") or a.get("operating_system", ""),
            arch=a.get("arch") or a.get("architecture", ""),
            pid=int(a.get("pid", 0)),
            process_name=a.get("process") or a.get("process_name", ""),
            integrity=integrity,
            last_checkin=_dt(a.get("last_checkin") or a.get("last_seen")),
            first_seen=_dt(a.get("created_at") or a.get("first_seen")),
            active=not bool(a.get("dead") or a.get("disconnected", False)),
            meta={
                "sleep":  a.get("sleep", 5),
                "jitter": a.get("jitter", 0),
                "pivot":  a.get("pivot", False),
            },
        )

    # ── Tâches ────────────────────────────────────────────────────────────────

    _TASK_TYPES: dict[str, str] = {
        "shell":          "shell",
        "cmd":            "shell",
        "ps":             "powershell",
        "powershell":     "powershell",
        "screenshot":     "screenshot",
        "ls":             "ls",
        "cd":             "cd",
        "upload":         "upload",
        "download":       "download",
        "sysinfo":        "sysinfo",
        "persistence":    "persistence",
        "inject":         "inject",
        "pivot":          "pivot",
        "reverse_tcp":    "reverse_tcp",
        "reverse_http":   "reverse_http",
        "kill":           "kill",
        "sleep":          "sleep",
    }

    async def send_task(
        self,
        agent_id: str,
        command:  str,
        args:     list[str] | None = None,
    ) -> Task:
        self._require_connected()
        args_list = args or []
        cmd_parts = command.split()
        cmd_lower = cmd_parts[0].lower() if cmd_parts else "shell"
        task_type = self._TASK_TYPES.get(cmd_lower, "shell")
        extra     = cmd_parts[1:] + args_list

        body: dict[str, Any] = {
            "type":    task_type,
            "payload": " ".join(extra) if extra else command,
            "args":    extra,
            "timeout": 60,
        }
        if task_type == "sleep" and extra:
            body["sleep"] = int(extra[0]) if extra[0].isdigit() else 5
        elif task_type in ("download", "upload") and extra:
            body["path"] = extra[0]

        data = await self._rest_post(f"/api/v1/agents/{agent_id}/tasks", json=body)
        return Task(
            id=str(data.get("id") or data.get("task_id") or uuid.uuid4()),
            agent_id=agent_id,
            c2_type=str(self._config.c2_type),
            command=command,
            args=args_list,
            status=data.get("status", "queued"),
            meta={"task_type": task_type},
        )

    async def get_task_result(self, task_id: str) -> dict[str, Any]:
        self._require_connected()
        # Chercher dans tous les agents (l'ID suffit dans l'API DeimosC2)
        try:
            data = await self._rest_get(f"/api/v1/tasks/{task_id}")
        except Exception:
            data = {}
        return {
            "task_id": task_id,
            "status":  data.get("status", "unknown"),
            "output":  data.get("output") or data.get("result", ""),
        }

    # ── Payload (implant builder) ─────────────────────────────────────────────

    async def generate_payload(self, config: PayloadConfig) -> bytes:
        self._require_connected()
        listener_id = config.extra.get("listener_id", "")
        body = {
            "listener_id": listener_id,
            "format":      config.format or "exe",
            "arch":        config.arch or "x64",
            "os":          config.os or "windows",
            "sleep":       config.extra.get("sleep", 5),
            "jitter":      config.extra.get("jitter", 0),
            "obfuscate":   config.obfuscation,
            "name":        config.name,
        }
        data = await self._rest_post("/api/v1/payloads/generate", json=body)
        file_id = data.get("file_id") or data.get("id", "")
        if file_id:
            try:
                resp = await self._rest_client.get(
                    f"/api/v1/files/download/{file_id}"
                )
                return resp.content
            except Exception:
                pass
        b64 = data.get("data") or data.get("binary", "")
        return b64decode(b64) if b64 else b""

    async def get_capabilities(self) -> list[str]:
        return self.CAPABILITIES
