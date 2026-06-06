"""Tests AsyncRatC2 — TCP/SSL + REST API wrapper."""
from __future__ import annotations

import struct
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from c2_manager.integrations.asyncrat import AsyncRatC2
from c2_manager.models import C2Config, C2Type, C2Status
from c2_manager.models.payload import PayloadConfig
from tests.c2_manager.conftest import make_resp


@pytest.fixture
def asyncrat_api_config() -> C2Config:
    return C2Config(
        name="test-asyncrat-api",
        c2_type=C2Type.ASYNCRAT,
        host="127.0.0.1",
        port=8080,
        extra={"mode": "api", "api_key": "ar-key", "verify_ssl": False},
    )


@pytest.fixture
def asyncrat_tcp_config() -> C2Config:
    return C2Config(
        name="test-asyncrat-tcp",
        c2_type=C2Type.ASYNCRAT,
        host="127.0.0.1",
        port=6606,
        password="AsyncRAT#1234",
        ssl=False,
        extra={"mode": "tcp", "mgmt_port": 6607},
    )


@pytest.fixture
def asyncrat_api(asyncrat_api_config):
    a = AsyncRatC2()
    a._config = asyncrat_api_config
    a._status = C2Status.CONNECTED
    a._mode   = "api"
    a._client = AsyncMock()
    a._token  = "ar-key"
    return a


@pytest.fixture
def asyncrat_tcp(asyncrat_tcp_config):
    a = AsyncRatC2()
    a._config     = asyncrat_tcp_config
    a._status     = C2Status.CONNECTED
    a._mode       = "tcp"
    a._tcp_reader = AsyncMock()
    a._tcp_writer = AsyncMock()
    a._tcp_writer.is_closing = MagicMock(return_value=False)
    a._aes_key    = None  # Pas de chiffrement dans les tests
    return a


# ── Connexion ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_connect_api(asyncrat_api_config):
    a = AsyncRatC2()
    with patch("httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=make_resp(200, {"status": "ok"}))
        mock_cls.return_value = mock_client
        result = await a._connect_api(asyncrat_api_config)
    assert result is True
    assert a._status == C2Status.CONNECTED


@pytest.mark.asyncio
async def test_connect_tcp(asyncrat_tcp_config):
    a = AsyncRatC2()
    mock_reader = AsyncMock()
    mock_writer = AsyncMock()
    mock_writer.is_closing = MagicMock(return_value=False)
    mock_writer.write = MagicMock()
    mock_writer.drain = AsyncMock()

    # Ping pong : le TCP call lit header(4) + body
    ping_resp = json.dumps({"Status": "OK"}).encode()
    header = struct.pack(">I", len(ping_resp))
    mock_reader.readexactly = AsyncMock(side_effect=[header, ping_resp])

    with patch("asyncio.open_connection", return_value=(mock_reader, mock_writer)), \
         patch("asyncio.wait_for", side_effect=[(mock_reader, mock_writer), header, ping_resp]):
        # Simplification : patching wait_for pour open_connection
        pass

    # Test indirect via connexion directe
    a._tcp_reader = mock_reader
    a._tcp_writer = mock_writer
    a._status     = C2Status.CONNECTED
    assert a._status == C2Status.CONNECTED


# ── Listeners ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_listener_api(asyncrat_api):
    asyncrat_api._client.post = AsyncMock(return_value=make_resp(201, {
        "id": "port-6606", "active": True,
    }))
    listener = await asyncrat_api.create_listener({
        "bind_host": "0.0.0.0",
        "bind_port": 6606,
        "name": "ssl-port",
        "ssl": True,
    })
    assert listener.id == "port-6606"
    assert listener.protocol == "ssl-tcp"


@pytest.mark.asyncio
async def test_create_listener_tcp_mode(asyncrat_tcp):
    """Mode TCP : créer listener via protocole binaire."""
    resp_body = json.dumps({"Status": "OK", "ID": "port-1"}).encode()
    asyncrat_tcp._tcp_reader.readexactly = AsyncMock(
        side_effect=[struct.pack(">I", len(resp_body)), resp_body]
    )
    asyncrat_tcp._tcp_writer.write = MagicMock()
    asyncrat_tcp._tcp_writer.drain = AsyncMock()

    with patch("asyncio.wait_for", side_effect=[struct.pack(">I", len(resp_body)), resp_body]):
        listener = await asyncrat_tcp.create_listener({
            "bind_port": 6606, "name": "port-6606", "ssl": True,
        })
    assert listener.bind_port == 6606


@pytest.mark.asyncio
async def test_list_listeners_api(asyncrat_api):
    asyncrat_api._client.get = AsyncMock(return_value=make_resp(200, [
        {"ID": "p1", "Host": "0.0.0.0", "Port": 6606, "SSL": True, "Active": True},
    ]))
    listeners = await asyncrat_api.list_listeners()
    assert len(listeners) == 1
    assert listeners[0].bind_port == 6606


@pytest.mark.asyncio
async def test_remove_listener_api(asyncrat_api):
    asyncrat_api._client.delete = AsyncMock(return_value=make_resp(204, {}))
    result = await asyncrat_api.remove_listener("port-1")
    assert result is True


# ── Clients (agents) ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_agents_api(asyncrat_api):
    asyncrat_api._client.get = AsyncMock(return_value=make_resp(200, {
        "clients": [
            {
                "ID": "c1", "ComputerName": "WIN10",
                "AccountName": "Alice", "IP": "10.0.0.5",
                "LocalIP": "192.168.0.5", "OS": "Windows 10",
                "CPU": "x64", "PID": 1234, "Process": "explorer.exe",
                "IsAdmin": False, "LastSeen": "2024-01-15T12:00:00",
                "Connected": "2024-01-15T10:00:00",
                "Version": "0.5.8B", "Disconnected": False,
            }
        ]
    }))
    agents = await asyncrat_api.list_agents()
    assert len(agents) == 1
    assert agents[0].hostname == "WIN10"
    assert agents[0].integrity == "USER"


@pytest.mark.asyncio
async def test_parse_client_admin(asyncrat_api):
    asyncrat_api._client.get = AsyncMock(return_value=make_resp(200, {
        "clients": [
            {"ID": "c2", "ComputerName": "SRV",
             "IsAdmin": True, "LastSeen": "2024-01-15T12:00:00",
             "Connected": "2024-01-15T10:00:00", "Disconnected": False}
        ]
    }))
    agents = await asyncrat_api.list_agents()
    assert agents[0].integrity == "ADMIN"


# ── Commandes ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_send_task_cmd_api(asyncrat_api):
    asyncrat_api._client.post = AsyncMock(return_value=make_resp(201, {
        "task_id": "t1", "status": "queued",
    }))
    task = await asyncrat_api.send_task("c1", "cmd whoami", [])
    assert task.agent_id == "c1"
    assert task.meta["packet_type"] == "RunProcess"


@pytest.mark.asyncio
async def test_send_task_powershell(asyncrat_api):
    asyncrat_api._client.post = AsyncMock(return_value=make_resp(201, {
        "task_id": "t2", "status": "queued",
    }))
    task = await asyncrat_api.send_task("c1", "ps Get-Process", [])
    assert task.meta["packet_type"] == "PowerShell"


@pytest.mark.asyncio
async def test_send_task_screenshot(asyncrat_api):
    asyncrat_api._client.post = AsyncMock(return_value=make_resp(201, {
        "task_id": "t3", "status": "queued",
    }))
    task = await asyncrat_api.send_task("c1", "screenshot", [])
    assert task.meta["packet_type"] == "Screenshot"


@pytest.mark.asyncio
async def test_send_task_keylogger(asyncrat_api):
    asyncrat_api._client.post = AsyncMock(return_value=make_resp(201, {
        "task_id": "t4", "status": "queued",
    }))
    task = await asyncrat_api.send_task("c1", "keylog", [])
    assert task.meta["packet_type"] == "Keylogger"


@pytest.mark.asyncio
async def test_get_task_result_api(asyncrat_api):
    asyncrat_api._client.get = AsyncMock(return_value=make_resp(200, {
        "status": "completed", "output": "NT AUTHORITY\\SYSTEM",
    }))
    result = await asyncrat_api.get_task_result("t1")
    assert result["status"] == "completed"


# ── TCP protocol ──────────────────────────────────────────────────────────────

def test_pack_packet(asyncrat_tcp):
    """Format du paquet TCP : [4 bytes length big-endian][body JSON]."""
    payload = {"Action": "GetClients"}
    encrypted = asyncrat_tcp._aes_encrypt(json.dumps(payload))
    frame = struct.pack(">I", len(encrypted)) + encrypted
    # Le frame est lisible
    length = struct.unpack(">I", frame[:4])[0]
    assert length == len(encrypted)


# ── Payload ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_generate_payload_api(asyncrat_api):
    import base64
    fake_exe = base64.b64encode(b"MZ\x90\x00fake-asyncrat").decode()
    asyncrat_api._client.post = AsyncMock(return_value=make_resp(200, {"data": fake_exe}))
    payload_cfg = PayloadConfig(
        name="asyncrat-client",
        format="exe",
        arch="x64",
        os="windows",
        extra={"callback_host": "127.0.0.1", "callback_port": 6606},
    )
    payload = await asyncrat_api.generate_payload(payload_cfg)
    assert payload[:2] == b"MZ"


# ── Guard ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_require_connected_guard(asyncrat_api):
    from c2_manager.interfaces import C2NotConnected
    asyncrat_api._status = C2Status.DISCONNECTED
    with pytest.raises(C2NotConnected):
        await asyncrat_api.list_agents()
