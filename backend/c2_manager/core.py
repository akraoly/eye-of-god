"""
C2ManagerEngine — Singleton orchestrateur de tous les C2.

Fonctionnalités :
  - Enregistrement dynamique de n'importe quel C2 (C2Config)
  - connect/disconnect/status par instance nommée
  - API unifiée : list_agents, send_task, create_listener, generate_payload
  - Healthchecks périodiques + reconnexion automatique
  - File de tâches pendantes (si C2 offline)
  - Publication d'événements via EventBus
  - Dashboard GET /c2/status → état de tous les C2

Usage :
    from c2_manager.core import c2_engine

    await c2_engine.register(C2Config(name="sliver-ops", c2_type=C2Type.SLIVER, ...))
    await c2_engine.connect("sliver-ops")
    agents = await c2_engine.list_agents("sliver-ops")
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

from c2_manager.integrations import C2_REGISTRY
from c2_manager.interfaces   import BaseC2Interface, C2Error, C2ConnectionError
from c2_manager.models        import C2Config, C2Status, Listener, Implant, Task, PayloadConfig
from c2_manager.webhooks.event_bus import event_bus, EventType

logger = logging.getLogger(__name__)


class _PendingTask:
    def __init__(
        self,
        c2_name:  str,
        agent_id: str,
        command:  str,
        args:     list[str],
    ) -> None:
        self.c2_name  = c2_name
        self.agent_id = agent_id
        self.command  = command
        self.args     = args
        self.queued_at = datetime.utcnow()


class C2ManagerEngine:
    """
    Singleton orchestrateur de tous les frameworks C2.
    À instancier une seule fois : c2_engine = C2ManagerEngine()
    """

    def __init__(self) -> None:
        # name → (config, interface_instance)
        self._instances: dict[str, tuple[C2Config, BaseC2Interface]] = {}
        # Tâches en attente par instance
        self._pending:   dict[str, asyncio.Queue[_PendingTask]] = {}
        # Flush tasks (background)
        self._flush_tasks: dict[str, asyncio.Task] = {}

    # ── Enregistrement ────────────────────────────────────────────────────────

    def register(self, config: C2Config) -> BaseC2Interface:
        """
        Enregistrer une instance C2 sans la connecter.
        Retourne l'interface créée.
        """
        if config.name in self._instances:
            logger.warning("C2Engine : instance '%s' déjà enregistrée, remplacement", config.name)

        cls = C2_REGISTRY.get(config.c2_type)
        if not cls:
            raise ValueError(f"Type C2 inconnu : {config.c2_type}")

        instance = cls()
        self._instances[config.name] = (config, instance)
        self._pending[config.name]   = asyncio.Queue()
        logger.info("C2Engine : '%s' [%s] enregistré", config.name, config.c2_type)
        return instance

    def unregister(self, name: str) -> None:
        """Déconnecter et supprimer une instance."""
        if name in self._instances:
            del self._instances[name]
        if name in self._pending:
            del self._pending[name]
        if name in self._flush_tasks:
            self._flush_tasks[name].cancel()
        logger.info("C2Engine : '%s' désenregistré", name)

    # ── Connexion ────────────────────────────────────────────────────────────

    async def connect(self, name: str) -> bool:
        """Connecter une instance enregistrée."""
        config, instance = self._get(name)
        try:
            ok = await instance.connect_with_retry(config)
            if ok:
                await event_bus.publish(EventType.C2_CONNECTED, name, {
                    "host": config.host, "port": config.port,
                })
                await instance.start_healthcheck(interval=30.0)
                self._start_flush_task(name)
            return ok
        except C2ConnectionError as exc:
            await event_bus.publish(EventType.C2_ERROR, name, {"error": str(exc)})
            raise

    async def disconnect(self, name: str) -> None:
        """Déconnecter proprement."""
        _, instance = self._get(name)
        await instance.disconnect()
        await event_bus.publish(EventType.C2_DISCONNECTED, name, {})
        if name in self._flush_tasks:
            self._flush_tasks[name].cancel()

    async def reconnect(self, name: str) -> bool:
        """Forcer une reconnexion."""
        await self.disconnect(name)
        return await self.connect(name)

    # ── Status dashboard ──────────────────────────────────────────────────────

    async def status_all(self) -> dict[str, Any]:
        """Retourne l'état de tous les C2 enregistrés."""
        result: dict[str, Any] = {}
        for name, (config, instance) in self._instances.items():
            try:
                st = await asyncio.wait_for(instance.get_status(), timeout=5.0)
            except Exception:
                st = C2Status.ERROR
            result[name] = {
                "c2_type":       config.c2_type,
                "host":          config.host,
                "port":          config.port,
                "status":        st,
                "connected_at":  instance._connected_at.isoformat() if instance._connected_at else None,
                "pending_tasks": self._pending.get(name, asyncio.Queue()).qsize(),
            }
        return result

    async def status(self, name: str) -> dict[str, Any]:
        config, instance = self._get(name)
        try:
            st = await asyncio.wait_for(instance.get_status(), timeout=5.0)
        except Exception:
            st = C2Status.ERROR
        return {
            "name":          name,
            "c2_type":       config.c2_type,
            "host":          config.host,
            "port":          config.port,
            "status":        st,
            "connected_at":  instance._connected_at.isoformat() if instance._connected_at else None,
            "capabilities":  await instance.get_capabilities(),
        }

    # ── API unifiée ───────────────────────────────────────────────────────────

    async def list_listeners(self, name: str) -> list[Listener]:
        _, instance = self._get(name)
        instance._require_connected()
        return await instance.list_listeners()

    async def create_listener(self, name: str, config: dict[str, Any]) -> Listener:
        _, instance = self._get(name)
        instance._require_connected()
        listener = await instance.create_listener(config)
        await event_bus.publish(EventType.LISTENER_STARTED, name, {
            "listener_id": listener.id,
            "protocol":    listener.protocol,
            "port":        listener.bind_port,
        })
        return listener

    async def remove_listener(self, name: str, listener_id: str) -> bool:
        _, instance = self._get(name)
        instance._require_connected()
        ok = await instance.remove_listener(listener_id)
        if ok:
            await event_bus.publish(EventType.LISTENER_STOPPED, name, {"listener_id": listener_id})
        return ok

    async def list_agents(self, name: str) -> list[Implant]:
        _, instance = self._get(name)
        instance._require_connected()
        return await instance.list_agents()

    async def list_all_agents(self) -> dict[str, list[Implant]]:
        """Tous les agents de tous les C2 connectés."""
        result: dict[str, list[Implant]] = {}
        for name, (_, instance) in self._instances.items():
            if instance.is_connected:
                try:
                    result[name] = await instance.list_agents()
                except Exception as exc:
                    logger.warning("list_all_agents [%s] : %s", name, exc)
                    result[name] = []
        return result

    async def send_task(
        self,
        name:     str,
        agent_id: str,
        command:  str,
        args:     list[str] | None = None,
    ) -> Task:
        _, instance = self._get(name)
        if not instance.is_connected:
            # Mettre en file d'attente
            pending = _PendingTask(name, agent_id, command, args or [])
            await self._pending[name].put(pending)
            logger.warning(
                "C2Engine : [%s] hors-ligne, tâche mise en attente (queue=%d)",
                name, self._pending[name].qsize(),
            )
            from c2_manager.models.task import Task as TaskModel
            return TaskModel(
                id="pending",
                agent_id=agent_id,
                c2_type=name,
                command=command,
                args=args or [],
                status="queued",
            )

        task = await instance.send_task(agent_id, command, args)
        await event_bus.publish(EventType.TASK_SENT, name, {
            "task_id":  task.id,
            "agent_id": agent_id,
            "command":  command,
        })
        return task

    async def get_task_result(self, name: str, task_id: str) -> dict[str, Any]:
        _, instance = self._get(name)
        instance._require_connected()
        return await instance.get_task_result(task_id)

    async def generate_payload(self, name: str, config: PayloadConfig) -> bytes:
        _, instance = self._get(name)
        instance._require_connected()
        payload_bytes = await instance.generate_payload(config)
        await event_bus.publish(EventType.PAYLOAD_GENERATED, name, {
            "payload_name": config.name,
            "format":       config.format,
            "os":           config.os,
            "size":         len(payload_bytes),
        })
        return payload_bytes

    # ── File d'attente ────────────────────────────────────────────────────────

    def _start_flush_task(self, name: str) -> None:
        """Démarre la tâche de flush en arrière-plan pour une instance."""
        if name in self._flush_tasks and not self._flush_tasks[name].done():
            return
        self._flush_tasks[name] = asyncio.create_task(self._flush_pending(name))

    async def _flush_pending(self, name: str) -> None:
        """Tente de rejouer les tâches en attente quand le C2 est de retour."""
        queue = self._pending.get(name)
        if not queue:
            return
        while True:
            await asyncio.sleep(5.0)
            if queue.empty():
                continue
            _, instance = self._instances.get(name, (None, None))
            if not instance or not instance.is_connected:
                continue
            while not queue.empty():
                pending = await queue.get()
                try:
                    task = await instance.send_task(
                        pending.agent_id, pending.command, pending.args
                    )
                    logger.info(
                        "C2Engine : tâche en attente exécutée [%s] : %s",
                        name, pending.command,
                    )
                except Exception as exc:
                    logger.error("C2Engine flush erreur [%s] : %s", name, exc)
                    await queue.put(pending)  # remettre en queue
                    break

    # ── Helpers internes ──────────────────────────────────────────────────────

    def _get(self, name: str) -> tuple[C2Config, BaseC2Interface]:
        if name not in self._instances:
            raise KeyError(f"Instance C2 '{name}' non enregistrée")
        return self._instances[name]

    def list_registered(self) -> list[str]:
        return list(self._instances.keys())

    def get_instance(self, name: str) -> BaseC2Interface:
        return self._get(name)[1]

    def get_config(self, name: str) -> C2Config:
        return self._get(name)[0]


# ── Singleton global ──────────────────────────────────────────────────────────
c2_engine = C2ManagerEngine()
