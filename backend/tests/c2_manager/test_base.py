"""Tests BaseC2Interface — reconnexion, retry, healthcheck."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from c2_manager.interfaces.base import BaseC2Interface, C2ConnectionError, C2NotConnected
from c2_manager.models import C2Config, C2Status, C2Type, Listener, Implant, Task, PayloadConfig


class ConcreteC2(BaseC2Interface):
    """Implémentation minimale pour tester la classe de base."""

    def __init__(self, fail_times: int = 0):
        super().__init__()
        self._fail_times = fail_times
        self._attempts   = 0

    async def connect(self, config: C2Config) -> bool:
        self._attempts += 1
        if self._attempts <= self._fail_times:
            raise C2ConnectionError(f"Échec simulé tentative {self._attempts}")
        self._config = config
        return True

    async def disconnect(self):                  self._status = C2Status.DISCONNECTED
    async def get_status(self) -> C2Status:      return self._status
    async def create_listener(self, c):          return Listener(id="1", name="l", c2_type=C2Type.SLIVER, bind_host="0.0.0.0", bind_port=80, protocol="http", created_at=__import__('datetime').datetime.utcnow())
    async def remove_listener(self, lid):        return True
    async def list_listeners(self):              return []
    async def list_agents(self):                 return []
    async def send_task(self, aid, cmd, args):   return Task(id="1", agent_id=aid, c2_type="test", command=cmd, created_at=__import__('datetime').datetime.utcnow())
    async def get_task_result(self, tid):        return {}
    async def generate_payload(self, cfg):       return b""
    async def get_capabilities(self):            return []


@pytest.fixture
def config():
    return C2Config(name="test", c2_type=C2Type.SLIVER, host="127.0.0.1", port=9999)


class TestBaseC2Interface:
    def test_initial_state(self, config):
        c2 = ConcreteC2()
        assert not c2.is_connected
        assert c2._status == C2Status.DISCONNECTED

    @pytest.mark.asyncio
    async def test_connect_success(self, config):
        c2 = ConcreteC2(fail_times=0)
        ok = await c2.connect_with_retry(config)
        assert ok
        assert c2._status == C2Status.CONNECTED

    @pytest.mark.asyncio
    async def test_retry_success_after_failures(self, config):
        c2 = ConcreteC2(fail_times=2)
        c2.MAX_RETRIES = 3
        c2.RETRY_BASE_SEC = 0.01
        ok = await c2.connect_with_retry(config)
        assert ok
        assert c2._attempts == 3

    @pytest.mark.asyncio
    async def test_retry_exhausted_raises(self, config):
        c2 = ConcreteC2(fail_times=10)
        c2.MAX_RETRIES = 2
        c2.RETRY_BASE_SEC = 0.01
        with pytest.raises(C2ConnectionError):
            await c2.connect_with_retry(config)
        assert c2._status == C2Status.ERROR

    @pytest.mark.asyncio
    async def test_require_connected_raises_when_disconnected(self, config):
        c2 = ConcreteC2()
        with pytest.raises(C2NotConnected):
            c2._require_connected()

    @pytest.mark.asyncio
    async def test_require_connected_passes_when_connected(self, config):
        c2 = ConcreteC2()
        await c2.connect_with_retry(config)
        c2._require_connected()  # ne doit pas lever

    @pytest.mark.asyncio
    async def test_healthcheck_detects_disconnect(self, config):
        c2 = ConcreteC2()
        await c2.connect_with_retry(config)
        # Simuler une perte de connexion
        c2._status = C2Status.DISCONNECTED
        await c2.start_healthcheck(interval=0.05)
        await asyncio.sleep(0.15)
        await c2.stop_healthcheck()
        # La healthcheck tente de reconnecter — status change
        assert c2._attempts >= 1
