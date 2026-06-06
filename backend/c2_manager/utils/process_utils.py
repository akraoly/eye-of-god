"""Utilitaires processus — démarrage, monitoring, logs."""
from __future__ import annotations

import asyncio
import logging
import os
import shlex
import subprocess
from collections import deque
from typing import Any

logger = logging.getLogger(__name__)


class ManagedProcess:
    """Processus fils géré avec capture de logs."""

    def __init__(self, name: str, cmd: str | list[str], **popen_kwargs: Any) -> None:
        self.name = name
        self.cmd  = cmd
        self._proc: subprocess.Popen | None = None
        self._logs: deque[str] = deque(maxlen=500)
        self._log_thread = None
        self._kwargs = popen_kwargs

    def start(self) -> bool:
        if self.is_running:
            logger.warning("%s : déjà en cours", self.name)
            return True
        cmd = shlex.split(self.cmd) if isinstance(self.cmd, str) else self.cmd
        try:
            self._proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                **self._kwargs,
            )
            self._start_log_capture()
            logger.info("%s : démarré (pid=%d)", self.name, self._proc.pid)
            return True
        except FileNotFoundError:
            logger.error("%s : commande introuvable : %s", self.name, cmd[0])
            return False

    def _start_log_capture(self) -> None:
        import threading
        def _read():
            for line in self._proc.stdout:
                self._logs.append(line.rstrip())
        self._log_thread = threading.Thread(target=_read, daemon=True)
        self._log_thread.start()

    def stop(self, timeout: int = 10) -> bool:
        if not self._proc:
            return True
        try:
            self._proc.terminate()
            self._proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            self._proc.kill()
        self._proc = None
        logger.info("%s : arrêté", self.name)
        return True

    @property
    def is_running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    @property
    def pid(self) -> int | None:
        return self._proc.pid if self._proc else None

    def logs(self, n: int = 50) -> list[str]:
        return list(self._logs)[-n:]


def port_is_open(host: str, port: int, timeout: float = 2.0) -> bool:
    """Vérifie si un port TCP est ouvert."""
    import socket
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (OSError, TimeoutError):
        return False


async def wait_for_port(
    host: str,
    port: int,
    timeout: float = 30.0,
    interval: float = 0.5,
) -> bool:
    """Attend qu'un port TCP soit accessible."""
    import time
    start = time.monotonic()
    while time.monotonic() - start < timeout:
        if port_is_open(host, port):
            return True
        await asyncio.sleep(interval)
    return False
