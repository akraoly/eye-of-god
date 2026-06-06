"""RestC2Interface — base pour toutes les intégrations REST/HTTP."""
from __future__ import annotations

import logging
from typing import Any

import httpx

from c2_manager.interfaces.base import BaseC2Interface, C2AuthError, C2Error
from c2_manager.models import C2Config, C2Status

logger = logging.getLogger(__name__)


class RestC2Interface(BaseC2Interface):
    """
    Base commune pour les C2 REST (Empire, Covenant, Mythic, PoshC2…).
    Fournit un client httpx async persistant avec bearer token.
    """

    def __init__(self) -> None:
        super().__init__()
        self._client: httpx.AsyncClient | None = None
        self._token:  str | None = None

    def _build_client(self, config: C2Config) -> httpx.AsyncClient:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        elif config.api_key:
            headers["Authorization"] = f"Bearer {config.api_key}"
        return httpx.AsyncClient(
            base_url=config.base_url,
            headers=headers,
            verify=False,
            timeout=30.0,
        )

    async def _authenticate(self, config: C2Config) -> str:
        """Obtenir un token JWT. Doit être surchargé si endpoint != /token."""
        async with httpx.AsyncClient(
            base_url=config.base_url, verify=False, timeout=15.0
        ) as client:
            resp = await client.post(
                "/token",
                json={"username": config.username, "password": config.password},
            )
            if resp.status_code not in (200, 201):
                raise C2AuthError(
                    f"Auth échouée [{resp.status_code}]: {resp.text[:200]}"
                )
            data = resp.json()
            token = data.get("access_token") or data.get("token") or data.get("key")
            if not token:
                raise C2AuthError(f"Token absent dans la réponse: {data}")
            return token

    async def connect(self, config: C2Config) -> bool:
        self._config = config
        self._token = await self._authenticate(config)
        self._client = self._build_client(config)
        return True

    async def disconnect(self) -> None:
        await self.stop_healthcheck()
        if self._client:
            await self._client.aclose()
            self._client = None
        self._token = None
        self._status = C2Status.DISCONNECTED

    async def get_status(self) -> C2Status:
        if not self._client:
            return C2Status.DISCONNECTED
        try:
            resp = await self._client.get("/api/v2/agents", timeout=5.0)
            return C2Status.CONNECTED if resp.status_code < 500 else C2Status.ERROR
        except Exception:
            return C2Status.ERROR

    async def _get(self, path: str, **kwargs: Any) -> Any:
        self._require_connected()
        resp = await self._client.get(path, **kwargs)
        resp.raise_for_status()
        return resp.json()

    async def _post(self, path: str, json: Any = None, **kwargs: Any) -> Any:
        self._require_connected()
        resp = await self._client.post(path, json=json, **kwargs)
        resp.raise_for_status()
        return resp.json()

    async def _delete(self, path: str, **kwargs: Any) -> Any:
        self._require_connected()
        resp = await self._client.delete(path, **kwargs)
        resp.raise_for_status()
        return resp.json() if resp.content else {}

    async def _put(self, path: str, json: Any = None, **kwargs: Any) -> Any:
        self._require_connected()
        resp = await self._client.put(path, json=json, **kwargs)
        resp.raise_for_status()
        return resp.json()
