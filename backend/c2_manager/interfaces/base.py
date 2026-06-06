"""BaseC2Interface — Abstract base class pour toutes les intégrations C2."""
from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from c2_manager.models import (
    C2Config, C2Status, Listener, Implant, Task, PayloadConfig,
)

logger = logging.getLogger(__name__)


class C2Error(Exception):
    """Erreur générique C2."""


class C2ConnectionError(C2Error):
    """Impossible de se connecter au C2."""


class C2AuthError(C2Error):
    """Échec d'authentification."""


class C2NotConnected(C2Error):
    """Opération tentée sans connexion active."""


class BaseC2Interface(ABC):
    """
    Interface abstraite unifiée pour tous les frameworks C2.

    Chaque intégration hérite de cette classe et implémente les méthodes
    abstraites. Les méthodes utilitaires (retry, healthcheck loop, etc.)
    sont fournies ici.
    """

    # Sous-classes peuvent surcharger ces valeurs
    MAX_RETRIES:    int   = 3
    RETRY_BASE_SEC: float = 2.0   # backoff exponentiel : 2^n
    CONNECT_TIMEOUT: float = 10.0

    def __init__(self) -> None:
        self._config:    C2Config | None = None
        self._status:    C2Status = C2Status.DISCONNECTED
        self._connected_at: datetime | None = None
        self._healthcheck_task: asyncio.Task | None = None

    # ── Méthodes abstraites obligatoires ─────────────────────────────────────

    @abstractmethod
    async def connect(self, config: C2Config) -> bool:
        """Ouvrir la connexion / s'authentifier. Retourne True si succès."""

    @abstractmethod
    async def disconnect(self) -> None:
        """Fermer proprement la connexion."""

    @abstractmethod
    async def get_status(self) -> C2Status:
        """Retourner l'état courant (ping / healthcheck)."""

    @abstractmethod
    async def create_listener(self, config: dict[str, Any]) -> Listener:
        """Créer un listener sur le C2."""

    @abstractmethod
    async def remove_listener(self, listener_id: str) -> bool:
        """Supprimer un listener."""

    @abstractmethod
    async def list_listeners(self) -> list[Listener]:
        """Lister tous les listeners actifs."""

    @abstractmethod
    async def list_agents(self) -> list[Implant]:
        """Lister tous les agents/implants connectés."""

    @abstractmethod
    async def send_task(
        self,
        agent_id: str,
        command: str,
        args: list[str] | None = None,
    ) -> Task:
        """Envoyer une tâche à un agent."""

    @abstractmethod
    async def get_task_result(self, task_id: str) -> dict[str, Any]:
        """Récupérer le résultat d'une tâche."""

    @abstractmethod
    async def generate_payload(self, config: PayloadConfig) -> bytes:
        """Générer un payload/implant. Retourne les bytes du fichier."""

    @abstractmethod
    async def get_capabilities(self) -> list[str]:
        """Retourner la liste des capacités supportées par ce C2."""

    # ── Méthodes utilitaires héritées ────────────────────────────────────────

    @property
    def is_connected(self) -> bool:
        return self._status == C2Status.CONNECTED

    def _require_connected(self) -> None:
        if not self.is_connected:
            raise C2NotConnected(
                f"{self.__class__.__name__} n'est pas connecté. "
                "Appelez connect() d'abord."
            )

    async def connect_with_retry(self, config: C2Config) -> bool:
        """connect() avec retry exponentiel."""
        self._status = C2Status.CONNECTING
        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                ok = await asyncio.wait_for(
                    self.connect(config),
                    timeout=self.CONNECT_TIMEOUT,
                )
                if ok:
                    self._status = C2Status.CONNECTED
                    self._connected_at = datetime.utcnow()
                    logger.info(
                        "[%s] Connecté à %s:%s",
                        self.__class__.__name__, config.host, config.port,
                    )
                    return True
            except asyncio.TimeoutError:
                logger.warning(
                    "[%s] Timeout tentative %d/%d",
                    self.__class__.__name__, attempt, self.MAX_RETRIES,
                )
            except C2AuthError:
                self._status = C2Status.ERROR
                raise
            except Exception as exc:
                logger.warning(
                    "[%s] Erreur tentative %d/%d : %s",
                    self.__class__.__name__, attempt, self.MAX_RETRIES, exc,
                )
            if attempt < self.MAX_RETRIES:
                wait = self.RETRY_BASE_SEC ** attempt
                logger.debug("[%s] Retry dans %.1fs…", self.__class__.__name__, wait)
                await asyncio.sleep(wait)

        self._status = C2Status.ERROR
        raise C2ConnectionError(
            f"{self.__class__.__name__} : impossible de se connecter à "
            f"{config.host}:{config.port} après {self.MAX_RETRIES} tentatives."
        )

    async def start_healthcheck(self, interval: float = 30.0) -> None:
        """Démarrer un healthcheck périodique en arrière-plan."""
        if self._healthcheck_task and not self._healthcheck_task.done():
            return
        self._healthcheck_task = asyncio.create_task(
            self._healthcheck_loop(interval)
        )

    async def stop_healthcheck(self) -> None:
        if self._healthcheck_task:
            self._healthcheck_task.cancel()
            try:
                await self._healthcheck_task
            except asyncio.CancelledError:
                pass

    async def _healthcheck_loop(self, interval: float) -> None:
        while True:
            await asyncio.sleep(interval)
            try:
                st = await self.get_status()
                if st != C2Status.CONNECTED and self._status == C2Status.CONNECTED:
                    logger.warning(
                        "[%s] Perte de connexion détectée, tentative reconnexion…",
                        self.__class__.__name__,
                    )
                    self._status = C2Status.DISCONNECTED
                    if self._config:
                        try:
                            await self.connect_with_retry(self._config)
                        except C2Error:
                            pass
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.debug("[%s] Healthcheck erreur : %s", self.__class__.__name__, exc)

    def __repr__(self) -> str:
        cfg = f"{self._config.host}:{self._config.port}" if self._config else "unconfigured"
        return f"<{self.__class__.__name__} [{self._status}] {cfg}>"
