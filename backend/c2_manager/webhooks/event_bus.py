"""
Event Bus — diffusion des événements C2 en temps réel.

Fournit :
  - EventBus singleton avec subscribe/publish
  - Types d'événements : agent_connected, agent_disconnected, task_completed,
    listener_started, listener_stopped, payload_generated
  - WebSocket broadcast (FastAPI compatible)
  - Historique des derniers N événements
"""
from __future__ import annotations

import asyncio
import json
import logging
from collections import deque
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Coroutine

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    AGENT_CONNECTED     = "agent_connected"
    AGENT_DISCONNECTED  = "agent_disconnected"
    AGENT_CHECKIN       = "agent_checkin"
    TASK_SENT           = "task_sent"
    TASK_COMPLETED      = "task_completed"
    TASK_ERROR          = "task_error"
    LISTENER_STARTED    = "listener_started"
    LISTENER_STOPPED    = "listener_stopped"
    PAYLOAD_GENERATED   = "payload_generated"
    C2_CONNECTED        = "c2_connected"
    C2_DISCONNECTED     = "c2_disconnected"
    C2_ERROR            = "c2_error"


class Event:
    def __init__(
        self,
        event_type: EventType,
        c2_name:    str,
        data:       dict[str, Any],
    ) -> None:
        self.type      = event_type
        self.c2_name   = c2_name
        self.data      = data
        self.timestamp = datetime.utcnow().isoformat() + "Z"

    def to_json(self) -> str:
        return json.dumps({
            "type":      self.type,
            "c2":        self.c2_name,
            "data":      self.data,
            "timestamp": self.timestamp,
        })

    def to_dict(self) -> dict[str, Any]:
        return {
            "type":      self.type,
            "c2":        self.c2_name,
            "data":      self.data,
            "timestamp": self.timestamp,
        }


Handler = Callable[[Event], Coroutine[Any, Any, None]]


class EventBus:
    """Bus d'événements async — pub/sub interne + WebSocket broadcast."""

    def __init__(self, history_size: int = 500) -> None:
        self._handlers:  dict[EventType, list[Handler]] = {}
        self._global:    list[Handler] = []
        self._ws_clients: set[Any] = set()  # WebSocket connections
        self._history:   deque[dict[str, Any]] = deque(maxlen=history_size)

    def subscribe(
        self,
        event_type: EventType | None,
        handler: Handler,
    ) -> None:
        """S'abonner à un type d'événement. event_type=None → tous les événements."""
        if event_type is None:
            self._global.append(handler)
        else:
            self._handlers.setdefault(event_type, []).append(handler)

    def unsubscribe(self, event_type: EventType | None, handler: Handler) -> None:
        if event_type is None:
            self._global.remove(handler)
        else:
            handlers = self._handlers.get(event_type, [])
            if handler in handlers:
                handlers.remove(handler)

    async def publish(
        self,
        event_type: EventType,
        c2_name:    str,
        data:       dict[str, Any],
    ) -> None:
        event = Event(event_type, c2_name, data)
        self._history.append(event.to_dict())

        # Handlers spécifiques
        for handler in self._handlers.get(event_type, []):
            try:
                await handler(event)
            except Exception as exc:
                logger.error("EventBus handler erreur [%s] : %s", event_type, exc)

        # Handlers globaux
        for handler in self._global:
            try:
                await handler(event)
            except Exception as exc:
                logger.error("EventBus global handler erreur : %s", exc)

        # Broadcast WebSocket
        await self._broadcast_ws(event.to_json())

        logger.debug("EventBus : %s [%s] data=%s", event_type, c2_name, data)

    async def _broadcast_ws(self, message: str) -> None:
        dead = set()
        for ws in self._ws_clients:
            try:
                await ws.send_text(message)
            except Exception:
                dead.add(ws)
        self._ws_clients -= dead

    def add_ws_client(self, ws: Any) -> None:
        self._ws_clients.add(ws)
        logger.debug("EventBus : WebSocket client ajouté (%d total)", len(self._ws_clients))

    def remove_ws_client(self, ws: Any) -> None:
        self._ws_clients.discard(ws)

    def get_history(
        self,
        n: int = 100,
        event_type: EventType | None = None,
        c2_name: str | None = None,
    ) -> list[dict[str, Any]]:
        events = list(self._history)
        if event_type:
            events = [e for e in events if e["type"] == event_type]
        if c2_name:
            events = [e for e in events if e["c2"] == c2_name]
        return events[-n:]

    def clear_history(self) -> None:
        self._history.clear()


# Singleton global
event_bus = EventBus()
