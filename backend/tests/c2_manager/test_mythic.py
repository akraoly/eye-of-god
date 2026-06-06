"""Tests MythicC2 — GraphQL + JWT."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from c2_manager.integrations.mythic import MythicC2
from c2_manager.models import C2Config, C2Type, C2Status, PayloadConfig
from tests.c2_manager.conftest import make_resp


@pytest.fixture
def mythic():
    return MythicC2()


@pytest.fixture
def connected_mythic(mythic_config):
    m = MythicC2()
    m._config = mythic_config
    m._token  = "jwt_mythic_token"
    m._status = C2Status.CONNECTED
    m._operation_id = 1
    mock_client = AsyncMock()
    mock_client.get    = AsyncMock()
    mock_client.post   = AsyncMock()
    mock_client.delete = AsyncMock()
    mock_client.aclose = AsyncMock()
    m._client = mock_client
    return m


class TestMythicAuth:
    @pytest.mark.asyncio
    async def test_authenticate_success(self, mythic, mythic_config):
        gql_resp = make_resp(200, {
            "data": {
                "userLogin": {
                    "access_token":  "mythic-jwt-123",
                    "refresh_token": "refresh-abc",
                    "user": {
                        "id": 1,
                        "username": "mythic_admin",
                        "current_operation": {"id": 5, "name": "test-op"},
                    },
                }
            }
        })
        with patch("httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__ = AsyncMock(return_value=AsyncMock(
                post=AsyncMock(return_value=gql_resp)
            ))
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
            token = await mythic._authenticate(mythic_config)
        assert token == "mythic-jwt-123"
        assert mythic._operation_id == 5

    @pytest.mark.asyncio
    async def test_authenticate_graphql_error(self, mythic, mythic_config):
        from c2_manager.interfaces import C2AuthError
        err_resp = make_resp(200, {
            "errors": [{"message": "Invalid credentials"}]
        })
        with patch("httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__ = AsyncMock(return_value=AsyncMock(
                post=AsyncMock(return_value=err_resp)
            ))
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
            with pytest.raises(C2AuthError):
                await mythic._authenticate(mythic_config)


class TestMythicAgents:
    @pytest.mark.asyncio
    async def test_list_agents_empty(self, connected_mythic):
        gql_resp = make_resp(200, {"data": {"callback": []}})
        connected_mythic._client.post.return_value = gql_resp
        agents = await connected_mythic.list_agents()
        assert agents == []

    @pytest.mark.asyncio
    async def test_list_agents_with_callbacks(self, connected_mythic):
        gql_resp = make_resp(200, {"data": {"callback": [
            {
                "id":                42,
                "agent_callback_id": "abc123",
                "init_callback":     "2026-06-06T10:00:00Z",
                "last_checkin":      "2026-06-06T12:00:00Z",
                "user":              "DOMAIN\\victim",
                "host":              "WIN-VICTIM",
                "pid":               1337,
                "ip":                "192.168.1.100",
                "os":                "Windows 10 Enterprise",
                "architecture":      "x64",
                "integrity_level":   3,
                "process_name":      "explorer.exe",
                "registered_payload": {"payloadtype": {"name": "apollo"}},
                "callbackc2profiles": [{"c2profile": {"name": "http"}}],
            }
        ]}})
        connected_mythic._client.post.return_value = gql_resp
        agents = await connected_mythic.list_agents()
        assert len(agents) == 1
        a = agents[0]
        assert a.id        == "42"
        assert a.hostname  == "WIN-VICTIM"
        assert a.username  == "DOMAIN\\victim"
        assert a.integrity == "ADMIN"  # level 3


class TestMythicTasks:
    @pytest.mark.asyncio
    async def test_send_task(self, connected_mythic):
        gql_resp = make_resp(200, {"data": {"createTask": {"id": 77, "status": "submitted"}}})
        connected_mythic._client.post.return_value = gql_resp
        task = await connected_mythic.send_task("42", "shell", ["whoami"])
        assert task.id       == "77"
        assert task.agent_id == "42"
        assert task.command  == "shell"

    @pytest.mark.asyncio
    async def test_get_task_result(self, connected_mythic):
        gql_resp = make_resp(200, {"data": {"task": [{
            "id":        77,
            "status":    "completed",
            "completed": True,
            "command":   "shell",
            "params":    '{"command": "whoami"}',
            "responses": [{"id": 1, "response": "nt authority\\system", "timestamp": "2026-06-06T12:01:00Z"}],
        }]}})
        connected_mythic._client.post.return_value = gql_resp
        result = await connected_mythic.get_task_result("77")
        assert result["status"] == "completed"
        assert "nt authority\\system" in result["result"]


class TestMythicCapabilities:
    @pytest.mark.asyncio
    async def test_get_capabilities(self, mythic):
        caps = await mythic.get_capabilities()
        assert "list_agents" in caps
        assert "generate_payload" in caps
