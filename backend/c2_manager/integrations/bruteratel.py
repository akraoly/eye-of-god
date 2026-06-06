"""
BruteRatel C4 — API propriétaire + SMB ExternalC2

STATUT : Stub — à implémenter avec les détails de l'API officielle.
Interface parente : ExternalC2Interface
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from c2_manager.interfaces import ExternalC2Interface
from c2_manager.models import C2Config, C2Status, Listener, Implant, Task, PayloadConfig


class BruteRatelC2(ExternalC2Interface):
    """BruteRatel C4 — API propriétaire + SMB ExternalC2."""

    CAPABILITIES: list[str] = []

    async def connect(self, config: C2Config) -> bool:
        self._config = config
        # TODO: implémenter la connexion tcp
        raise NotImplementedError("bruteratel connect() non implémenté")

    async def create_listener(self, config: dict[str, Any]) -> Listener:
        raise NotImplementedError("bruteratel create_listener() non implémenté")

    async def remove_listener(self, listener_id: str) -> bool:
        raise NotImplementedError("bruteratel remove_listener() non implémenté")

    async def list_listeners(self) -> list[Listener]:
        raise NotImplementedError("bruteratel list_listeners() non implémenté")

    async def list_agents(self) -> list[Implant]:
        raise NotImplementedError("bruteratel list_agents() non implémenté")

    async def send_task(self, agent_id: str, command: str, args: list[str] | None = None) -> Task:
        raise NotImplementedError("bruteratel send_task() non implémenté")

    async def get_task_result(self, task_id: str) -> dict[str, Any]:
        raise NotImplementedError("bruteratel get_task_result() non implémenté")

    async def generate_payload(self, config: PayloadConfig) -> bytes:
        raise NotImplementedError("bruteratel generate_payload() non implémenté")

    async def get_capabilities(self) -> list[str]:
        return self.CAPABILITIES
