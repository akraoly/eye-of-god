"""RpcC2Interface — base pour MSFRPC (Metasploit) et Pupy RPC."""
from __future__ import annotations

import logging
from typing import Any

import httpx

from c2_manager.interfaces.base import BaseC2Interface, C2AuthError
from c2_manager.models import C2Config, C2Status

logger = logging.getLogger(__name__)


class MsfRpcC2Interface(BaseC2Interface):
    """
    Base pour Metasploit MSFRPC (port 55553 par défaut).
    Utilise msgpack sur HTTP (Content-Type: binary/message-pack)
    ou JSON selon la configuration.
    """

    def __init__(self) -> None:
        super().__init__()
        self._client:  httpx.AsyncClient | None = None
        self._auth_id: str | None = None

    def _rpc_url(self, config: C2Config) -> str:
        scheme = "https" if config.ssl else "http"
        return f"{scheme}://{config.host}:{config.port}/api/1.0"

    async def _call(self, method: str, *args: Any) -> Any:
        """Appel JSON-RPC Metasploit."""
        self._require_connected()
        payload = [method, self._auth_id] + list(args)
        resp = await self._client.post(
            "/api/1.0",
            json=payload,
            headers={"Content-Type": "application/json"},
        )
        resp.raise_for_status()
        result = resp.json()
        if isinstance(result, dict) and result.get("error"):
            raise Exception(f"MSFRPC error: {result}")
        return result

    async def connect(self, config: C2Config) -> bool:
        self._config = config
        self._client = httpx.AsyncClient(
            base_url=f"http{'s' if config.ssl else ''}://{config.host}:{config.port}",
            verify=False,
            timeout=30.0,
        )
        payload = ["auth.login", config.username or "msf", config.password or ""]
        resp = await self._client.post(
            "/api/1.0",
            json=payload,
            headers={"Content-Type": "application/json"},
        )
        if resp.status_code != 200:
            raise C2AuthError(f"MSFRPC auth échouée [{resp.status_code}]")
        data = resp.json()
        if data.get("result") != "success":
            raise C2AuthError(f"MSFRPC login refusé : {data}")
        self._auth_id = data.get("token")
        return True

    async def disconnect(self) -> None:
        if self._auth_id and self._client:
            try:
                await self._call("auth.logout", self._auth_id)
            except Exception:
                pass
        if self._client:
            await self._client.aclose()
        self._auth_id = None
        self._client  = None
        self._status  = C2Status.DISCONNECTED

    async def get_status(self) -> C2Status:
        if not self._client or not self._auth_id:
            return C2Status.DISCONNECTED
        try:
            result = await self._call("core.version")
            return C2Status.CONNECTED if result else C2Status.ERROR
        except Exception:
            return C2Status.ERROR
