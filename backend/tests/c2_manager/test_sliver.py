"""Tests SliverC2 — gRPC + operator config."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from c2_manager.integrations.sliver import SliverC2, _SliverStubSim
from c2_manager.models import C2Config, C2Type, C2Status


@pytest.fixture
def sliver():
    return SliverC2()


@pytest.fixture
def operator_cfg_file(tmp_path) -> str:
    cfg = {
        "operator":       "test-operator",
        "lhost":          "127.0.0.1",
        "lport":          31337,
        "ca_certificate": "-----BEGIN CERTIFICATE-----\nCA\n-----END CERTIFICATE-----\n",
        "certificate":    "-----BEGIN CERTIFICATE-----\nCLIENT\n-----END CERTIFICATE-----\n",
        "private_key":    "-----BEGIN RSA PRIVATE KEY-----\nKEY\n-----END RSA PRIVATE KEY-----\n",
        "token":          "test-token-abc123",
    }
    p = tmp_path / "test-operator.cfg"
    p.write_text(json.dumps(cfg))
    return str(p)


class TestSliverConfig:
    def test_load_operator_config(self, sliver, operator_cfg_file):
        data = sliver._load_operator_config(operator_cfg_file)
        assert data["operator"] == "test-operator"
        assert data["lhost"]    == "127.0.0.1"
        assert data["token"]    == "test-token-abc123"

    def test_load_operator_config_missing_file(self, sliver):
        with pytest.raises(FileNotFoundError):
            sliver._load_operator_config("/nonexistent/path/op.cfg")


class TestSliverStubSim:
    """Tests du stub simulé — utilisé quand sliver-py n'est pas installé."""

    @pytest.mark.asyncio
    async def test_get_sessions_empty(self):
        stub = _SliverStubSim()
        result = await stub.GetSessions()
        assert result.Sessions == []

    @pytest.mark.asyncio
    async def test_list_jobs_empty(self):
        stub = _SliverStubSim()
        result = await stub.ListJobs()
        assert result.Jobs == []

    @pytest.mark.asyncio
    async def test_start_mtls_listener(self):
        stub = _SliverStubSim()
        result = await stub.StartMTLSListener(host="0.0.0.0", port=8443)
        assert hasattr(result, "JobID")

    @pytest.mark.asyncio
    async def test_execute(self):
        stub = _SliverStubSim()
        result = await stub.Execute(Request={"SessionID": "1"}, Path="/bin/id", Args=[], Output=True)
        assert hasattr(result, "Stdout")


class TestSliverConnectWithStub:
    @pytest.mark.asyncio
    async def test_connect_uses_stub_when_no_grpc(self, sliver, sliver_config, operator_cfg_file):
        sliver_config.extra["operator_cfg"] = operator_cfg_file

        with patch.object(sliver, "_build_grpc_channel") as mock_channel:
            mock_channel.return_value = MagicMock()
            with patch.object(sliver, "_verify_connection", new_callable=AsyncMock):
                with patch.object(sliver, "_make_stub", new_callable=AsyncMock) as mock_stub:
                    mock_stub.return_value = _SliverStubSim()
                    ok = await sliver.connect(sliver_config)
        assert ok
        assert sliver._stub is not None

    @pytest.mark.asyncio
    async def test_list_agents_with_stub(self, sliver, sliver_config):
        sliver._config = sliver_config
        sliver._stub   = _SliverStubSim()
        sliver._status = C2Status.CONNECTED
        agents = await sliver.list_agents()
        assert agents == []

    @pytest.mark.asyncio
    async def test_send_task_with_stub(self, sliver, sliver_config):
        sliver._config = sliver_config
        sliver._stub   = _SliverStubSim()
        sliver._status = C2Status.CONNECTED
        task = await sliver.send_task("session-123", "execute", ["/bin/id"])
        assert task.agent_id == "session-123"
        assert task.command  == "execute"


class TestSliverCapabilities:
    @pytest.mark.asyncio
    async def test_get_capabilities(self, sliver):
        caps = await sliver.get_capabilities()
        assert "list_agents" in caps
        assert "generate_payload" in caps
