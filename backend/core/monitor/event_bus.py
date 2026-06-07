"""
Bus d'événements temps réel du daemon Sentinel.
Thread-safe : les jobs APScheduler (sync) publient, les WebSockets (async) s'abonnent.
"""
from __future__ import annotations

import json
import threading
import asyncio
from collections import deque
from datetime import datetime
from typing import Optional

_MAX_HISTORY = 500


class SentinelEventBus:
    def __init__(self):
        self._history: deque[dict] = deque(maxlen=_MAX_HISTORY)
        self._queues: list[asyncio.Queue] = []
        self._lock = threading.Lock()
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def set_loop(self, loop: asyncio.AbstractEventLoop):
        self._loop = loop

    def subscribe(self, q: asyncio.Queue):
        with self._lock:
            self._queues.append(q)

    def unsubscribe(self, q: asyncio.Queue):
        with self._lock:
            try:
                self._queues.remove(q)
            except ValueError:
                pass

    def publish(self, event: dict):
        """Appelé depuis n'importe quel thread (APScheduler)."""
        event.setdefault("timestamp", datetime.utcnow().isoformat())
        self._history.append(event)

        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(self._push(event), self._loop)

    async def _push(self, event: dict):
        dead = []
        with self._lock:
            qs = list(self._queues)
        for q in qs:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                pass
            except Exception:
                dead.append(q)
        for q in dead:
            self.unsubscribe(q)

    def get_history(self, n: int = 50) -> list[dict]:
        return list(self._history)[-n:]

    def get_history_by_severity(self, severity: str, n: int = 50) -> list[dict]:
        return [e for e in self._history if e.get("severity") == severity][-n:]


sentinel_bus = SentinelEventBus()
