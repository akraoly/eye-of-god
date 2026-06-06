"""
Faction C2 — REST API + WebSocket SignalR (ASP.NET Core).

Faction C2 (github.com/FactionC2/Faction) — framework C2 open-source .NET.
Port      : 5000 (HTTP) / 8443 (HTTPS) par défaut
Auth      : POST /api/session → Bearer token
WebSocket : /hub (SignalR)

Endpoints REST :
  POST /api/session                   → login → {token}
  GET  /api/agent                     → liste des agents
  GET  /api/agent/{id}                → détail agent
  GET  /api/listener                  → liste des listeners
  POST /api/listener                  → créer un listener
  DELETE /api/listener/{id}           → supprimer un listener
  POST /api/task                      → créer une task
  GET  /api/task/{id}                 → résultat d'une task
  GET  /api/agent/{id}/tasks          → historique tasks agent
  POST /api/payload                   → générer un payload
  GET  /api/transport                 → liste des transports
  POST /api/transport                 → créer un transport
  GET  /api/module                    → modules disponibles
  POST /api/agent/{id}/module/run     → exécuter un module
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import Any

import httpx

from c2_manager.interfaces import RestC2Interface, C2AuthError
from c2_manager.models import C2Config, C2Status, Listener, Implant, Task, PayloadConfig

logger = logging.getLogger(__name__)


class FactionC2(RestC2Interface):
    """
    Faction C2 — REST API + SignalR WebSocket.

    Paramètres extra (config.extra) :
      verify_ssl : bool  (défaut: False)
      hub_path   : str   (défaut: "/hub")
      disable_ws : bool  (désactiver WebSocket pour les tests)
    """

    CAPABILITIES = [
        "list_agents", "send_task", "create_listener", "remove_listener",
        "generate_payload", "list_modules", "run_module", "list_transports",
    ]

    # ── Auth ──────────────────────────────────────────────────────────────────

    async def _authenticate(self, config: C2Config) -> str:
        async with httpx.AsyncClient(
            base_url=config.base_url,
            verify=config.extra.get("verify_ssl", False),
            timeout=15.0,
        ) as client:
            resp = await client.post(
                "/api/session",
                json={"username": config.username or "admin", "password": config.password or ""},
            )
            if resp.status_code not in (200, 201):
                raise C2AuthError(f"Faction auth échouée [{resp.status_code}]: {resp.text[:200]}")
            data  = resp.json()
            token = (
                data.get("token")
                or data.get("access_token")
                or (data.get("datas") or {}).get("token")
            )
            if not token:
                raise C2AuthError(f"Token Faction absent : {data}")
            logger.info("Faction : authentifié")
            return token

    async def connect(self, config: C2Config) -> bool:
        result = await super().connect(config)
        if result and not config.extra.get("disable_ws", False):
            asyncio.create_task(self._connect_signalr(config))
        return result

    async def _connect_signalr(self, config: C2Config) -> None:
        hub_path = config.extra.get("hub_path", "/hub")
        scheme   = "wss" if config.ssl else "ws"
        url      = f"{scheme}://{config.host}:{config.port}{hub_path}"
        try:
            import websockets.client as wsc  # type: ignore
            import ssl as _ssl
            ssl_ctx = None
            if config.ssl:
                ssl_ctx = _ssl.create_default_context()
                ssl_ctx.check_hostname = False
                ssl_ctx.verify_mode    = _ssl.CERT_NONE
            async with wsc.connect(url, ssl=ssl_ctx, extra_headers={"Authorization": f"Bearer {self._token}"}, ping_interval=30) as ws:
                logger.info("Faction : SignalR WebSocket connecté → %s", url)
                async for raw in ws:
                    try:
                        event = json.loads(raw)
                        logger.debug("Faction event : %s", event.get("type"))
                    except json.JSONDecodeError:
                        pass
        except (asyncio.CancelledError, ImportError):
            return
        except Exception as exc:
            logger.warning("Faction SignalR déconnecté : %s", exc)

    async def get_status(self) -> C2Status:
        if not self._client:
            return C2Status.DISCONNECTED
        try:
            resp = await self._client.get("/api/agent", timeout=5.0)
            return C2Status.CONNECTED if resp.status_code == 200 else C2Status.ERROR
        except Exception:
            return C2Status.ERROR

    # ── Listeners ─────────────────────────────────────────────────────────────

    async def create_listener(self, config: dict[str, Any]) -> Listener:
        self._require_connected()
        protocol = config.get("protocol", "https").lower()
        host     = config.get("bind_host", "0.0.0.0")
        port     = int(config.get("bind_port", 443))
        name     = config.get("name", f"faction-{protocol}-{port}")

        transport_type_map = {"http": "HTTP", "https": "HTTPS", "dns": "DNS", "smb": "SMB"}
        transport_data = await self._post("/api/transport", json={
            "name":           f"transport-{name}",
            "transport_type": transport_type_map.get(protocol, "HTTPS"),
            "host":           config.get("callback_host", host),
            "port":           port,
            "use_ssl":        protocol == "https",
        })
        transport_id = str((transport_data.get("datas") or transport_data).get("id", uuid.uuid4()))

        data  = await self._post("/api/listener", json={
            "name": name, "transport_id": transport_id,
            "bind_address": host, "bind_port": port,
            "config": {"sleep_time": config.get("sleep", 60), "jitter": config.get("jitter", 10),
                       "user_agent": config.get("user_agent", "Mozilla/5.0")},
        })
        datas = data.get("datas") or data
        lid   = str(datas.get("id") or uuid.uuid4())
        return Listener(
            id=lid, name=name, c2_type=self._config.c2_type,
            bind_host=host, bind_port=port, protocol=protocol,
            status="running" if datas.get("enabled", True) else "stopped",
            meta={"transport_id": transport_id},
        )

    async def remove_listener(self, listener_id: str) -> bool:
        self._require_connected()
        try:
            await self._delete(f"/api/listener/{listener_id}")
            return True
        except Exception as exc:
            logger.error("Faction remove_listener : %s", exc)
            return False

    async def list_listeners(self) -> list[Listener]:
        self._require_connected()
        data  = await self._get("/api/listener")
        items = (data.get("datas") or data) if isinstance(data, dict) else data
        if not isinstance(items, list):
            items = []
        return [
            Listener(
                id=str(l.get("id") or uuid.uuid4()),
                name=l.get("name", ""),
                c2_type=self._config.c2_type,
                bind_host=l.get("bind_address", "0.0.0.0"),
                bind_port=int(l.get("bind_port", 443)),
                protocol=(l.get("transport") or {}).get("transport_type", "https").lower(),
                status="running" if l.get("enabled", True) else "stopped",
                meta={"transport_id": l.get("transport_id")},
            )
            for l in items
        ]

    # ── Agents ────────────────────────────────────────────────────────────────

    async def list_agents(self) -> list[Implant]:
        self._require_connected()
        data  = await self._get("/api/agent")
        items = (data.get("datas") or data) if isinstance(data, dict) else data
        if not isinstance(items, list):
            items = []
        return [self._parse_agent(a) for a in items]

    def _parse_agent(self, a: dict[str, Any]) -> Implant:
        aid = str(a.get("id") or uuid.uuid4())

        def _dt(v: Any) -> datetime:
            if not v:
                return datetime.utcnow()
            for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S.%fZ",
                        "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
                try:
                    return datetime.strptime(str(v)[:26], fmt)
                except ValueError:
                    continue
            return datetime.utcnow()

        integrity = "ADMIN" if a.get("admin") is True else "USER"

        return Implant(
            id=aid,
            name=a.get("name") or a.get("hostname") or aid,
            c2_type=self._config.c2_type,
            listener_id=str(a.get("listener_id") or ""),
            external_ip=a.get("external_ip", ""),
            internal_ip=a.get("internal_ip") or a.get("ip_address", ""),
            hostname=a.get("hostname", ""),
            username=a.get("username") or a.get("user", ""),
            os=a.get("os") or a.get("operating_system", ""),
            arch=a.get("architecture") or a.get("arch", ""),
            pid=int(a.get("pid") or a.get("process_id", 0)),
            process_name=a.get("process_name") or a.get("process", ""),
            integrity=integrity,
            last_checkin=_dt(a.get("last_checkin") or a.get("last_seen")),
            first_seen=_dt(a.get("first_seen") or a.get("registered")),
            active=a.get("enabled", True) and not a.get("killed", False),
            meta={"agent_type": a.get("agent_type", ""), "sleep_time": a.get("sleep_time", 60)},
        )

    # ── Tasks ─────────────────────────────────────────────────────────────────

    _TASK_TYPES: dict[str, str] = {
        "shell": "shell", "cmd": "shell",
        "ps": "powershell", "powershell": "powershell",
        "upload": "upload", "download": "download",
        "ls": "list_directory", "cd": "change_directory",
        "cat": "read_file", "whoami": "whoami",
        "ps_list": "list_processes", "kill": "kill_process",
        "screenshot": "screenshot", "inject": "inject",
        "sleep": "modify_sleep", "exit": "exit",
        "module": "run_module",
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

        params: dict[str, Any]
        if task_type in ("shell", "powershell"):
            params = {"command": " ".join(extra) if extra else command}
        elif task_type == "modify_sleep":
            params = {"sleep_time": int(extra[0]) if extra else 60, "jitter": int(extra[1]) if len(extra) > 1 else 10}
        elif task_type == "inject":
            params = {"shellcode": extra[0] if extra else "", "pid": int(extra[1]) if len(extra) > 1 and extra[1].isdigit() else 0}
        else:
            params = {"args": extra}

        data  = await self._post("/api/task", json={"agent_id": agent_id, "task_type": task_type, "parameters": params})
        datas = data.get("datas") or data
        return Task(
            id=str(datas.get("id") or uuid.uuid4()),
            agent_id=agent_id,
            c2_type=str(self._config.c2_type),
            command=command,
            args=args_list,
            status=datas.get("status", "queued"),
            meta={"task_type": task_type},
        )

    async def get_task_result(self, task_id: str) -> dict[str, Any]:
        self._require_connected()
        data  = await self._get(f"/api/task/{task_id}")
        datas = data.get("datas") or data
        return {"task_id": task_id, "status": datas.get("status"), "output": datas.get("output", "")}

    # ── Payload ───────────────────────────────────────────────────────────────

    async def generate_payload(self, config: PayloadConfig) -> bytes:
        self._require_connected()
        fmt_map = {"exe": "dotnet_exe", "ps1": "powershell", "dll": "dotnet_dll", "shellcode": "shellcode", "elf": "elf"}
        data    = await self._post("/api/payload", json={
            "listener_id": config.listener_id,
            "payload_type": config.extra.get("payload_type", fmt_map.get(config.format, "dotnet_exe")),
            "arch": config.arch, "name": config.name,
            "sleep_time": config.sleep, "jitter": config.jitter,
        })
        datas   = data.get("datas") or data
        file_id = datas.get("file_id") or datas.get("id")
        if file_id:
            resp = await self._client.get(f"/api/payload/{file_id}/download")
            return resp.content if resp.status_code == 200 else b""
        import base64
        b64 = datas.get("data") or datas.get("payload", "")
        return base64.b64decode(b64) if b64 else b""

    async def list_modules(self) -> list[dict[str, Any]]:
        self._require_connected()
        data  = await self._get("/api/module")
        items = (data.get("datas") or data) if isinstance(data, dict) else data
        return items if isinstance(items, list) else []

    async def run_module(self, agent_id: str, module_name: str, options: dict[str, Any]) -> Task:
        self._require_connected()
        data  = await self._post(f"/api/agent/{agent_id}/module/run", json={"module": module_name, "options": options})
        datas = data.get("datas") or data
        return Task(
            id=str(datas.get("id") or uuid.uuid4()),
            agent_id=agent_id,
            c2_type=str(self._config.c2_type),
            command=f"module:{module_name}",
            status=datas.get("status", "queued"),
            meta={"module": module_name},
        )

    async def get_capabilities(self) -> list[str]:
        return self.CAPABILITIES
