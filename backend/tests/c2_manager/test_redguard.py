"""Tests RedGuardC2 — reverse proxy traffic filtering."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from c2_manager.integrations.redguard import RedGuardC2
from c2_manager.models import C2Config, C2Type, C2Status
from c2_manager.models.payload import PayloadConfig
from tests.c2_manager.conftest import make_resp


@pytest.fixture
def redguard_config() -> C2Config:
    return C2Config(
        name="test-redguard",
        c2_type=C2Type.REDGUARD,
        host="127.0.0.1",
        port=4433,
        ssl=True,
        username="admin",
        password="redguard123",
        extra={"verify_ssl": False},
    )


@pytest.fixture
def redguard(redguard_config):
    r = RedGuardC2()
    r._config     = redguard_config
    r._status     = C2Status.CONNECTED
    r._client     = AsyncMock()
    r._token      = "rg-token"
    r._api_prefix = "/api/v1"
    return r


# ── Auth ──────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_authenticate_jwt(redguard_config):
    c = RedGuardC2()
    mock_resp = make_resp(200, {"token": "rg-jwt"})
    with patch("httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__  = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_cls.return_value = mock_client
        token = await c._authenticate(redguard_config)
    assert token == "rg-jwt"


@pytest.mark.asyncio
async def test_authenticate_api_key(redguard_config):
    redguard_config.extra["api_key"] = "static-key"
    c = RedGuardC2()
    token = await c._authenticate(redguard_config)
    assert token == "static-key"


@pytest.mark.asyncio
async def test_authenticate_no_auth(redguard_config):
    redguard_config.extra["no_auth"] = True
    c = RedGuardC2()
    token = await c._authenticate(redguard_config)
    assert token == "no-auth"


@pytest.mark.asyncio
async def test_authenticate_nested_token(redguard_config):
    """Token imbriqué dans data.token."""
    c = RedGuardC2()
    mock_resp = make_resp(200, {"data": {"token": "nested-tok"}})
    with patch("httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__  = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_cls.return_value = mock_client
        token = await c._authenticate(redguard_config)
    assert token == "nested-tok"


# ── Listeners (règles) ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_listener_strict(redguard):
    """Créer une règle proxy avec profil strict."""
    redguard._client.post = AsyncMock(return_value=make_resp(201, {
        "id": "rule-1", "active": True,
    }))
    listener = await redguard.create_listener({
        "protocol": "https",
        "bind_host": "0.0.0.0",
        "bind_port": 443,
        "name": "c2-proxy",
        "upstream": "https://real-c2.internal:443",
        "profile": "strict",
    })
    assert listener.id == "rule-1"
    assert listener.protocol == "https"
    assert listener.meta["profile"] == "strict"


@pytest.mark.asyncio
async def test_create_listener_medium_profile(redguard):
    """Profil medium activé par défaut."""
    redguard._client.post = AsyncMock(return_value=make_resp(201, {
        "id": "rule-2", "active": True,
    }))
    listener = await redguard.create_listener({
        "bind_port": 80,
    })
    call_body = redguard._client.post.call_args[1].get("json", {})
    assert call_body.get("profile") == "medium"


@pytest.mark.asyncio
async def test_list_listeners(redguard):
    redguard._client.get = AsyncMock(return_value=make_resp(200, {
        "rules": [
            {"id": "r1", "name": "proxy-443", "listen_host": "0.0.0.0",
             "listen_port": 443, "protocol": "https", "active": True,
             "profile": "strict", "upstream": "https://c2:443"},
        ]
    }))
    listeners = await redguard.list_listeners()
    assert len(listeners) == 1
    assert listeners[0].bind_port == 443
    assert listeners[0].status == "running"


@pytest.mark.asyncio
async def test_remove_listener(redguard):
    redguard._client.delete = AsyncMock(return_value=make_resp(204, {}))
    result = await redguard.remove_listener("rule-1")
    assert result is True


@pytest.mark.asyncio
async def test_remove_listener_error(redguard):
    redguard._client.delete = AsyncMock(side_effect=Exception("404"))
    result = await redguard.remove_listener("inexistant")
    assert result is False


# ── Agents (connexions) ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_agents_from_logs(redguard):
    """Les agents = IPs uniques dans les logs de trafic."""
    redguard._client.get = AsyncMock(return_value=make_resp(200, {
        "logs": [
            {"remote_ip": "10.0.0.1", "user_agent": "Mozilla/5.0",
             "method": "GET", "allowed": True, "rule_id": "r1"},
            {"remote_ip": "10.0.0.1", "user_agent": "Mozilla/5.0",
             "method": "POST", "allowed": True, "rule_id": "r1"},  # doublon → 1 agent
            {"remote_ip": "10.0.0.2", "user_agent": "CobaltStrike/4.x",
             "method": "GET", "allowed": True, "rule_id": "r1"},
        ]
    }))
    agents = await redguard.list_agents()
    assert len(agents) == 2  # 2 IPs uniques


@pytest.mark.asyncio
async def test_list_agents_empty_on_error(redguard):
    """Retourner [] si l'API échoue."""
    redguard._client.get = AsyncMock(side_effect=Exception("net error"))
    agents = await redguard.list_agents()
    assert agents == []


# ── Tasks (commandes proxy) ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_send_task_block_ip(redguard):
    redguard._client.post = AsyncMock(return_value=make_resp(200, {"id": "t1"}))
    task = await redguard.send_task("*", "block 10.0.0.99", [])
    assert task.meta["cmd_type"] == "block"
    assert task.status == "completed"


@pytest.mark.asyncio
async def test_send_task_allow_ip(redguard):
    redguard._client.post = AsyncMock(return_value=make_resp(200, {"id": "t2"}))
    task = await redguard.send_task("*", "allow 10.0.0.50", [])
    assert task.meta["cmd_type"] == "allow"


@pytest.mark.asyncio
async def test_send_task_start_stop(redguard):
    redguard._client.post = AsyncMock(return_value=make_resp(200, {"id": "t3"}))
    task = await redguard.send_task("*", "start", [])
    assert task.meta["cmd_type"] == "start"


@pytest.mark.asyncio
async def test_send_task_stats(redguard):
    redguard._client.get = AsyncMock(return_value=make_resp(200, {
        "total": 1000, "blocked": 200, "allowed": 800,
    }))
    task = await redguard.send_task("*", "stats", [])
    assert task.meta["cmd_type"] == "stats"


@pytest.mark.asyncio
async def test_send_task_reload(redguard):
    redguard._client.post = AsyncMock(return_value=make_resp(200, {}))
    task = await redguard.send_task("*", "reload", [])
    assert task.meta["cmd_type"] == "reload"


# ── Méthodes spécifiques ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_traffic_logs(redguard):
    redguard._client.get = AsyncMock(return_value=make_resp(200, {
        "logs": [{"remote_ip": "1.2.3.4", "method": "GET"}]
    }))
    logs = await redguard.get_traffic_logs()
    assert len(logs) == 1


@pytest.mark.asyncio
async def test_get_stats(redguard):
    redguard._client.get = AsyncMock(return_value=make_resp(200, {
        "total": 5000, "blocked": 1000,
    }))
    stats = await redguard.get_stats()
    assert stats["total"] == 5000


@pytest.mark.asyncio
async def test_add_to_blocklist(redguard):
    redguard._client.post = AsyncMock(return_value=make_resp(200, {}))
    result = await redguard.add_to_blocklist("1.2.3.4", reason="scanner")
    assert result is True


@pytest.mark.asyncio
async def test_add_to_allowlist(redguard):
    redguard._client.post = AsyncMock(return_value=make_resp(200, {}))
    result = await redguard.add_to_allowlist("10.0.0.5")
    assert result is True


@pytest.mark.asyncio
async def test_get_config(redguard):
    redguard._client.get = AsyncMock(return_value=make_resp(200, {
        "upstream": "https://c2:443", "profile": "strict",
    }))
    config = await redguard.get_config()
    assert config["profile"] == "strict"


@pytest.mark.asyncio
async def test_update_config(redguard):
    redguard._client.put = AsyncMock(return_value=make_resp(200, {}))
    result = await redguard.update_config({"sleep": 10})
    assert result is True


# ── Payload (config.ini) ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_generate_payload_config(redguard):
    redguard._client.get = AsyncMock(return_value=make_resp(200, {
        "upstream": "https://c2:443", "profile": "strict",
    }))
    payload_cfg = PayloadConfig(name="redguard-config", format="ini")
    payload = await redguard.generate_payload(payload_cfg)
    assert b"upstream" in payload or b"profile" in payload


# ── Guard ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_require_connected_guard(redguard):
    from c2_manager.interfaces import C2NotConnected
    redguard._status = C2Status.DISCONNECTED
    with pytest.raises(C2NotConnected):
        await redguard.list_listeners()
