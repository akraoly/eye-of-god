"""Tests FactionC2 — REST API + SignalR WebSocket."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from c2_manager.integrations.faction import FactionC2
from c2_manager.models import C2Config, C2Type, C2Status
from c2_manager.models.payload import PayloadConfig
from tests.c2_manager.conftest import make_resp


@pytest.fixture
def faction_config() -> C2Config:
    return C2Config(
        name="test-faction",
        c2_type=C2Type.FACTION,
        host="127.0.0.1",
        port=5000,
        ssl=False,
        username="admin",
        password="faction-pass",
        extra={"verify_ssl": False, "disable_ws": True},
    )


@pytest.fixture
def faction(faction_config):
    f = FactionC2()
    f._config = faction_config
    f._status = C2Status.CONNECTED
    f._client = AsyncMock()
    f._token  = "faction-jwt-token"
    return f


# ── Auth ──────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_authenticate_jwt(faction_config):
    c = FactionC2()
    mock_resp = make_resp(200, {"token": "jwt-abc"})
    with patch("httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__  = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_cls.return_value = mock_client
        # Bypass la connexion gRPC / REST en testant _authenticate
        token = await c._authenticate(faction_config)
    assert token == "jwt-abc"


@pytest.mark.asyncio
async def test_authenticate_access_token_field(faction_config):
    """Faction peut retourner access_token."""
    c = FactionC2()
    mock_resp = make_resp(200, {"access_token": "at-tok"})
    with patch("httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__  = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_cls.return_value = mock_client
        token = await c._authenticate(faction_config)
    assert token == "at-tok"


# ── Listeners ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_listener(faction):
    """Création transport + listener."""
    faction._client.post = AsyncMock(return_value=make_resp(201, {
        "id": "listener-1", "active": True,
    }))
    listener = await faction.create_listener({
        "protocol": "http",
        "bind_host": "0.0.0.0",
        "bind_port": 80,
        "name": "http-listener",
        "transport_id": "transport-1",
    })
    assert listener.id == "listener-1"
    assert listener.bind_port == 80


@pytest.mark.asyncio
async def test_create_listener_creates_transport(faction):
    """Sans transport_id → création automatique du transport."""
    faction._client.post = AsyncMock(
        side_effect=[
            make_resp(201, {"id": "transport-new"}),  # POST /api/transport
            make_resp(201, {"id": "listener-new", "active": True}),  # POST /api/listener
        ]
    )
    listener = await faction.create_listener({
        "protocol": "https",
        "bind_port": 443,
    })
    assert listener.id == "listener-new"


@pytest.mark.asyncio
async def test_list_listeners(faction):
    faction._client.get = AsyncMock(return_value=make_resp(200, [
        {"id": "l1", "name": "http-80", "host": "0.0.0.0", "port": 80,
         "protocol": "http", "active": True},
    ]))
    listeners = await faction.list_listeners()
    assert len(listeners) == 1
    assert listeners[0].status == "running"


@pytest.mark.asyncio
async def test_remove_listener(faction):
    faction._client.delete = AsyncMock(return_value=make_resp(204, {}))
    result = await faction.remove_listener("l1")
    assert result is True


# ── Agents ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_agents(faction):
    faction._client.get = AsyncMock(return_value=make_resp(200, [
        {
            "id": "agent-1",
            "hostname": "WIN-PC",
            "username": "alice",
            "ip": "10.0.0.5",
            "os": "Windows 10",
            "arch": "x64",
            "pid": 4567,
            "admin": True,
            "active": True,
            "last_seen": "2024-01-15T12:00:00",
            "listener_id": "l1",
        }
    ]))
    agents = await faction.list_agents()
    assert len(agents) == 1
    assert agents[0].hostname == "WIN-PC"
    assert agents[0].integrity == "ADMIN"


@pytest.mark.asyncio
async def test_parse_agent_user_integrity(faction):
    faction._client.get = AsyncMock(return_value=make_resp(200, [
        {"id": "agent-2", "hostname": "PC", "admin": False, "active": True,
         "last_seen": "2024-01-15T12:00:00"}
    ]))
    agents = await faction.list_agents()
    assert agents[0].integrity == "USER"


# ── Tasks ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_send_task_shell(faction):
    faction._client.post = AsyncMock(return_value=make_resp(201, {
        "id": "task-1", "status": "queued",
    }))
    task = await faction.send_task("agent-1", "shell whoami", [])
    assert task.id == "task-1"
    assert task.agent_id == "agent-1"


@pytest.mark.asyncio
async def test_send_task_module(faction):
    faction._client.post = AsyncMock(return_value=make_resp(201, {
        "id": "task-mod", "status": "queued",
    }))
    task = await faction.send_task("agent-1", "module recon.whoami", [])
    assert task.id == "task-mod"


@pytest.mark.asyncio
async def test_get_task_result(faction):
    faction._client.get = AsyncMock(return_value=make_resp(200, {
        "status": "completed", "output": "NT AUTHORITY\\SYSTEM",
    }))
    result = await faction.get_task_result("task-1")
    assert result["status"] == "completed"


# ── Modules ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_modules(faction):
    faction._client.get = AsyncMock(return_value=make_resp(200, [
        {"name": "recon.whoami", "description": "Get current user"},
        {"name": "exec.shell", "description": "Run shell command"},
    ]))
    modules = await faction.list_modules()
    assert len(modules) == 2


@pytest.mark.asyncio
async def test_run_module(faction):
    faction._client.post = AsyncMock(return_value=make_resp(201, {
        "id": "task-m1", "status": "queued",
    }))
    task = await faction.run_module("agent-1", "recon.whoami", {})
    assert task.meta["module"] == "recon.whoami"


# ── Payload ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_generate_payload(faction):
    import base64
    fake_exe = base64.b64encode(b"MZ\x90\x00fake").decode()
    faction._client.post = AsyncMock(return_value=make_resp(200, {"data": fake_exe}))
    payload_cfg = PayloadConfig(
        name="faction-agent",
        format="exe",
        arch="x64",
        os="windows",
    )
    payload = await faction.generate_payload(payload_cfg)
    assert payload[:2] == b"MZ"


# ── Guard ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_require_connected_guard(faction):
    from c2_manager.interfaces import C2NotConnected
    faction._status = C2Status.DISCONNECTED
    with pytest.raises(C2NotConnected):
        await faction.list_agents()
