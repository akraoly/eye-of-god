"""
PwnDoc — REST API Node.js pour rapports de pentest.

PwnDoc est un outil de documentation pentest (rapports Word/PDF).
Port      : 5000 (HTTP) / 8443 (HTTPS) par défaut
Auth      : POST /api/users/token → {datas: {token, refreshToken}}

Note : PwnDoc n'est pas un C2 mais un outil de gestion de vulnérabilités
intégré à L'Œil de Dieu. Les "listeners" = audits, les "agents" = findings.

Endpoints REST :
  POST /api/users/token               → auth (JWT + refresh)
  GET  /api/audits                    → liste des audits
  POST /api/audits                    → créer un audit
  GET  /api/audits/{id}               → détail audit avec findings
  DELETE /api/audits/{id}             → supprimer audit
  GET  /api/audits/{id}/export/word   → rapport Word
  GET  /api/vulnerabilities           → base de vulnérabilités
  POST /api/vulnerabilities           → ajouter une vuln
  GET  /api/companies                 → clients
  GET  /api/templates                 → templates de rapport
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


class PwnDocC2(RestC2Interface):
    """
    PwnDoc — outil de documentation pentest intégré à L'Œil de Dieu.

    Paramètres extra (config.extra) :
      verify_ssl : bool  (défaut: False)
    """

    CAPABILITIES = [
        "list_audits", "create_audit", "list_vulnerabilities",
        "add_vulnerability", "generate_report", "list_clients",
        "list_templates", "export_word",
    ]

    def __init__(self) -> None:
        super().__init__()
        self._refresh_token: str | None = None

    # ── Auth ──────────────────────────────────────────────────────────────────

    async def _authenticate(self, config: C2Config) -> str:
        async with httpx.AsyncClient(
            base_url=config.base_url,
            verify=config.extra.get("verify_ssl", False),
            timeout=15.0,
        ) as client:
            resp = await client.post(
                "/api/users/token",
                json={"username": config.username or "admin", "password": config.password or ""},
            )
            if resp.status_code not in (200, 201):
                raise C2AuthError(f"PwnDoc auth échouée [{resp.status_code}]: {resp.text[:200]}")
            data  = resp.json()
            datas = data.get("datas") or data
            token = datas.get("token") or datas.get("access_token")
            if not token:
                raise C2AuthError(f"Token PwnDoc absent : {data}")
            self._refresh_token = datas.get("refreshToken") or datas.get("refresh_token")
            logger.info("PwnDoc : authentifié")
            return token

    async def get_status(self) -> C2Status:
        if not self._client:
            return C2Status.DISCONNECTED
        try:
            resp = await self._client.get("/api/audits", timeout=5.0)
            return C2Status.CONNECTED if resp.status_code == 200 else C2Status.ERROR
        except Exception:
            return C2Status.ERROR

    # ── Listeners = Audits ────────────────────────────────────────────────────

    async def create_listener(self, config: dict[str, Any]) -> Listener:
        self._require_connected()
        name = config.get("name", f"Audit-{datetime.utcnow().strftime('%Y%m%d')}")
        body = {
            "name":          name,
            "auditType":     config.get("audit_type", "Internal"),
            "date":          config.get("date", datetime.utcnow().strftime("%Y-%m-%d")),
            "date_start":    config.get("date_start", ""),
            "date_end":      config.get("date_end", ""),
            "language":      config.get("language", "en"),
            "template":      config.get("template", ""),
            "company":       config.get("company", ""),
            "collaborators": config.get("collaborators", []),
            "scope":         config.get("scope", []),
        }
        data  = await self._post("/api/audits", json=body)
        datas = data.get("datas", data)
        aid   = str(datas.get("_id") or datas.get("id") or uuid.uuid4())
        return Listener(
            id=aid, name=name, c2_type=self._config.c2_type,
            bind_host="pwndoc", bind_port=0,
            protocol=config.get("audit_type", "Internal"),
            status="running",
            meta={"audit_type": config.get("audit_type", "Internal")},
        )

    async def remove_listener(self, listener_id: str) -> bool:
        self._require_connected()
        try:
            await self._delete(f"/api/audits/{listener_id}")
            return True
        except Exception as exc:
            logger.error("PwnDoc delete audit : %s", exc)
            return False

    async def list_listeners(self) -> list[Listener]:
        self._require_connected()
        data  = await self._get("/api/audits")
        items = (data.get("datas") or data) if isinstance(data, dict) else data
        if not isinstance(items, list):
            items = []
        return [
            Listener(
                id=str(a.get("_id") or a.get("id") or uuid.uuid4()),
                name=a.get("name", ""),
                c2_type=self._config.c2_type,
                bind_host="pwndoc", bind_port=0,
                protocol=a.get("auditType", "Internal"),
                status="running" if a.get("state") != "REVIEW" else "stopped",
                meta={"date": a.get("date"), "language": a.get("language", "en")},
            )
            for a in items
        ]

    # ── Agents = Vulnérabilités ───────────────────────────────────────────────

    async def list_agents(self) -> list[Implant]:
        self._require_connected()
        data  = await self._get("/api/vulnerabilities")
        items = (data.get("datas") or data) if isinstance(data, dict) else data
        if not isinstance(items, list):
            items = []
        return [
            Implant(
                id=str(v.get("_id") or v.get("id") or uuid.uuid4()),
                name=v.get("name") or v.get("title", ""),
                c2_type=self._config.c2_type,
                listener_id="",
                hostname="pwndoc",
                os=v.get("category", ""),
                integrity=self._cvss_severity(v.get("cvssScore") or v.get("cvss", 0.0)),
                active=True,
                meta={
                    "category":    v.get("category", ""),
                    "cvss_score":  v.get("cvssScore") or v.get("cvss", 0.0),
                    "cvss_vector": v.get("cvssVector", ""),
                    "cwe":         v.get("cwe", ""),
                },
            )
            for v in items
        ]

    @staticmethod
    def _cvss_severity(score: Any) -> str:
        try:
            s = float(score)
        except (TypeError, ValueError):
            return "USER"
        return "SYSTEM" if s >= 9.0 else "ADMIN" if s >= 7.0 else "USER"

    async def send_task(
        self,
        agent_id: str,
        command:  str,
        args:     list[str] | None = None,
    ) -> Task:
        """Ajoute un finding à un audit (agent_id = audit_id)."""
        self._require_connected()
        args_list = args or []
        audit_id  = args_list[0] if args_list else agent_id
        severity  = args_list[1] if len(args_list) > 1 else "Medium"
        cvss      = float(args_list[2]) if len(args_list) > 2 else 5.0

        data  = await self._post(f"/api/audits/{audit_id}/findings", json={
            "title":     command,
            "severity":  severity,
            "cvssScore": cvss,
            "status":    0,
        })
        datas = data.get("datas", data)
        return Task(
            id=str(datas.get("_id") or datas.get("id") or uuid.uuid4()),
            agent_id=audit_id,
            c2_type=str(self._config.c2_type),
            command=command,
            args=args_list,
            status="queued",
            meta={"severity": severity, "cvss": cvss},
        )

    async def get_task_result(self, task_id: str) -> dict[str, Any]:
        self._require_connected()
        data  = await self._get(f"/api/vulnerabilities/{task_id}")
        datas = data.get("datas", data)
        return {"task_id": task_id, "status": "completed", "title": datas.get("name", "")}

    # ── Payload = rapport Word ────────────────────────────────────────────────

    async def generate_payload(self, config: PayloadConfig) -> bytes:
        self._require_connected()
        resp = await self._client.get(f"/api/audits/{config.listener_id}/export/word")
        return resp.content if resp.status_code == 200 else b""

    # ── Méthodes PwnDoc spécifiques ───────────────────────────────────────────

    async def list_vulnerabilities(self, search: str = "") -> list[dict[str, Any]]:
        self._require_connected()
        data  = await self._get("/api/vulnerabilities", params={"search": search} if search else {})
        items = (data.get("datas") or data) if isinstance(data, dict) else data
        return items if isinstance(items, list) else []

    async def add_vulnerability(
        self, title: str, cvss: float, description: str = "", category: str = ""
    ) -> dict[str, Any]:
        self._require_connected()
        data  = await self._post("/api/vulnerabilities", json={
            "name": title, "cvssScore": cvss,
            "category": category,
            "details": [{"locale": "en", "title": title, "description": description}],
        })
        datas = data.get("datas", data)
        return {"id": str(datas.get("_id") or datas.get("id", "")), "title": title}

    async def list_clients(self) -> list[dict[str, Any]]:
        self._require_connected()
        data  = await self._get("/api/companies")
        items = (data.get("datas") or data) if isinstance(data, dict) else data
        return items if isinstance(items, list) else []

    async def generate_report(self, audit_id: str) -> bytes:
        self._require_connected()
        resp = await self._client.get(f"/api/audits/{audit_id}/export/word")
        return resp.content if resp.status_code == 200 else b""

    async def get_capabilities(self) -> list[str]:
        return self.CAPABILITIES
