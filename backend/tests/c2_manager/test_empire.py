"""Tests EmpireC2 — REST API v2."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

import pytest

from c2_manager.integrations.empire import EmpireC2
from c2_manager.models import C2Config, C2Type, PayloadConfig
from tests.c2_manager.conftest import make_resp


@pytest.fixture
def empire(empire_config):
    return EmpireC2()


@pytest.fixture
def connected_empire(empire_config):
    e = EmpireC2()
    e._config = empire_config
    e._token  = "test_jwt_token"
    e._status  = __import__('c2_manager.models', fromlist=['C2Status']).C2Status.CONNECTED
    mock_client = AsyncMock()
    mock_client.get    = AsyncMock()
    mock_client.post   = AsyncMock()
    mock_client.delete = AsyncMock()
    mock_client.aclose = AsyncMock()
    e._client = mock_client
    return e


class TestEmpireAuth:
    @pytest.mark.asyncio
    async def test_authenticate_success(self, empire, empire_config):
        token_resp = make_resp(200, {"access_token": "jwt123"})
        with patch("httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__ = AsyncMock(return_value=AsyncMock(
                post=AsyncMock(return_value=token_resp)
            ))
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
            token = await empire._authenticate(empire_config)
        assert token == "jwt123"

    @pytest.mark.asyncio
    async def test_authenticate_wrong_password(self, empire, empire_config):
        from c2_manager.interfaces import C2AuthError
        bad_resp = make_resp(401, {"detail": "Unauthorized"})
        with patch("httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__ = AsyncMock(return_value=AsyncMock(
                post=AsyncMock(return_value=bad_resp)
            ))
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
            with pytest.raises(C2AuthError):
                await empire._authenticate(empire_config)


class TestEmpireListeners:
    @pytest.mark.asyncio
    async def test_list_listeners_empty(self, connected_empire):
        connected_empire._client.get.return_value = make_resp(200, {"records": []})
        listeners = await connected_empire.list_listeners()
        assert listeners == []

    @pytest.mark.asyncio
    async def test_list_listeners_returns_items(self, connected_empire):
        connected_empire._client.get.return_value = make_resp(200, {"records": [
            {
                "id": 1,
                "name": "http-listener",
                "template": "http",
                "enabled": True,
                "options": {
                    "Port": {"value": "80"},
                    "BindIP": {"value": "0.0.0.0"},
                    "Host":   {"value": "http://0.0.0.0:80"},
                }
            }
        ]})
        listeners = await connected_empire.list_listeners()
        assert len(listeners) == 1
        assert listeners[0].name == "http-listener"
        assert listeners[0].protocol == "http"

    @pytest.mark.asyncio
    async def test_create_listener(self, connected_empire):
        connected_empire._client.post.return_value = make_resp(201, {
            "id": 42, "name": "my-http", "enabled": True
        })
        listener = await connected_empire.create_listener({
            "name": "my-http", "protocol": "http", "bind_port": 8080
        })
        assert listener.id == "42"
        assert listener.status == "running"

    @pytest.mark.asyncio
    async def test_remove_listener(self, connected_empire):
        connected_empire._client.delete.return_value = make_resp(200, {"result": "success"})
        ok = await connected_empire.remove_listener("42")
        assert ok


class TestEmpireAgents:
    @pytest.mark.asyncio
    async def test_list_agents_empty(self, connected_empire):
        connected_empire._client.get.return_value = make_resp(200, {"records": []})
        agents = await connected_empire.list_agents()
        assert agents == []

    @pytest.mark.asyncio
    async def test_list_agents_parses_fields(self, connected_empire):
        connected_empire._client.get.return_value = make_resp(200, {"records": [
            {
                "name":          "ABCD1234",
                "hostname":      "WIN-TARGET",
                "username":      "DOMAIN\\jdoe",
                "internal_ip":   "192.168.1.50",
                "external_ip":   "1.2.3.4",
                "os_details":    "Windows 10",
                "architecture":  "x64",
                "process_id":    1337,
                "process_name":  "powershell.exe",
                "high_integrity": True,
                "lastseen_time": "2026-06-06T12:00:00",
                "listener":      "http-listener",
                "stale":         False,
            }
        ]})
        agents = await connected_empire.list_agents()
        assert len(agents) == 1
        a = agents[0]
        assert a.hostname == "WIN-TARGET"
        assert a.username == "DOMAIN\\jdoe"
        assert a.arch == "x64"
        assert a.active


class TestEmpireTasks:
    @pytest.mark.asyncio
    async def test_send_shell_task(self, connected_empire):
        connected_empire._client.post.return_value = make_resp(201, {
            "id": 99, "status": "sent"
        })
        task = await connected_empire.send_task("ABCD1234", "whoami")
        assert task.command == "whoami"
        assert task.status == "sent"

    @pytest.mark.asyncio
    async def test_send_task_with_args(self, connected_empire):
        connected_empire._client.post.return_value = make_resp(201, {
            "id": 100, "status": "sent"
        })
        task = await connected_empire.send_task("ABCD1234", "shell", ["dir", "C:\\"])
        assert "dir" in task.command


class TestEmpirePayload:
    @pytest.mark.asyncio
    async def test_generate_powershell_stager(self, connected_empire):
        connected_empire._client.post.return_value = make_resp(200, {
            "output": "IEX(New-Object Net.WebClient)..."
        })
        cfg = PayloadConfig(
            name="test-stager",
            c2_type=C2Type.EMPIRE,
            listener_id="http-listener",
            format="ps1",
        )
        payload = await connected_empire.generate_payload(cfg)
        assert len(payload) > 0
