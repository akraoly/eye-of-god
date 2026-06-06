"""Tests PupyC2 — REST API web (mode --web, port 1337)."""
from __future__ import annotations

import base64
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from c2_manager.integrations.pupy import PupyC2
from c2_manager.models import C2Config, C2Type, C2Status
from c2_manager.models.payload import PayloadConfig
from tests.c2_manager.conftest import make_resp


@pytest.fixture
def pupy_config() -> C2Config:
    return C2Config(
        name="test-pupy",
        c2_type=C2Type.PUPY,
        host="127.0.0.1",
        port=1337,
        ssl=False,
        username="admin",
        password="pupy-pass",
        extra={"api_port": 1337, "verify_ssl": False},
    )


@pytest.fixture
def pupy(pupy_config):
    p = PupyC2()
    p._config       = pupy_config
    p._status       = C2Status.CONNECTED
    p._rest_client  = AsyncMock()
    p._jwt_token    = "pupy-jwt"
    return p


# ── Connexion ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_connect_jwt(pupy_config):
    p = PupyC2()
    mock_resp = make_resp(200, {"token": "pupy-tok"})
    with patch("httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_cls.return_value = mock_client
        result = await p.connect(pupy_config)
    assert result is True
    assert p._jwt_token == "pupy-tok"
    assert p._status == C2Status.CONNECTED


@pytest.mark.asyncio
async def test_connect_api_key(pupy_config):
    pupy_config.extra["api_key"] = "static-pupy-key"
    p = PupyC2()
    with patch("httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value = mock_client
        result = await p.connect(pupy_config)
    assert result is True
    assert p._jwt_token == "static-pupy-key"


@pytest.mark.asyncio
async def test_connect_auth_failure(pupy_config):
    from c2_manager.interfaces import C2AuthError
    p = PupyC2()
    mock_resp = make_resp(401, {"error": "unauthorized"})
    mock_resp.status_code = 401
    with patch("httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_cls.return_value = mock_client
        with pytest.raises(C2AuthError):
            await p.connect(pupy_config)


@pytest.mark.asyncio
async def test_connect_missing_token(pupy_config):
    from c2_manager.interfaces import C2AuthError
    p = PupyC2()
    mock_resp = make_resp(200, {"other_field": "no-token"})
    with patch("httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_cls.return_value = mock_client
        with pytest.raises(C2AuthError):
            await p.connect(pupy_config)


# ── Listeners ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_listener_ssl(pupy):
    pupy._rest_client.post = AsyncMock(return_value=make_resp(201, {
        "id": "l-1", "active": True,
    }))
    listener = await pupy.create_listener({
        "transport": "ssl",
        "bind_host": "0.0.0.0",
        "bind_port": 443,
        "name": "ssl-listener",
    })
    assert listener.id == "l-1"
    assert listener.protocol == "ssl"


@pytest.mark.asyncio
async def test_create_listener_dns(pupy):
    pupy._rest_client.post = AsyncMock(return_value=make_resp(201, {
        "id": "l-dns", "active": True,
    }))
    listener = await pupy.create_listener({
        "transport": "dnscnc",
        "bind_port": 53,
        "dns_domain": "c2.evil.com",
    })
    assert listener.protocol == "dnscnc"


@pytest.mark.asyncio
async def test_list_listeners(pupy):
    pupy._rest_client.get = AsyncMock(return_value=make_resp(200, {
        "listeners": [
            {"id": "l1", "name": "ssl-443", "host": "0.0.0.0",
             "port": 443, "transport": "ssl", "active": True},
        ]
    }))
    listeners = await pupy.list_listeners()
    assert len(listeners) == 1
    assert listeners[0].protocol == "ssl"


@pytest.mark.asyncio
async def test_remove_listener(pupy):
    pupy._rest_client.delete = AsyncMock(return_value=MagicMock(raise_for_status=MagicMock()))
    result = await pupy.remove_listener("l1")
    assert result is True


# ── Sessions (agents) ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_agents(pupy):
    pupy._rest_client.get = AsyncMock(return_value=make_resp(200, {
        "sessions": [
            {
                "id": "s1",
                "hostname": "linux-box",
                "user": "root",
                "ip": "10.0.0.5",
                "local_ip": "192.168.1.5",
                "os": "Linux",
                "arch": "x64",
                "pid": 1234,
                "process": "python3",
                "transport": "ssl",
                "is_root": True,
                "dead": False,
                "last_seen": "2024-01-15T12:00:00",
                "connected_at": "2024-01-15T10:00:00",
                "loaded_modules": ["pupyutils", "shell"],
            }
        ]
    }))
    agents = await pupy.list_agents()
    assert len(agents) == 1
    assert agents[0].hostname == "linux-box"
    assert agents[0].integrity == "SYSTEM"


@pytest.mark.asyncio
async def test_parse_session_non_root(pupy):
    pupy._rest_client.get = AsyncMock(return_value=make_resp(200, {
        "sessions": [
            {"id": "s2", "hostname": "pc", "user": "alice", "is_root": False,
             "dead": False, "last_seen": "2024-01-15T12:00:00",
             "connected_at": "2024-01-15T10:00:00"}
        ]
    }))
    agents = await pupy.list_agents()
    assert agents[0].integrity == "USER"


# ── Commandes ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_send_task_shell(pupy):
    pupy._rest_client.post = AsyncMock(return_value=make_resp(201, {
        "id": "t1", "status": "queued",
    }))
    task = await pupy.send_task("s1", "shell id", [])
    assert task.id == "t1"
    assert task.meta["module"] == "shell"


@pytest.mark.asyncio
async def test_send_task_screenshot(pupy):
    pupy._rest_client.post = AsyncMock(return_value=make_resp(201, {
        "id": "t2", "status": "queued",
    }))
    task = await pupy.send_task("s1", "screenshot", [])
    assert task.meta["module"] == "screenshot"


@pytest.mark.asyncio
async def test_send_task_keylogger(pupy):
    pupy._rest_client.post = AsyncMock(return_value=make_resp(201, {
        "id": "t3", "status": "queued",
    }))
    task = await pupy.send_task("s1", "keylog", [])
    assert task.meta["module"] == "keylogger"


@pytest.mark.asyncio
async def test_send_task_persistence(pupy):
    pupy._rest_client.post = AsyncMock(return_value=make_resp(201, {
        "id": "t4", "status": "queued",
    }))
    task = await pupy.send_task("s1", "persistence", [])
    assert task.id == "t4"


@pytest.mark.asyncio
async def test_get_task_result(pupy):
    pupy._rest_client.get = AsyncMock(return_value=make_resp(200, {
        "status": "completed", "output": "uid=0(root)",
    }))
    result = await pupy.get_task_result("t1")
    assert result["status"] == "completed"


# ── Modules ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_modules(pupy):
    pupy._rest_client.get = AsyncMock(return_value=make_resp(200, {
        "modules": [
            {"name": "pupyutils.shell", "category": "exec",
             "description": "Run shell commands", "platform": ["linux", "windows"]},
        ]
    }))
    modules = await pupy.list_modules()
    assert len(modules) == 1
    assert modules[0]["name"] == "pupyutils.shell"


@pytest.mark.asyncio
async def test_run_module(pupy):
    pupy._rest_client.post = AsyncMock(return_value=make_resp(201, {
        "id": "t-mod", "status": "queued",
    }))
    task = await pupy.run_module("s1", "pupyutils.shell", {"cmd": "id"})
    assert task.meta["module"] == "pupyutils.shell"


# ── Payload ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_generate_payload_exe(pupy):
    fake_exe = base64.b64encode(b"MZ\x90\x00fake-pupy").decode()
    pupy._rest_client.post = AsyncMock(return_value=make_resp(200, {"data": fake_exe}))
    payload_cfg = PayloadConfig(
        name="pupy-win",
        format="exe",
        os="windows",
        arch="x64",
        extra={"listener_id": "l1"},
    )
    payload = await pupy.generate_payload(payload_cfg)
    assert payload[:2] == b"MZ"


@pytest.mark.asyncio
async def test_generate_payload_py(pupy):
    fake_py = base64.b64encode(b"#!/usr/bin/env python3\n# pupy agent").decode()
    pupy._rest_client.post = AsyncMock(return_value=make_resp(200, {"data": fake_py}))
    payload_cfg = PayloadConfig(
        name="pupy-linux",
        format="py",
        os="linux",
        arch="x64",
    )
    payload = await pupy.generate_payload(payload_cfg)
    assert b"python" in payload or b"pupy" in payload


# ── Guard ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_require_connected_guard(pupy):
    from c2_manager.interfaces import C2NotConnected
    pupy._status = C2Status.DISCONNECTED
    with pytest.raises(C2NotConnected):
        await pupy.list_agents()
