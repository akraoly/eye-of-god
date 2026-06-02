"""
Store d'alertes proactives — file en mémoire, max 200 entrées.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional
from collections import deque
import threading


class AlertStore:
    def __init__(self, max_size: int = 200):
        self._alerts: deque[dict] = deque(maxlen=max_size)
        self._lock = threading.Lock()

    def add(
        self,
        title: str,
        body: str,
        level: str = "info",     # info | warning | error | critical
        source: str = "system",  # system | task | monitor
        meta: Optional[dict] = None,
    ) -> dict:
        alert = {
            "id": str(uuid.uuid4()),
            "title": title,
            "body": body,
            "level": level,
            "source": source,
            "meta": meta or {},
            "ts": datetime.now(timezone.utc).isoformat(),
            "read": False,
        }
        with self._lock:
            self._alerts.appendleft(alert)
        return alert

    def get_all(self, unread_only: bool = False, limit: int = 50) -> list[dict]:
        with self._lock:
            alerts = list(self._alerts)
        if unread_only:
            alerts = [a for a in alerts if not a["read"]]
        return alerts[:limit]

    def mark_read(self, alert_id: str):
        with self._lock:
            for a in self._alerts:
                if a["id"] == alert_id:
                    a["read"] = True
                    return True
        return False

    def mark_all_read(self):
        with self._lock:
            for a in self._alerts:
                a["read"] = True

    def dismiss(self, alert_id: str) -> bool:
        with self._lock:
            for i, a in enumerate(self._alerts):
                if a["id"] == alert_id:
                    del self._alerts[i]  # type: ignore[attr-defined]
                    return True
        return False

    def clear(self):
        with self._lock:
            self._alerts.clear()

    @property
    def unread_count(self) -> int:
        with self._lock:
            return sum(1 for a in self._alerts if not a["read"])


alert_store = AlertStore()
