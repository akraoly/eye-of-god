"""Tests PoshC2 — REST API Python (port 5000)."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from c2_manager.integrations.poshc2 import PoshC2C2
from c2_manager.models import C2Config, C2Type, C2Status
from c2_manager.models.payload import PayloadConfig
from tests.c2_manager.conftest import make_resp


@pytest.fixture
def poshc2_config() -> C2Config:
    return C2Config(
        name="test-poshc2",
        c2_type=C2Type.POSHC2,
        host="127.0.0.1",
        port=5000,
        username="admin",
        password="poshpw123",
        extra={"verify_ssl": False},
    )


@pytest.fixture
def poshc2(poshc2_config):
    c = PoshC2C2()
    c._config = poshc2_config
    c._status = C2Status.CONNECTED
    c._client = AsyncMock()
    c._token  = "posh-jwt-fake-token"
    return c


# ── Connexion ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_authenticate_jwt(poshc2_config):
    """Auth via POST /api/authenticate → token."""
    c = PoshC2C2()
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=make_resp(200, {"token": "jwt-abc"}))
    with patch("httpx.AsyncClient", return_value=mock_client):
        token = await c._authenticate(poshc2_config)
    assert token == "jwt-abc"


@pytest.mark.asyncio
async def test_authenticate_api_key(poshc2_config):
    """Auth via api_key dans extra."""
    poshc2_config.extra["api_key"] = "mykey"
    c = PoshC2C2()
    token = await c._authenticate(poshc2_config)
    assert token == "mykey"


@pytest.mark.asyncio
async def test_authenticate_alt_token_fields(poshc2_config):
    """Supporte access_token et jwt comme champs de réponse."""
    c = PoshC2C2()
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=make_resp(200, {"access_token": "alt-token"}))
    with patch("httpx.AsyncClient", return_value=mock_client):
        token = await c._authenticate(poshc2_config)
    assert token == "alt-token"


# ── Listeners / Handlers ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_listener_http(poshc2):
    """Créer un handler HTTP PoshC2."""
    poshc2._client.post = AsyncMock(return_value=make_resp(201, {
        "id": "hdl-1", "name": "http-handler", "active": True,
    }))
    listener = await poshc2.create_listener({
        "protocol": "http",
        "bind_host": "0.0.0.0",
        "bind_port": 80,
        "name": "http-handler",
    })
    assert listener.id == "hdl-1"
    assert listener.bind_port == 80
    assert listener.protocol == "http"


@pytest.mark.asyncio
async def test_create_listener_pbind(poshc2):
    """Créer un handler PBind (SMB)."""
    poshc2._client.post = AsyncMock(return_value=make_resp(201, {
        "id": "pbind-1", "name": "pbind", "active": True,
    }))
    listener = await poshc2.create_listener({
        "protocol": "smb",
        "name": "pbind",
    })
    assert listener.id == "pbind-1"


@pytest.mark.asyncio
async def test_list_listeners(poshc2):
    """Lister les handlers actifs."""
    poshc2._client.get = AsyncMock(return_value=make_resp(200, [
        {"id": "h1", "name": "http-80", "host": "0.0.0.0", "port": 80,
         "type": "http", "active": True},
        {"id": "h2", "name": "https-443", "host": "0.0.0.0", "port": 443,
         "type": "https", "active": False},
    ]))
    listeners = await poshc2.list_listeners()
    assert len(listeners) == 2
    assert listeners[0].status == "running"
    assert listeners[1].status == "stopped"


@pytest.mark.asyncio
async def test_remove_listener(poshc2):
    """Supprimer un handler."""
    poshc2._client.delete = AsyncMock(return_value=make_resp(204, {}))
    result = await poshc2.remove_listener("hdl-1")
    assert result is True


# ── Agents / Implants ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_agents(poshc2):
    """Lister les implants PoshC2."""
    poshc2._client.get = AsyncMock(return_value=make_resp(200, {
        "implants": [
            {
                "id": "imp-1",
                "hostname": "WIN10-PC",
                "username": "corp\\user",
                "ip": "10.0.0.5",
                "local_ip": "192.168.0.5",
                "os": "Windows 10",
                "arch": "x64",
                "pid": 1234,
                "process": "notepad.exe",
                "is_admin": False,
                "active": True,
                "last_seen": "2024-01-15T12:00:00",
            }
        ]
    }))
    agents = await poshc2.list_agents()
    assert len(agents) == 1
    assert agents[0].hostname == "WIN10-PC"
    assert agents[0].integrity == "USER"


@pytest.mark.asyncio
async def test_list_agents_admin(poshc2):
    """Implant admin → integrity ADMIN."""
    poshc2._client.get = AsyncMock(return_value=make_resp(200, {
        "implants": [
            {"id": "imp-2", "hostname": "SRV", "is_admin": True,
             "last_seen": "2024-01-15T12:00:00", "active": True}
        ]
    }))
    agents = await poshc2.list_agents()
    assert agents[0].integrity == "ADMIN"


# ── Tâches ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_send_task_cmd(poshc2):
    """Envoyer une tâche shell."""
    poshc2._client.post = AsyncMock(return_value=make_resp(201, {
        "id": "task-1", "status": "queued",
    }))
    task = await poshc2.send_task("imp-1", "cmd whoami", [])
    assert task.id == "task-1"
    assert task.agent_id == "imp-1"


@pytest.mark.asyncio
async def test_send_task_powershell(poshc2):
    """Envoyer une tâche PowerShell."""
    poshc2._client.post = AsyncMock(return_value=make_resp(201, {
        "id": "task-ps", "status": "queued",
    }))
    task = await poshc2.send_task("imp-1", "ps Get-Process", [])
    assert task.id == "task-ps"


@pytest.mark.asyncio
async def test_get_task_result(poshc2):
    """Récupérer le résultat d'une tâche."""
    poshc2._client.get = AsyncMock(return_value=make_resp(200, {
        "task_id": "task-1",
        "status": "completed",
        "output": "nt authority\\system",
    }))
    result = await poshc2.get_task_result("task-1")
    assert result["status"] == "completed"
    assert "system" in result["output"]


# ── Payload ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_generate_payload_b64(poshc2):
    """Générer un payload PoshC2 (retourné en base64)."""
    import base64
    b64_payload = base64.b64encode(b"MZ\x90\x00fake-exe").decode()
    poshc2._client.post = AsyncMock(return_value=make_resp(200, {
        "data": b64_payload,
    }))
    payload_cfg = PayloadConfig(
        name="posh-implant",
        format="exe",
        arch="x64",
        os="windows",
    )
    payload = await poshc2.generate_payload(payload_cfg)
    assert payload[:2] == b"MZ"


@pytest.mark.asyncio
async def test_list_hosted_files(poshc2):
    """Lister les fichiers hébergés."""
    poshc2._client.get = AsyncMock(return_value=make_resp(200, [
        {"id": "f1", "name": "loader.exe", "url": "/files/loader.exe"},
    ]))
    files = await poshc2.list_hosted_files()
    assert len(files) == 1
    assert files[0]["name"] == "loader.exe"


# ── Capabilities ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_capabilities(poshc2):
    caps = await poshc2.get_capabilities()
    assert "list_agents" in caps
    assert "send_task" in caps


# ── Disconnected guard ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_require_connected_guard(poshc2):
    """_require_connected() lève C2NotConnected si déconnecté."""
    from c2_manager.interfaces import C2NotConnected
    poshc2._status = C2Status.DISCONNECTED
    with pytest.raises(C2NotConnected):
        await poshc2.list_agents()
