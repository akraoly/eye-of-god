"""Tests NighthawkC2 — JSON-RPC 2.0 + WebSocket push (MDSec)."""
from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest

from c2_manager.integrations.nighthawk import NighthawkC2, NighthawkRPCError, _next_rpc_id
from c2_manager.models import C2Config, C2Type, C2Status
from c2_manager.models.payload import PayloadConfig
from tests.c2_manager.conftest import make_resp


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def nighthawk_config() -> C2Config:
    return C2Config(
        name="test-nighthawk",
        c2_type=C2Type.NIGHTHAWK,
        host="127.0.0.1",
        port=8443,
        ssl=True,
        username="operator1",
        password="Nighthawk$ecure!",
        extra={
            "verify_ssl": False,
            "disable_ws": True,  # Désactiver WS dans les tests
        },
    )


@pytest.fixture
def nighthawk_apikey_config() -> C2Config:
    return C2Config(
        name="test-nighthawk-key",
        c2_type=C2Type.NIGHTHAWK,
        host="127.0.0.1",
        port=8443,
        ssl=True,
        extra={
            "api_key":   "static-api-key-xyz",
            "verify_ssl": False,
            "disable_ws": True,
        },
    )


@pytest.fixture
def nighthawk(nighthawk_config):
    n = NighthawkC2()
    n._config      = nighthawk_config
    n._rpc_path    = "/api/rpc"
    n._rpc_timeout = 30.0
    n._token       = "session-token-abc"
    n._status      = C2Status.CONNECTED
    n._client      = AsyncMock()
    n._client.headers = MagicMock()
    n._client.headers.update = MagicMock()
    return n


def _rpc_resp(result: dict | list | None, error: dict | None = None) -> MagicMock:
    """Créer une réponse JSON-RPC mockée."""
    body = {"jsonrpc": "2.0", "id": 1}
    if error:
        body["error"] = error
    else:
        body["result"] = result
    return make_resp(200, body)


# ── Tests connexion et auth ───────────────────────────────────────────────────

class TestNighthawkAuth:
    @pytest.mark.asyncio
    async def test_connect_with_login(self, nighthawk_config):
        n = NighthawkC2()
        mock_client = AsyncMock()
        mock_client.headers = {"Content-Type": "application/json"}

        login_resp = _rpc_resp({"token": "fresh-session-token"})
        mock_client.post = AsyncMock(return_value=login_resp)
        mock_client.aclose = AsyncMock()

        with patch("httpx.AsyncClient", return_value=mock_client), \
             patch("asyncio.create_task"):
            result = await n.connect(nighthawk_config)

        assert result is True
        assert n._token == "fresh-session-token"

    @pytest.mark.asyncio
    async def test_connect_with_api_key(self, nighthawk_apikey_config):
        n = NighthawkC2()
        mock_client = AsyncMock()
        mock_client.headers = {}
        mock_client.aclose  = AsyncMock()

        with patch("httpx.AsyncClient", return_value=mock_client), \
             patch("asyncio.create_task"):
            result = await n.connect(nighthawk_apikey_config)

        assert result is True
        assert n._token == "static-api-key-xyz"

    @pytest.mark.asyncio
    async def test_rpc_login_success(self, nighthawk_config):
        n = NighthawkC2()
        n._client    = AsyncMock()
        n._rpc_path  = "/api/rpc"
        n._rpc_timeout = 30.0
        n._client.post = AsyncMock(
            return_value=_rpc_resp({"token": "new-token"})
        )
        token = await n._rpc_login(nighthawk_config)
        assert token == "new-token"

    @pytest.mark.asyncio
    async def test_rpc_login_bad_creds(self, nighthawk_config):
        from c2_manager.interfaces import C2AuthError
        n = NighthawkC2()
        n._client   = AsyncMock()
        n._rpc_path = "/api/rpc"
        n._rpc_timeout = 30.0
        n._client.post = AsyncMock(
            return_value=_rpc_resp(None, {"code": -32000, "message": "Invalid credentials"})
        )
        with pytest.raises(C2AuthError, match="login RPC erreur"):
            await n._rpc_login(nighthawk_config)

    @pytest.mark.asyncio
    async def test_rpc_login_alt_token_fields(self, nighthawk_config):
        """Test les différents noms de champ pour le token."""
        n = NighthawkC2()
        n._client    = AsyncMock()
        n._rpc_path  = "/api/rpc"
        n._rpc_timeout = 30.0

        for field, value in [("session_token", "s1"), ("access_token", "a2"), ("api_key", "k3")]:
            n._client.post = AsyncMock(
                return_value=_rpc_resp({field: value})
            )
            token = await n._rpc_login(nighthawk_config)
            assert token == value

    @pytest.mark.asyncio
    async def test_rpc_login_http_error(self, nighthawk_config):
        from c2_manager.interfaces import C2AuthError
        n = NighthawkC2()
        n._client   = AsyncMock()
        n._rpc_path = "/api/rpc"
        n._rpc_timeout = 30.0
        n._client.post = AsyncMock(return_value=make_resp(403, {"error": "Forbidden"}))
        with pytest.raises(C2AuthError, match="HTTP échouée"):
            await n._rpc_login(nighthawk_config)


# ── Tests RPC core ────────────────────────────────────────────────────────────

class TestNighthawkRPC:
    @pytest.mark.asyncio
    async def test_rpc_success(self, nighthawk):
        nighthawk._client.post = AsyncMock(
            return_value=_rpc_resp({"agents": []})
        )
        result = await nighthawk._rpc("Agent_List")
        assert result == {"agents": []}

    @pytest.mark.asyncio
    async def test_rpc_with_params(self, nighthawk):
        nighthawk._client.post = AsyncMock(
            return_value=_rpc_resp({"task_id": "t123"})
        )
        result = await nighthawk._rpc("Agent_Task", {"agent_id": "a1", "command": "whoami"})
        assert result["task_id"] == "t123"

        # Vérifier que la structure JSON-RPC est correcte
        call_kwargs = nighthawk._client.post.call_args
        body = call_kwargs[1]["json"]
        assert body["jsonrpc"] == "2.0"
        assert body["method"]  == "Agent_Task"
        assert "id" in body
        assert body["params"]["agent_id"] == "a1"

    @pytest.mark.asyncio
    async def test_rpc_error_response(self, nighthawk):
        nighthawk._client.post = AsyncMock(
            return_value=_rpc_resp(None, {"code": -32601, "message": "Method not found"})
        )
        with pytest.raises(NighthawkRPCError) as exc_info:
            await nighthawk._rpc("Unknown_Method")
        assert exc_info.value.code == -32601
        assert "not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_rpc_timeout(self, nighthawk):
        import httpx
        nighthawk._client.post = AsyncMock(
            side_effect=httpx.TimeoutException("timeout")
        )
        with pytest.raises(NighthawkRPCError, match="Timeout"):
            await nighthawk._rpc("Slow_Method", timeout=0.001)

    @pytest.mark.asyncio
    async def test_rpc_http_non_200(self, nighthawk):
        nighthawk._client.post = AsyncMock(
            return_value=make_resp(503, {"error": "Service Unavailable"})
        )
        with pytest.raises(NighthawkRPCError):
            await nighthawk._rpc("Any_Method")

    def test_rpc_id_increments(self):
        """Vérifie que _next_rpc_id() génère des IDs croissants."""
        ids = [_next_rpc_id() for _ in range(5)]
        assert ids == sorted(ids)
        assert len(set(ids)) == 5


# ── Tests Listeners ───────────────────────────────────────────────────────────

class TestNighthawkListeners:
    @pytest.mark.asyncio
    async def test_list_listeners_empty(self, nighthawk):
        nighthawk._rpc = AsyncMock(return_value={"listeners": []})
        result = await nighthawk.list_listeners()
        assert result == []

    @pytest.mark.asyncio
    async def test_list_listeners_with_data(self, nighthawk):
        nighthawk._rpc = AsyncMock(return_value={"listeners": [
            {"id": "l1", "name": "https-443", "protocol": "https",
             "bind_address": "0.0.0.0", "bind_port": 443, "status": "active"},
            {"id": "l2", "name": "http-80", "protocol": "http",
             "bind_address": "0.0.0.0", "bind_port": 80, "status": "stopped"},
        ]})
        result = await nighthawk.list_listeners()
        assert len(result) == 2
        assert result[0].id == "l1"
        assert result[0].protocol == "https"
        assert result[0].status == "running"
        assert result[1].status == "stopped"

    @pytest.mark.asyncio
    async def test_list_listeners_as_list(self, nighthawk):
        """Test quand l'API retourne directement une liste."""
        nighthawk._rpc = AsyncMock(return_value=[
            {"id": "l3", "name": "direct-list", "protocol": "https",
             "bind_address": "0.0.0.0", "bind_port": 8443, "status": "active"},
        ])
        result = await nighthawk.list_listeners()
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_create_listener(self, nighthawk):
        nighthawk._rpc = AsyncMock(return_value={
            "id": "new-l1", "name": "beacon-443", "status": "active",
            "profile": "default", "uri_paths": ["/update"],
        })
        listener = await nighthawk.create_listener({
            "name": "beacon-443",
            "protocol": "https",
            "bind_port": 443,
            "callback_host": "10.0.0.1",
        })
        assert listener.id == "new-l1"
        assert listener.status == "running"
        # Vérifier les paramètres passés à _rpc
        call_args = nighthawk._rpc.call_args
        assert call_args[0][0] == "Listener_Create"
        params = call_args[0][1]
        assert params["bind_port"] == 443
        assert params["ssl"] is True

    @pytest.mark.asyncio
    async def test_remove_listener_success(self, nighthawk):
        nighthawk._rpc = AsyncMock(return_value={"deleted": True})
        result = await nighthawk.remove_listener("l1")
        assert result is True
        nighthawk._rpc.assert_called_with("Listener_Delete", {"listener_id": "l1"})

    @pytest.mark.asyncio
    async def test_remove_listener_rpc_error(self, nighthawk):
        nighthawk._rpc = AsyncMock(side_effect=NighthawkRPCError(-1, "Not found"))
        result = await nighthawk.remove_listener("nonexistent")
        assert result is False


# ── Tests Agents ──────────────────────────────────────────────────────────────

class TestNighthawkAgents:
    @pytest.fixture
    def agent_data(self):
        return {
            "id": "agent-abc-123",
            "hostname": "WIN-VICTIM-01",
            "username": "NT AUTHORITY\\SYSTEM",
            "external_ip": "203.0.113.1",
            "internal_ip": "10.0.0.50",
            "os": "Windows 10 x64",
            "arch": "x64",
            "pid": 6789,
            "process": "explorer.exe",
            "integrity": 4,  # SYSTEM
            "listener_id": "l1",
            "last_checkin": 1700000000000,
            "first_seen": 1699900000000,
            "active": True,
            "sleep": 60,
            "jitter": 10,
        }

    @pytest.mark.asyncio
    async def test_list_agents(self, nighthawk, agent_data):
        nighthawk._rpc = AsyncMock(return_value={"agents": [agent_data]})
        agents = await nighthawk.list_agents()
        assert len(agents) == 1
        a = agents[0]
        assert a.id == "agent-abc-123"
        assert a.integrity == "SYSTEM"
        assert a.hostname == "WIN-VICTIM-01"
        assert a.active is True

    @pytest.mark.asyncio
    async def test_list_agents_as_list(self, nighthawk, agent_data):
        nighthawk._rpc = AsyncMock(return_value=[agent_data])
        agents = await nighthawk.list_agents()
        assert len(agents) == 1

    def test_parse_agent_integrity_int(self, nighthawk):
        for level, expected in [(4, "SYSTEM"), (3, "SYSTEM"), (2, "ADMIN"), (1, "USER"), (0, "USER")]:
            a = {"id": "x", "integrity": level, "last_checkin": 0, "first_seen": 0}
            implant = nighthawk._parse_agent(a)
            assert implant.integrity == expected, f"Level {level} → attendu {expected}"

    def test_parse_agent_integrity_string(self, nighthawk):
        cases = [
            ("SYSTEM",    "SYSTEM"),
            ("ADMIN",     "ADMIN"),
            ("HIGH",      "ADMIN"),
            ("MEDIUM",    "USER"),
            ("USER",      "USER"),
            ("LOW",       "USER"),
        ]
        for raw, expected in cases:
            a = {"id": "x", "integrity": raw, "last_checkin": 0, "first_seen": 0}
            implant = nighthawk._parse_agent(a)
            assert implant.integrity == expected, f"'{raw}' → attendu {expected}"

    def test_parse_agent_dead_flag(self, nighthawk):
        a = {"id": "x", "active": True, "dead": True, "last_checkin": 0, "first_seen": 0}
        implant = nighthawk._parse_agent(a)
        assert implant.active is False

    def test_parse_agent_unix_timestamps(self, nighthawk):
        a = {
            "id": "x",
            "last_checkin": 1700000000000,   # ms
            "first_seen":   1699900000000,
        }
        implant = nighthawk._parse_agent(a)
        assert implant.last_checkin.year == 2023
        assert implant.first_seen.year   == 2023

    def test_parse_agent_iso_timestamps(self, nighthawk):
        a = {
            "id": "x",
            "last_checkin": "2024-05-01T10:00:00Z",
            "first_seen":   "2024-04-30T08:00:00Z",
        }
        implant = nighthawk._parse_agent(a)
        assert implant.last_checkin.month == 5
        assert implant.first_seen.month   == 4


# ── Tests Tâches ──────────────────────────────────────────────────────────────

class TestNighthawkTasks:
    @pytest.mark.asyncio
    async def test_send_shell_task(self, nighthawk):
        nighthawk._rpc = AsyncMock(return_value={"task_id": "t001", "status": "queued"})
        task = await nighthawk.send_task("agent1", "shell whoami")
        assert task.id == "t001"
        assert task.status == "queued"
        assert task.agent_id == "agent1"

        call_args = nighthawk._rpc.call_args
        assert call_args[0][0] == "Agent_Task"
        params = call_args[0][1]
        assert params["task_type"] == "ShellExecute"

    @pytest.mark.asyncio
    async def test_send_powershell_task(self, nighthawk):
        nighthawk._rpc = AsyncMock(return_value={"task_id": "t002", "status": "queued"})
        task = await nighthawk.send_task("agent1", "ps Get-Process -Name explorer")
        call_args = nighthawk._rpc.call_args
        assert call_args[0][1]["task_type"] == "PowerShellExecute"

    @pytest.mark.asyncio
    async def test_send_assembly_task(self, nighthawk):
        nighthawk._rpc = AsyncMock(return_value={"task_id": "t003", "status": "queued"})
        await nighthawk.send_task("agent1", "assembly Seatbelt.exe -group=all")
        params = nighthawk._rpc.call_args[0][1]["parameters"]
        assert params["in_memory"] is True
        assert params["bypass_amsi"] is True

    @pytest.mark.asyncio
    async def test_send_screenshot_task(self, nighthawk):
        nighthawk._rpc = AsyncMock(return_value={"task_id": "t004", "status": "queued"})
        await nighthawk.send_task("agent1", "screenshot")
        params = nighthawk._rpc.call_args[0][1]["parameters"]
        assert "monitor" in params
        assert params["quality"] == 85

    @pytest.mark.asyncio
    async def test_send_sleep_task(self, nighthawk):
        nighthawk._rpc = AsyncMock(return_value={"id": "t005", "status": "sent"})
        task = await nighthawk.send_task("agent1", "sleep 30 5")
        params = nighthawk._rpc.call_args[0][1]["parameters"]
        assert params["sleep_time"] == 30

    @pytest.mark.asyncio
    async def test_send_inject_task(self, nighthawk):
        nighthawk._rpc = AsyncMock(return_value={"task_id": "t006", "status": "queued"})
        await nighthawk.send_task("agent1", "inject 1234 x64 shellcode")
        params = nighthawk._rpc.call_args[0][1]["parameters"]
        assert params["pid"] == 1234

    @pytest.mark.asyncio
    async def test_get_task_result(self, nighthawk):
        nighthawk._rpc = AsyncMock(return_value={
            "status":   "completed",
            "output":   "NT AUTHORITY\\SYSTEM",
            "duration_ms": 1234,
        })
        result = await nighthawk.get_task_result("agent1/t001")
        assert result["status"] == "completed"
        assert "SYSTEM" in result["output"]

    @pytest.mark.asyncio
    async def test_get_task_result_no_slash(self, nighthawk):
        nighthawk._rpc = AsyncMock(return_value={
            "status": "completed",
            "result": "output here",
        })
        result = await nighthawk.get_task_result("standalone-task-id")
        assert result["output"] == "output here"

    def test_task_types_coverage(self, nighthawk):
        for cmd in ("shell", "ps", "assembly", "inject", "screenshot", "keylog",
                    "upload", "download", "pivot", "exit", "sleep"):
            assert cmd in nighthawk._TASK_TYPES, f"Type '{cmd}' manquant"


# ── Tests Payload ─────────────────────────────────────────────────────────────

class TestNighthawkPayload:
    @pytest.mark.asyncio
    async def test_generate_payload_base64(self, nighthawk):
        import base64
        fake_pe = b"MZ\x90\x00" + b"\x00" * 300
        b64_pe  = base64.b64encode(fake_pe).decode()

        nighthawk._rpc = AsyncMock(return_value={"data": b64_pe})
        cfg = PayloadConfig(
            name="nighthawk-payload",
            c2_type=C2Type.NIGHTHAWK,
            listener_id="l1",
            format="exe",
            arch="x64",
            sleep=60,
            jitter=10,
            obfuscation=True,
        )
        payload = await nighthawk.generate_payload(cfg)
        assert payload == fake_pe
        assert payload[:2] == b"MZ"

    @pytest.mark.asyncio
    async def test_generate_payload_with_evasion_options(self, nighthawk):
        """Vérifie que les options d'évasion avancées sont transmises."""
        nighthawk._rpc = AsyncMock(return_value={"data": ""})
        cfg = PayloadConfig(
            name="stealthy",
            c2_type=C2Type.NIGHTHAWK,
            listener_id="l1",
            format="shellcode",
            arch="x64",
            extra={
                "sleep_mask": "foliage",
                "syscall_type": "indirect",
                "spoof_call_stack": True,
                "etw_bypass": True,
            },
        )
        await nighthawk.generate_payload(cfg)
        params = nighthawk._rpc.call_args[0][1]
        assert params["sleep_mask"] == "foliage"
        assert params["syscall_type"] == "indirect"
        assert params["spoof_call_stack"] is True

    @pytest.mark.asyncio
    async def test_generate_payload_file_id_download(self, nighthawk):
        import base64
        fake_dll = b"MZ" + b"\xAA" * 100
        b64_dll  = base64.b64encode(fake_dll).decode()

        # Première appel → file_id, deuxième → données
        nighthawk._rpc = AsyncMock(side_effect=[
            {"file_id": "fid-xyz"},
            {"data": b64_dll},
        ])
        cfg = PayloadConfig(
            name="dll-payload",
            c2_type=C2Type.NIGHTHAWK,
            listener_id="l1",
            format="dll",
            arch="x64",
        )
        payload = await nighthawk.generate_payload(cfg)
        assert payload == fake_dll


# ── Tests kill_agent ──────────────────────────────────────────────────────────

class TestNighthawkKillAgent:
    @pytest.mark.asyncio
    async def test_kill_agent_success(self, nighthawk):
        nighthawk._rpc = AsyncMock(return_value={"killed": True})
        result = await nighthawk.kill_agent("agent1")
        assert result is True
        nighthawk._rpc.assert_called_with("Agent_Kill", {"agent_id": "agent1"})

    @pytest.mark.asyncio
    async def test_kill_agent_rpc_error(self, nighthawk):
        nighthawk._rpc = AsyncMock(side_effect=NighthawkRPCError(-1, "Agent not found"))
        result = await nighthawk.kill_agent("nonexistent")
        assert result is False


# ── Tests event callbacks ─────────────────────────────────────────────────────

class TestNighthawkEvents:
    @pytest.mark.asyncio
    async def test_on_event_sync_callback(self, nighthawk):
        received = []
        nighthawk.on_event(lambda t, d: received.append((t, d)))

        await nighthawk._handle_push_event({
            "event_type": "agent_callback",
            "data": {"agent_id": "a1"},
        })
        assert len(received) == 1
        assert received[0][0] == "agent_callback"

    @pytest.mark.asyncio
    async def test_on_event_async_callback(self, nighthawk):
        received = []

        async def cb(event_type, data):
            received.append(event_type)

        nighthawk.on_event(cb)
        await nighthawk._handle_push_event({"type": "task_complete", "payload": {}})
        assert "task_complete" in received

    @pytest.mark.asyncio
    async def test_on_event_multiple_callbacks(self, nighthawk):
        calls = []
        nighthawk.on_event(lambda t, d: calls.append(1))
        nighthawk.on_event(lambda t, d: calls.append(2))

        await nighthawk._handle_push_event({"event_type": "beacon", "data": {}})
        assert len(calls) == 2


# ── Tests statut et capabilities ─────────────────────────────────────────────

class TestNighthawkStatusCaps:
    @pytest.mark.asyncio
    async def test_get_status_connected(self, nighthawk):
        nighthawk._rpc = AsyncMock(return_value={"agents": []})
        status = await nighthawk.get_status()
        assert status == C2Status.CONNECTED

    @pytest.mark.asyncio
    async def test_get_status_rpc_error(self, nighthawk):
        nighthawk._rpc = AsyncMock(side_effect=NighthawkRPCError(-1, "Offline"))
        status = await nighthawk.get_status()
        assert status == C2Status.ERROR

    @pytest.mark.asyncio
    async def test_get_status_no_client(self):
        n = NighthawkC2()
        status = await n.get_status()
        assert status == C2Status.DISCONNECTED

    @pytest.mark.asyncio
    async def test_get_capabilities(self, nighthawk):
        caps = await nighthawk.get_capabilities()
        for expected in ("list_agents", "send_task", "generate_payload",
                         "screenshot", "keylog", "inject", "ws_events"):
            assert expected in caps

    @pytest.mark.asyncio
    async def test_disconnect(self, nighthawk):
        nighthawk._client = AsyncMock()
        nighthawk._client.aclose = AsyncMock()
        await nighthawk.disconnect()
        assert nighthawk._client is None
        assert nighthawk._status == C2Status.DISCONNECTED
