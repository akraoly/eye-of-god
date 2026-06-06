"""
RedGuard — reverse proxy C2 Traffic Control + admin REST API.

RedGuard (github.com/wikiZ/RedGuard) — outil de filtrage du trafic C2.
Rôle      : reverse proxy qui filtre les connexions des implants
Port REST  : port configurable (défaut: 4433 pour l'admin API)
Auth       : POST /api/v1/auth/login → token (si auth activée)
             ou Basic Auth / API Key

Note : RedGuard est un traffic redirector, pas un vrai C2. Dans L'Œil de Dieu,
les "agents" = connexions passant par RedGuard (traffic logs),
les "listeners" = règles de proxy configurées.

Endpoints REST (API d'administration) :
  POST /api/v1/auth/login         → auth → token
  GET  /api/v1/status             → statut du proxy
  GET  /api/v1/config             → configuration actuelle
  PUT  /api/v1/config             → modifier la configuration
  GET  /api/v1/rules              → liste des règles de proxy
  POST /api/v1/rules              → ajouter une règle
  DELETE /api/v1/rules/{id}       → supprimer une règle
  GET  /api/v1/allowlist          → liste blanche IP/UA
  POST /api/v1/allowlist          → ajouter à la liste blanche
  GET  /api/v1/blocklist          → liste noire IP/UA
  POST /api/v1/blocklist          → ajouter à la liste noire
  GET  /api/v1/traffic/logs       → logs de trafic
  GET  /api/v1/traffic/stats      → statistiques
  POST /api/v1/proxy/start        → démarrer le proxy
  POST /api/v1/proxy/stop         → arrêter le proxy
  GET  /api/v1/certificates       → certificats TLS
  POST /api/v1/certificates       → générer/importer un certificat
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


class RedGuardC2(RestC2Interface):
    """
    RedGuard — reverse proxy traffic filtering.

    Paramètres extra (config.extra) :
      verify_ssl     : bool  (défaut: False)
      api_key        : str   — clé API statique
      no_auth        : bool  — RedGuard sans auth (défaut: False)
      upstream_c2    : str   — URL du vrai C2 en amont
      api_prefix     : str   — préfixe API (défaut: "/api/v1")
    """

    CAPABILITIES = [
        "list_rules", "add_rule", "delete_rule",
        "list_allowlist", "add_allowlist",
        "list_blocklist", "add_blocklist",
        "get_traffic_logs", "get_stats",
        "start_proxy", "stop_proxy",
        "get_config", "update_config",
    ]

    def __init__(self) -> None:
        super().__init__()
        self._api_prefix = "/api/v1"

    # ── Auth ──────────────────────────────────────────────────────────────────

    async def _authenticate(self, config: C2Config) -> str:
        self._api_prefix = config.extra.get("api_prefix", "/api/v1")
        api_key = config.extra.get("api_key")
        if api_key:
            return api_key

        if config.extra.get("no_auth", False):
            return "no-auth"

        async with httpx.AsyncClient(
            base_url=config.base_url,
            verify=config.extra.get("verify_ssl", False),
            timeout=15.0,
        ) as client:
            resp = await client.post(
                f"{self._api_prefix}/auth/login",
                json={"username": config.username or "admin", "password": config.password or ""},
            )
            if resp.status_code not in (200, 201):
                raise C2AuthError(f"RedGuard auth échouée [{resp.status_code}]: {resp.text[:200]}")
            data  = resp.json()
            token = data.get("token") or data.get("access_token") or (data.get("data") or {}).get("token")
            if not token:
                raise C2AuthError(f"Token RedGuard absent : {data}")
            logger.info("RedGuard : authentifié")
            return token

    async def get_status(self) -> C2Status:
        if not self._client:
            return C2Status.DISCONNECTED
        try:
            resp = await self._client.get(f"{self._api_prefix}/status", timeout=5.0)
            return C2Status.CONNECTED if resp.status_code == 200 else C2Status.ERROR
        except Exception:
            return C2Status.ERROR

    # ── Listeners = règles de proxy ───────────────────────────────────────────

    async def create_listener(self, config: dict[str, Any]) -> Listener:
        self._require_connected()
        protocol = config.get("protocol", "https").lower()
        host     = config.get("bind_host", "0.0.0.0")
        port     = int(config.get("bind_port", 443))
        name     = config.get("name", f"redguard-{protocol}-{port}")
        upstream = config.get("upstream", self._config.extra.get("upstream_c2", ""))

        # Profils de filtrage RedGuard
        profile_types = {
            "strict":  {"filter_by_ua": True, "filter_by_ip": True, "geo_block": True},
            "medium":  {"filter_by_ua": True, "filter_by_ip": False, "geo_block": False},
            "permissive": {"filter_by_ua": False, "filter_by_ip": False, "geo_block": False},
        }
        profile_cfg  = profile_types.get(config.get("profile", "medium"), profile_types["medium"])

        body = {
            "name":          name,
            "listen_host":   host,
            "listen_port":   port,
            "upstream":      upstream,
            "protocol":      protocol,
            "ssl":           protocol in ("https", "tls"),
            "cert_path":     config.get("cert_path", ""),
            "key_path":      config.get("key_path", ""),
            "profile":       config.get("profile", "medium"),
            **profile_cfg,
            "allowed_ips":   config.get("allowed_ips", []),
            "blocked_ips":   config.get("blocked_ips", []),
            "allowed_ua":    config.get("allowed_ua", ["Mozilla/5.0"]),
            "blocked_ua":    config.get("blocked_ua", ["curl", "python-requests", "Masscan"]),
            "allowed_countries": config.get("allowed_countries", []),
            "blocked_countries": config.get("blocked_countries", ["CN", "RU", "KP", "IR"]),
            "redirect_url":  config.get("redirect_url", "https://www.microsoft.com"),
            "jitter":        config.get("jitter", 0),
        }

        data = await self._post(f"{self._api_prefix}/rules", json=body)
        rid  = str(data.get("id") or data.get("rule_id") or uuid.uuid4())
        return Listener(
            id=rid,
            name=name,
            c2_type=self._config.c2_type,
            bind_host=host,
            bind_port=port,
            protocol=protocol,
            status="running" if data.get("active", True) else "stopped",
            meta={
                "upstream": upstream,
                "profile":  config.get("profile", "medium"),
                "redirect": body["redirect_url"],
            },
        )

    async def remove_listener(self, listener_id: str) -> bool:
        self._require_connected()
        try:
            await self._delete(f"{self._api_prefix}/rules/{listener_id}")
            return True
        except Exception as exc:
            logger.error("RedGuard delete rule : %s", exc)
            return False

    async def list_listeners(self) -> list[Listener]:
        self._require_connected()
        data  = await self._get(f"{self._api_prefix}/rules")
        items = data if isinstance(data, list) else data.get("rules", data.get("data", []))
        return [
            Listener(
                id=str(r.get("id") or r.get("rule_id") or uuid.uuid4()),
                name=r.get("name", ""),
                c2_type=self._config.c2_type,
                bind_host=r.get("listen_host", "0.0.0.0"),
                bind_port=int(r.get("listen_port", 443)),
                protocol=r.get("protocol", "https"),
                status="running" if r.get("active", True) else "stopped",
                meta={
                    "upstream": r.get("upstream", ""),
                    "profile":  r.get("profile", ""),
                },
            )
            for r in items
        ]

    # ── Agents = connexions filtrées ──────────────────────────────────────────

    async def list_agents(self) -> list[Implant]:
        """Liste les connexions récentes passant par RedGuard."""
        self._require_connected()
        try:
            data = await self._get(f"{self._api_prefix}/traffic/logs", params={"limit": 100})
        except Exception:
            return []
        items = data if isinstance(data, list) else data.get("logs", data.get("data", []))

        seen: dict[str, Implant] = {}
        for log in items:
            ip = log.get("remote_ip") or log.get("client_ip", "")
            if not ip or ip in seen:
                continue
            seen[ip] = Implant(
                id=ip,
                name=f"client-{ip}",
                c2_type=self._config.c2_type,
                listener_id=str(log.get("rule_id", "")),
                external_ip=ip,
                hostname=log.get("hostname") or ip,
                os=log.get("os", ""),
                active=True,
                meta={
                    "user_agent":  log.get("user_agent", ""),
                    "last_method": log.get("method", ""),
                    "allowed":     log.get("allowed", True),
                    "country":     log.get("country", ""),
                },
            )
        return list(seen.values())

    # ── Tasks = commandes proxy ───────────────────────────────────────────────

    async def send_task(
        self,
        agent_id: str,
        command:  str,
        args:     list[str] | None = None,
    ) -> Task:
        """
        Envoie une commande de gestion au proxy RedGuard.
        command : "block <ip>", "allow <ip>", "reload", "stats", "stop", "start"
        """
        self._require_connected()
        args_list = args or []
        cmd_lower = command.lower().split()[0]
        extra     = command.split()[1:] + args_list

        if cmd_lower == "block":
            ip = extra[0] if extra else ""
            data = await self._post(f"{self._api_prefix}/blocklist", json={"ip": ip, "permanent": True})
        elif cmd_lower == "allow":
            ip = extra[0] if extra else ""
            data = await self._post(f"{self._api_prefix}/allowlist", json={"ip": ip})
        elif cmd_lower in ("start", "stop"):
            data = await self._post(f"{self._api_prefix}/proxy/{cmd_lower}")
        elif cmd_lower == "reload":
            data = await self._post(f"{self._api_prefix}/config/reload")
        elif cmd_lower == "stats":
            data = await self._get(f"{self._api_prefix}/traffic/stats")
        else:
            # Commande générique
            data = await self._post(f"{self._api_prefix}/commands", json={"command": command, "args": extra})

        return Task(
            id=str(data.get("id") or uuid.uuid4()),
            agent_id=agent_id,
            c2_type=str(self._config.c2_type),
            command=command,
            args=args_list,
            status="completed",
            result=str(data),
            meta={"cmd_type": cmd_lower},
        )

    async def get_task_result(self, task_id: str) -> dict[str, Any]:
        self._require_connected()
        data = await self._get(f"{self._api_prefix}/commands/{task_id}")
        return {"task_id": task_id, "status": data.get("status", "completed"), "output": str(data)}

    # ── Payload (config générée) ──────────────────────────────────────────────

    async def generate_payload(self, config: PayloadConfig) -> bytes:
        """Génère une configuration RedGuard (config.ini)."""
        self._require_connected()
        try:
            data = await self._get(f"{self._api_prefix}/config")
        except Exception:
            return b""
        # Retourne la config sous forme de texte ini
        cfg_text = "\n".join(f"{k} = {v}" for k, v in data.items())
        return cfg_text.encode()

    # ── Méthodes RedGuard spécifiques ─────────────────────────────────────────

    async def get_traffic_logs(self, limit: int = 100) -> list[dict[str, Any]]:
        self._require_connected()
        data  = await self._get(f"{self._api_prefix}/traffic/logs", params={"limit": limit})
        items = data if isinstance(data, list) else data.get("logs", data.get("data", []))
        return items

    async def get_stats(self) -> dict[str, Any]:
        self._require_connected()
        return await self._get(f"{self._api_prefix}/traffic/stats")

    async def add_to_blocklist(self, ip: str, reason: str = "", permanent: bool = True) -> bool:
        self._require_connected()
        try:
            await self._post(f"{self._api_prefix}/blocklist", json={
                "ip": ip, "reason": reason, "permanent": permanent
            })
            return True
        except Exception:
            return False

    async def add_to_allowlist(self, ip: str, description: str = "") -> bool:
        self._require_connected()
        try:
            await self._post(f"{self._api_prefix}/allowlist", json={"ip": ip, "description": description})
            return True
        except Exception:
            return False

    async def get_config(self) -> dict[str, Any]:
        self._require_connected()
        return await self._get(f"{self._api_prefix}/config")

    async def update_config(self, updates: dict[str, Any]) -> bool:
        self._require_connected()
        try:
            await self._put(f"{self._api_prefix}/config", json=updates)
            return True
        except Exception:
            return False

    async def get_capabilities(self) -> list[str]:
        return self.CAPABILITIES
