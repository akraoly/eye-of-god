"""Fixtures communes pour les tests C2Manager."""
from __future__ import annotations

import asyncio
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from c2_manager.models import C2Config, C2Type


@pytest.fixture
def sliver_config() -> C2Config:
    return C2Config(
        name="test-sliver",
        c2_type=C2Type.SLIVER,
        host="127.0.0.1",
        port=31337,
        extra={"operator_cfg": "/tmp/test_operator.cfg"},
    )


@pytest.fixture
def empire_config() -> C2Config:
    return C2Config(
        name="test-empire",
        c2_type=C2Type.EMPIRE,
        host="127.0.0.1",
        port=1337,
        username="empireadmin",
        password="password123",
    )


@pytest.fixture
def mythic_config() -> C2Config:
    return C2Config(
        name="test-mythic",
        c2_type=C2Type.MYTHIC,
        host="127.0.0.1",
        port=7443,
        ssl=True,
        username="mythic_admin",
        password="mythic_password",
        extra={"graphql_url": "https://127.0.0.1:7443/graphql"},
    )


@pytest.fixture
def cobalt_strike_config() -> C2Config:
    return C2Config(
        name="test-cs",
        c2_type=C2Type.COBALT_STRIKE,
        host="127.0.0.1",
        port=2222,
        extra={"mode": "external_c2"},
    )


@pytest.fixture
def mock_httpx_client():
    """Mock client httpx pour les tests REST."""
    mock = AsyncMock()
    mock.get   = AsyncMock()
    mock.post  = AsyncMock()
    mock.put   = AsyncMock()
    mock.delete = AsyncMock()
    mock.aclose = AsyncMock()
    return mock


def make_resp(status: int = 200, json_data: dict = None) -> MagicMock:
    """Helper : créer une réponse httpx mockée."""
    resp = MagicMock()
    resp.status_code = status
    resp.json = MagicMock(return_value=json_data or {})
    resp.content = b"{}" if json_data is not None else b""
    resp.text = str(json_data or {})
    resp.raise_for_status = MagicMock()
    return resp
