"""Tests HavocC2 — WebSocket operator protocol + REST API."""
from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest

from c2_manager.integrations.havoc import HavocC2, _T_LOGIN, _T_AGENT_LIST, _T_LISTENER_LIST
from c2_manager.models import C2Config, C2Type, C2Status
from c2_manager.models.payload import PayloadConfig
from tests.c2_manager.conftest import make_resp


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def havoc_ws_config() -> C2Config:
    return C2Config(
        name="test-havoc-ws",
        c2_type=C2Type.HAVOC,
        host="127.0.0.1",
        port=40056,
        username="neo",
        password="havoc123",
        ssl=False,
        extra={"mode": "websocket"},
    )


@pytest.fixture
def havoc_rest_config() -> C2Config:
    return C2Config(
        name="test-havoc-rest",
        c2_type=C2Type.HAVOC,
        host="127.0.0.1",
        port=40056,
        username="admin",
        password="admin123",
        ssl=False,
        extra={"mode": "rest"},
    )


@pytest.fixture
def havoc_ws(havoc_ws_config):
    h = HavocC2()
    h._config  = havoc_ws_config
    h._mode    = "websocket"
    h._status  = C2Status.CONNECTED
    return h


@pytest.fixture
def havoc_rest(havoc_rest_config):
    h = HavocC2()
    h._config  = havoc_rest_config
    h._mode    = "rest"
    h._status  = C2Status.CONNECTED
    h._client  = AsyncMock()
    h._token   = "fake-rest-token"
    return h


def _mock_ws_resp(msg_type: str, body: dict) -> str:
    return json.dumps({"Type": msg_type, "Body": body})


# ── Tests connexion WebSocket ────────────────────────────────────────────────

class TestHavocWSConnect:
    @pytest.mark.asyncio
    async def test_connect_ws_success(self, havoc_ws_config):
        h = HavocC2()
        mock_ws = AsyncMock()
        # Réponse auth OK
        mock_ws.recv = AsyncMock(return_value=json.dumps({"Type": "login/ok", "Body": {}}))
        mock_ws.send = AsyncMock()
        mock_ws.close = AsyncMock()

        with patch("c2_manager.integrations.havoc.asyncio.wait_for", return_value=mock_ws), \
             patch("asyncio.create_task"):
            result = await h._connect_ws(havoc_ws_config)

        assert result is True
        assert h._ws is mock_ws

    @pytest.mark.asyncio
    async def test_connect_ws_auth_failure(self, havoc_ws_config):
        from c2_manager.interfaces import C2AuthError
        h = HavocC2()
        mock_ws = AsyncMock()
        mock_ws.send = AsyncMock()
        auth_error_resp = {"Type": "login/error", "Body": {"message": "bad creds"}}

        # wait_for est appelé 2x : (1) connexion WS → mock_ws, (2) _ws_recv → réponse erreur
        with patch("c2_manager.integrations.havoc.asyncio.wait_for") as mock_wait:
            mock_wait.side_effect = [mock_ws, auth_error_resp]
            with pytest.raises(C2AuthError):
                await h._connect_ws(havoc_ws_config)

    @pytest.mark.asyncio
    async def test_connect_ws_no_websockets(self, havoc_ws_config):
        from c2_manager.interfaces import C2ConnectionError
        h = HavocC2()
        with patch("builtins.__import__", side_effect=ImportError("websockets")):
            with pytest.raises((C2ConnectionError, ImportError)):
                await h._connect_ws(havoc_ws_config)


# ── Tests connexion REST ──────────────────────────────────────────────────────

class TestHavocRESTConnect:
    @pytest.mark.asyncio
    async def test_authenticate_rest_success(self, havoc_rest_config):
        h = HavocC2()
        mock_resp = make_resp(200, {"token": "abc-token-xyz"})

        with patch("httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__  = AsyncMock(return_value=False)
            mock_client.post       = AsyncMock(return_value=mock_resp)
            mock_cls.return_value  = mock_client

            token = await h._authenticate(havoc_rest_config)

        assert token == "abc-token-xyz"

    @pytest.mark.asyncio
    async def test_authenticate_rest_failure(self, havoc_rest_config):
        from c2_manager.interfaces import C2AuthError
        h = HavocC2()
        mock_resp = make_resp(401, {"error": "unauthorized"})
        mock_resp.json = MagicMock(return_value={"error": "unauthorized"})

        with patch("httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__  = AsyncMock(return_value=False)
            mock_client.post       = AsyncMock(return_value=mock_resp)
            mock_cls.return_value  = mock_client

            with pytest.raises(C2AuthError):
                await h._authenticate(havoc_rest_config)


# ── Tests list_listeners ─────────────────────────────────────────────────────

class TestHavocListeners:
    @pytest.mark.asyncio
    async def test_list_listeners_ws(self, havoc_ws):
        listeners_data = [
            {"ListenerID": "l1", "Name": "http-80", "Protocol": "HTTP",
             "Host": "0.0.0.0", "Port": 80, "Status": "running"},
            {"ListenerID": "l2", "Name": "https-443", "Protocol": "HTTPS",
             "Host": "0.0.0.0", "Port": 443, "Status": "running"},
        ]
        havoc_ws._ws_request = AsyncMock(
            return_value={"Type": "listener/list", "Body": {"Listeners": listeners_data}}
        )

        result = await havoc_ws.list_listeners()
        assert len(result) == 2
        assert result[0].id == "l1"
        assert result[0].name == "http-80"
        assert result[0].protocol == "http"
        assert result[0].status == "running"
        assert result[1].bind_port == 443

    @pytest.mark.asyncio
    async def test_list_listeners_rest(self, havoc_rest):
        mock_resp = make_resp(200, {"listeners": [
            {"id": "r1", "name": "beacon-80", "type": "http",
             "host": "0.0.0.0", "port": 80, "status": "running"},
        ]})
        havoc_rest._client.get = AsyncMock(return_value=mock_resp)

        result = await havoc_rest.list_listeners()
        assert len(result) == 1
        assert result[0].id == "r1"

    @pytest.mark.asyncio
    async def test_create_listener_ws(self, havoc_ws):
        havoc_ws._ws_request = AsyncMock(
            return_value={"Type": "listener/add", "Body": {"ListenerID": "new-l", "Status": "running"}}
        )
        listener = await havoc_ws.create_listener({
            "name": "test-http",
            "protocol": "http",
            "bind_host": "0.0.0.0",
            "bind_port": 8080,
        })
        assert listener.id == "new-l"
        assert listener.bind_port == 8080
        assert listener.status == "running"

    @pytest.mark.asyncio
    async def test_remove_listener_ws(self, havoc_ws):
        havoc_ws._ws_request = AsyncMock(
            return_value={"Type": "listener/remove", "Body": {}}
        )
        result = await havoc_ws.remove_listener("l1")
        assert result is True

    @pytest.mark.asyncio
    async def test_remove_listener_rest(self, havoc_rest):
        mock_resp = make_resp(204, {})
        havoc_rest._client.delete = AsyncMock(return_value=mock_resp)
        result = await havoc_rest.remove_listener("r1")
        assert result is True


# ── Tests list_agents ────────────────────────────────────────────────────────

class TestHavocAgents:
    @pytest.fixture
    def demon_data(self):
        return {
            "AgentID": "d0c1a1e5",
            "Info": {
                "ComputerName": "WIN10-VICTIM",
                "Username":     "NT AUTHORITY\\SYSTEM",
                "InternalIP":   "192.168.1.50",
                "ExternalIP":   "1.2.3.4",
                "ProcessName":  "svchost.exe",
                "ProcessID":    1234,
                "OSVersion":    "Windows 10 x64",
                "ProcessArch":  "x64",
                "Elevated":     "system",
                "LastCheckin":  1700000000000,
                "Dead":         False,
            },
        }

    @pytest.mark.asyncio
    async def test_list_agents_ws(self, havoc_ws, demon_data):
        havoc_ws._ws_request = AsyncMock(
            return_value={"Type": "demon/list", "Body": {"Agents": [demon_data]}}
        )
        agents = await havoc_ws.list_agents()
        assert len(agents) == 1
        a = agents[0]
        assert a.id == "d0c1a1e5"
        assert a.hostname == "WIN10-VICTIM"
        assert a.integrity == "SYSTEM"
        assert a.pid == 1234
        assert a.active is True

    @pytest.mark.asyncio
    async def test_list_agents_rest(self, havoc_rest, demon_data):
        flat = {
            "id": demon_data["AgentID"],
            "hostname": "WIN10-REST",
            "username": "admin",
            "internal_ip": "10.0.0.1",
            "external_ip": "5.5.5.5",
            "integrity": "admin",
            "pid": 9999,
            "arch": "x64",
            "os": "Windows",
        }
        mock_resp = make_resp(200, {"agents": [flat]})
        havoc_rest._client.get = AsyncMock(return_value=mock_resp)

        agents = await havoc_rest.list_agents()
        assert len(agents) == 1
        assert agents[0].integrity == "ADMIN"

    def test_parse_demon_integrity_system(self, havoc_ws):
        d = {
            "AgentID": "abc",
            "Info": {"Elevated": "system", "ComputerName": "PC", "Listener": "l1"}
        }
        agent = havoc_ws._parse_demon(d)
        assert agent.integrity == "SYSTEM"

    def test_parse_demon_integrity_admin(self, havoc_ws):
        d = {
            "AgentID": "abc",
            "Info": {"Elevated": "high", "ComputerName": "PC", "Listener": "l1"}
        }
        agent = havoc_ws._parse_demon(d)
        assert agent.integrity == "ADMIN"

    def test_parse_demon_dead_flag(self, havoc_ws):
        d = {
            "AgentID": "dead1",
            "Info": {"Dead": True, "ComputerName": "PC"},
        }
        agent = havoc_ws._parse_demon(d)
        assert agent.active is False


# ── Tests send_task ──────────────────────────────────────────────────────────

class TestHavocTasks:
    @pytest.mark.asyncio
    async def test_send_task_shell_ws(self, havoc_ws):
        havoc_ws._ws_request = AsyncMock(
            return_value={
                "Type": "task/run",
                "Body": {"TaskID": "t123", "Status": "sent"},
            }
        )
        task = await havoc_ws.send_task("d0c1", "shell whoami")
        assert task.id == "t123"
        assert task.status == "sent"
        assert task.command == "shell whoami"

    @pytest.mark.asyncio
    async def test_send_task_screenshot_ws(self, havoc_ws):
        havoc_ws._ws_request = AsyncMock(
            return_value={"Type": "task/run", "Body": {"TaskID": "t-ss", "Status": "queued"}}
        )
        task = await havoc_ws.send_task("d0c1", "screenshot")
        assert task.id == "t-ss"

    @pytest.mark.asyncio
    async def test_send_task_rest(self, havoc_rest):
        mock_resp = make_resp(200, {"task_id": "t-rest-001", "status": "sent"})
        havoc_rest._client.post = AsyncMock(return_value=mock_resp)
        task = await havoc_rest.send_task("agent1", "shell id", ["arg1"])
        assert task.id == "t-rest-001"
        assert "arg1" in task.args

    def test_cmd_map_completeness(self, havoc_ws):
        """Vérifie que les commandes courantes sont dans le mapping."""
        for cmd in ("shell", "screenshot", "inject", "ls", "ps", "exit"):
            assert cmd in havoc_ws._CMD_MAP, f"Commande '{cmd}' manquante dans _CMD_MAP"


# ── Tests generate_payload ───────────────────────────────────────────────────

class TestHavocPayload:
    @pytest.mark.asyncio
    async def test_generate_payload_ws_base64(self, havoc_ws):
        import base64
        fake_bytes = b"MZ\x90\x00" + b"\x00" * 100
        b64 = base64.b64encode(fake_bytes).decode()

        havoc_ws._ws_request = AsyncMock(
            return_value={"Type": "payload/build", "Body": {"FileBase64": b64}}
        )
        cfg = PayloadConfig(
            name="test",
            c2_type=C2Type.HAVOC,
            listener_id="l1",
            format="exe",
            arch="x64",
        )
        payload = await havoc_ws.generate_payload(cfg)
        assert payload == fake_bytes
        assert payload[:2] == b"MZ"

    @pytest.mark.asyncio
    async def test_generate_payload_ws_empty(self, havoc_ws):
        havoc_ws._ws_request = AsyncMock(
            return_value={"Type": "payload/build", "Body": {}}
        )
        cfg = PayloadConfig(
            name="test", c2_type=C2Type.HAVOC, listener_id="l1", format="shellcode", arch="x64"
        )
        payload = await havoc_ws.generate_payload(cfg)
        assert payload == b""


# ── Tests capabilities ────────────────────────────────────────────────────────

class TestHavocCapabilities:
    @pytest.mark.asyncio
    async def test_get_capabilities(self, havoc_ws):
        caps = await havoc_ws.get_capabilities()
        assert "list_agents" in caps
        assert "send_task" in caps
        assert "generate_payload" in caps
        assert "screenshot" in caps

    @pytest.mark.asyncio
    async def test_get_status_ws_connected(self, havoc_ws):
        mock_ws = MagicMock()
        mock_ws.closed = False
        havoc_ws._ws = mock_ws
        status = await havoc_ws.get_status()
        assert status == C2Status.CONNECTED

    @pytest.mark.asyncio
    async def test_get_status_ws_no_conn(self, havoc_ws):
        havoc_ws._ws = None
        status = await havoc_ws.get_status()
        assert status == C2Status.DISCONNECTED
