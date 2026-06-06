"""Tests PwnDocC2 — outil rapport pentest (REST API JWT)."""
from __future__ import annotations

import base64
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from c2_manager.integrations.pwndoc import PwnDocC2
from c2_manager.models import C2Config, C2Type, C2Status
from c2_manager.models.payload import PayloadConfig
from tests.c2_manager.conftest import make_resp


@pytest.fixture
def pwndoc_config() -> C2Config:
    return C2Config(
        name="test-pwndoc",
        c2_type=C2Type.PWNDOC,
        host="127.0.0.1",
        port=8443,
        ssl=True,
        username="admin",
        password="P@ssw0rd",
        extra={"verify_ssl": False},
    )


@pytest.fixture
def pwndoc(pwndoc_config):
    c = PwnDocC2()
    c._config        = pwndoc_config
    c._status        = C2Status.CONNECTED
    c._client        = AsyncMock()
    c._token         = "pwndoc-jwt"
    c._refresh_token = "pwndoc-refresh"
    return c


# ── Auth ──────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_authenticate(pwndoc_config):
    """Auth via /api/users/token → {datas: {token, refreshToken}}."""
    c = PwnDocC2()
    mock_resp = make_resp(200, {"datas": {"token": "jwt-tok", "refreshToken": "ref-tok"}})
    with patch("httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__  = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_cls.return_value = mock_client
        token = await c._authenticate(pwndoc_config)
    assert token == "jwt-tok"


@pytest.mark.asyncio
async def test_authenticate_direct_token(pwndoc_config):
    """Auth : réponse avec token direct (pas dans datas)."""
    c = PwnDocC2()
    mock_resp = make_resp(200, {"token": "direct-tok"})
    with patch("httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__  = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_cls.return_value = mock_client
        token = await c._authenticate(pwndoc_config)
    assert token == "direct-tok"


# ── Audits (listeners) ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_listener_audit(pwndoc):
    """Créer un audit = listener dans PwnDoc."""
    pwndoc._client.post = AsyncMock(return_value=make_resp(201, {
        "datas": {"_id": "audit-1"}
    }))
    listener = await pwndoc.create_listener({
        "name": "Pentest-Corp",
        "client": "Corp Inc",
        "language": "fr",
    })
    assert listener.id == "audit-1"
    assert listener.protocol == "audit"


@pytest.mark.asyncio
async def test_list_listeners_audits(pwndoc):
    """Lister les audits → listeners."""
    pwndoc._client.get = AsyncMock(return_value=make_resp(200, {
        "datas": [
            {"_id": "a1", "name": "Audit-1", "state": "EDIT"},
            {"_id": "a2", "name": "Audit-2", "state": "REVIEW"},
        ]
    }))
    listeners = await pwndoc.list_listeners()
    assert len(listeners) == 2
    assert listeners[0].status == "running"


@pytest.mark.asyncio
async def test_remove_listener(pwndoc):
    """Supprimer un audit."""
    pwndoc._client.delete = AsyncMock(return_value=make_resp(200, {"datas": "success"}))
    result = await pwndoc.remove_listener("audit-1")
    assert result is True


# ── Vulnerabilities (agents) ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_agents_vulns(pwndoc):
    """Lister les vulnérabilités = agents."""
    pwndoc._client.get = AsyncMock(return_value=make_resp(200, {
        "datas": [
            {"_id": "v1", "title": "SQLi", "cvss": 9.5, "status": "confirmed",
             "category": "Web"},
            {"_id": "v2", "title": "XSS", "cvss": 6.5, "status": "unconfirmed",
             "category": "Web"},
        ]
    }))
    agents = await pwndoc.list_agents()
    assert len(agents) == 2
    assert agents[0].hostname == "SQLi"
    assert agents[0].integrity == "SYSTEM"    # cvss 9.5 ≥ 9.0
    assert agents[1].integrity == "USER"      # cvss 6.5


@pytest.mark.asyncio
async def test_cvss_severity_admin(pwndoc):
    """cvss ≥ 7.0 → ADMIN."""
    pwndoc._client.get = AsyncMock(return_value=make_resp(200, {
        "datas": [{"_id": "v3", "title": "RCE", "cvss": 8.0}]
    }))
    agents = await pwndoc.list_agents()
    assert agents[0].integrity == "ADMIN"


# ── Findings (tasks) ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_send_task_add_finding(pwndoc):
    """Ajouter un finding à un audit."""
    pwndoc._client.post = AsyncMock(return_value=make_resp(200, {
        "datas": {"_id": "finding-1"}
    }))
    task = await pwndoc.send_task("audit-1", "add_finding", ["vuln-id"])
    assert task.agent_id == "audit-1"
    assert task.status == "completed"


@pytest.mark.asyncio
async def test_send_task_update_finding(pwndoc):
    """Mettre à jour un finding existant."""
    pwndoc._client.put = AsyncMock(return_value=make_resp(200, {
        "datas": {"_id": "finding-1"}
    }))
    task = await pwndoc.send_task("audit-1", "update finding-1 status=confirmed", [])
    assert task.agent_id == "audit-1"


# ── Payload = rapport Word ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_generate_payload_report(pwndoc):
    """generate_payload → télécharger le rapport Word d'un audit."""
    word_bytes = b"PK\x03\x04fake-docx"
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = word_bytes
    mock_resp.raise_for_status = MagicMock()
    pwndoc._client.get = AsyncMock(return_value=mock_resp)

    payload_cfg = PayloadConfig(
        name="rapport",
        format="docx",
        extra={"audit_id": "audit-1"},
    )
    data = await pwndoc.generate_payload(payload_cfg)
    assert data == word_bytes


# ── Méthodes spécifiques ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_vulnerabilities(pwndoc):
    pwndoc._client.get = AsyncMock(return_value=make_resp(200, {
        "datas": [{"_id": "v1", "title": "SQLi", "cvss": 9.0}]
    }))
    vulns = await pwndoc.list_vulnerabilities()
    assert len(vulns) == 1


@pytest.mark.asyncio
async def test_add_vulnerability(pwndoc):
    pwndoc._client.post = AsyncMock(return_value=make_resp(201, {
        "datas": {"_id": "vuln-new"}
    }))
    vuln_id = await pwndoc.add_vulnerability({
        "title": "SSRF", "cvss": 7.5, "description": "SSRF endpoint"
    })
    assert vuln_id == "vuln-new"


@pytest.mark.asyncio
async def test_list_clients(pwndoc):
    pwndoc._client.get = AsyncMock(return_value=make_resp(200, {
        "datas": [{"_id": "c1", "name": "Corp Inc"}]
    }))
    clients = await pwndoc.list_clients()
    assert clients[0]["name"] == "Corp Inc"


@pytest.mark.asyncio
async def test_generate_report(pwndoc):
    pwndoc._client.get = AsyncMock(return_value=make_resp(200, {
        "datas": "report-generated"
    }))
    result = await pwndoc.generate_report("audit-1")
    assert result is not None


# ── Guard ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_require_connected_guard(pwndoc):
    from c2_manager.interfaces import C2NotConnected
    pwndoc._status = C2Status.DISCONNECTED
    with pytest.raises(C2NotConnected):
        await pwndoc.list_listeners()
