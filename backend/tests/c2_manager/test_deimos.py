"""Tests DeimosC2 — gRPC mTLS + REST API management."""
from __future__ import annotations

import base64
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from c2_manager.integrations.deimos import DeimosC2
from c2_manager.models import C2Config, C2Type, C2Status
from c2_manager.models.payload import PayloadConfig
from tests.c2_manager.conftest import make_resp


@pytest.fixture
def deimos_config() -> C2Config:
    return C2Config(
        name="test-deimos",
        c2_type=C2Type.DEIMOS,
        host="127.0.0.1",
        port=8443,
        ssl=True,
        username="admin",
        password="deimos123",
        extra={"mode": "rest", "web_port": 8443, "verify_ssl": False},
    )


@pytest.fixture
def deimos(deimos_config):
    d = DeimosC2()
    d._config       = deimos_config
    d._status       = C2Status.CONNECTED
    d._mode         = "rest"
    d._rest_client  = AsyncMock()
    d._jwt_token    = "deimos-jwt"
    return d


def make_rest_resp(data: dict, status: int = 200):
    resp = MagicMock()
    resp.status_code = status
    resp.json = MagicMock(return_value=data)
    resp.raise_for_status = MagicMock()
    return resp


# ── Connexion REST ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_connect_rest(deimos_config):
    d = DeimosC2()
    mock_resp = make_resp(200, {"token": "jwt-abc"})
    with patch("httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_cls.return_value = mock_client
        result = await d._connect_rest(deimos_config)
    assert result is True
    assert d._status == C2Status.CONNECTED
    assert d._jwt_token == "jwt-abc"


@pytest.mark.asyncio
async def test_connect_rest_auth_failure(deimos_config):
    from c2_manager.interfaces import C2AuthError
    d = DeimosC2()
    mock_resp = make_resp(401, {"error": "unauthorized"})
    mock_resp.status_code = 401
    with patch("httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_cls.return_value = mock_client
        with pytest.raises(C2AuthError):
            await d._connect_rest(deimos_config)


@pytest.mark.asyncio
async def test_connect_grpc_falls_back_to_rest(deimos_config):
    """Sans proto stubs → fallback REST."""
    deimos_config.extra["mode"] = "grpc"
    deimos_config.extra["ca_cert"]     = base64.b64encode(b"fake-ca").decode()
    deimos_config.extra["client_cert"] = base64.b64encode(b"fake-cert").decode()
    deimos_config.extra["client_key"]  = base64.b64encode(b"fake-key").decode()
    d = DeimosC2()
    mock_channel = AsyncMock()
    mock_channel.close = AsyncMock()

    with patch.object(d, "_build_grpc_channel", return_value=mock_channel), \
         patch.object(d, "_connect_rest", return_value=True) as mock_rest:
        # grpc_pb2 import échoue → fallback REST
        result = await d._connect_grpc(deimos_config)
    mock_rest.assert_called_once()


# ── Helpers REST ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_rest_get(deimos):
    deimos._rest_client.get = AsyncMock(return_value=make_rest_resp({"data": "ok"}))
    resp = await deimos._rest_get("/api/v1/agents")
    assert resp["data"] == "ok"


@pytest.mark.asyncio
async def test_rest_post(deimos):
    deimos._rest_client.post = AsyncMock(return_value=make_rest_resp({"id": "new-1"}))
    resp = await deimos._rest_post("/api/v1/listeners", json={"type": "https"})
    assert resp["id"] == "new-1"


# ── Listeners ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_listener_https(deimos):
    deimos._rest_client.post = AsyncMock(return_value=make_rest_resp({
        "id": "l-1", "active": True,
    }))
    listener = await deimos.create_listener({
        "protocol": "https",
        "bind_host": "0.0.0.0",
        "bind_port": 443,
        "name": "deimos-https",
        "sleep": 5,
        "jitter": 10,
    })
    assert listener.id == "l-1"
    assert listener.protocol == "https"


@pytest.mark.asyncio
async def test_create_listener_smb(deimos):
    deimos._rest_client.post = AsyncMock(return_value=make_rest_resp({
        "id": "l-smb", "active": True,
    }))
    listener = await deimos.create_listener({
        "protocol": "smb",
        "name": "smb-pivot",
    })
    assert listener.id == "l-smb"


@pytest.mark.asyncio
async def test_list_listeners(deimos):
    deimos._rest_client.get = AsyncMock(return_value=make_rest_resp({
        "listeners": [
            {"id": "l1", "name": "https-443", "host": "0.0.0.0",
             "port": 443, "type": "https", "active": True},
        ]
    }))
    listeners = await deimos.list_listeners()
    assert len(listeners) == 1
    assert listeners[0].protocol == "https"


@pytest.mark.asyncio
async def test_remove_listener(deimos):
    deimos._rest_client.delete = AsyncMock(return_value=MagicMock(raise_for_status=MagicMock()))
    result = await deimos.remove_listener("l-1")
    assert result is True


@pytest.mark.asyncio
async def test_remove_listener_error(deimos):
    deimos._rest_client.delete = AsyncMock(side_effect=Exception("404"))
    result = await deimos.remove_listener("inexistant")
    assert result is False


# ── Agents ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_agents(deimos):
    deimos._rest_client.get = AsyncMock(return_value=make_rest_resp({
        "agents": [
            {
                "id": "a1",
                "hostname": "WIN10-PC",
                "username": "alice",
                "external_ip": "8.8.8.8",
                "internal_ip": "192.168.1.5",
                "os": "Windows 10",
                "arch": "x64",
                "pid": 4567,
                "process": "notepad.exe",
                "privilege": "Medium",
                "listener_id": "l1",
                "last_checkin": "2024-01-15T12:00:00Z",
                "created_at":  "2024-01-15T10:00:00Z",
                "dead": False,
                "sleep": 5,
                "jitter": 0,
            }
        ]
    }))
    agents = await deimos.list_agents()
    assert len(agents) == 1
    assert agents[0].hostname == "WIN10-PC"
    assert agents[0].integrity == "USER"


@pytest.mark.asyncio
async def test_parse_agent_system_integrity(deimos):
    deimos._rest_client.get = AsyncMock(return_value=make_rest_resp({
        "agents": [
            {"id": "a2", "hostname": "DC01", "privilege": "SYSTEM",
             "last_checkin": "2024-01-15T12:00:00Z",
             "created_at": "2024-01-15T10:00:00Z", "dead": False}
        ]
    }))
    agents = await deimos.list_agents()
    assert agents[0].integrity == "SYSTEM"


@pytest.mark.asyncio
async def test_parse_agent_admin_integrity(deimos):
    deimos._rest_client.get = AsyncMock(return_value=make_rest_resp({
        "agents": [
            {"id": "a3", "hostname": "SRV", "privilege": "High",
             "last_checkin": "2024-01-15T12:00:00Z",
             "created_at": "2024-01-15T10:00:00Z", "dead": False}
        ]
    }))
    agents = await deimos.list_agents()
    assert agents[0].integrity == "ADMIN"


# ── Tâches ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_send_task_shell(deimos):
    deimos._rest_client.post = AsyncMock(return_value=make_rest_resp({
        "id": "t1", "status": "queued",
    }))
    task = await deimos.send_task("a1", "shell whoami", [])
    assert task.id == "t1"
    assert task.meta["task_type"] == "shell"


@pytest.mark.asyncio
async def test_send_task_powershell(deimos):
    deimos._rest_client.post = AsyncMock(return_value=make_rest_resp({
        "id": "t2", "status": "queued",
    }))
    task = await deimos.send_task("a1", "ps Get-Process", [])
    assert task.meta["task_type"] == "powershell"


@pytest.mark.asyncio
async def test_send_task_screenshot(deimos):
    deimos._rest_client.post = AsyncMock(return_value=make_rest_resp({
        "id": "t3", "status": "queued",
    }))
    task = await deimos.send_task("a1", "screenshot", [])
    assert task.meta["task_type"] == "screenshot"


@pytest.mark.asyncio
async def test_send_task_sleep(deimos):
    deimos._rest_client.post = AsyncMock(return_value=make_rest_resp({
        "id": "t4", "status": "queued",
    }))
    task = await deimos.send_task("a1", "sleep 30", [])
    assert task.meta["task_type"] == "sleep"


@pytest.mark.asyncio
async def test_get_task_result(deimos):
    deimos._rest_client.get = AsyncMock(return_value=make_rest_resp({
        "status": "completed", "output": "admin",
    }))
    result = await deimos.get_task_result("t1")
    assert result["status"] == "completed"


# ── Payload ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_generate_payload(deimos):
    fake_exe = base64.b64encode(b"MZ\x90\x00fake-deimos").decode()
    deimos._rest_client.post = AsyncMock(return_value=make_rest_resp({"data": fake_exe}))
    payload_cfg = PayloadConfig(
        name="deimos-implant",
        format="exe",
        arch="x64",
        os="windows",
        extra={"listener_id": "l1"},
    )
    payload = await deimos.generate_payload(payload_cfg)
    assert payload[:2] == b"MZ"


# ── Guard ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_require_connected_guard(deimos):
    from c2_manager.interfaces import C2NotConnected
    deimos._status = C2Status.DISCONNECTED
    with pytest.raises(C2NotConnected):
        await deimos.list_agents()
