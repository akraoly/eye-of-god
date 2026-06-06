"""ExternalC2Interface — protocole External C2 (Cobalt Strike, Havoc, BruteRatel)."""
from __future__ import annotations

import asyncio
import logging
import struct
from typing import Any

from c2_manager.interfaces.base import BaseC2Interface, C2ConnectionError
from c2_manager.models import C2Config, C2Status

logger = logging.getLogger(__name__)

# Frame types External C2 (Cobalt Strike spec)
FRAME_STAGE    = 0x00   # Données du stager
FRAME_TASK     = 0x01   # Tâche pour le beacon
FRAME_RESPONSE = 0x02   # Réponse du beacon
FRAME_PING     = 0x03   # Keepalive


def pack_frame(frame_type: int, data: bytes) -> bytes:
    """[4-byte length][1-byte type][data]"""
    return struct.pack(">I", len(data)) + bytes([frame_type]) + data


def unpack_frame(buf: bytes) -> tuple[int, bytes]:
    """Retourne (type, data) depuis un buffer complet."""
    if len(buf) < 5:
        raise ValueError("Buffer trop court pour un frame")
    length = struct.unpack(">I", buf[:4])[0]
    ftype  = buf[4]
    data   = buf[5:5 + length]
    return ftype, data


class ExternalC2Interface(BaseC2Interface):
    """
    Base pour le protocole External C2 — connexion TCP raw au teamserver.
    Cobalt Strike External C2 spec :
      - Connexion TCP vers le port External C2 du teamserver
      - Réception du stage (FRAME_STAGE), transmission au beacon
      - Polling loop : beacon → FRAME_RESPONSE, C2 → FRAME_TASK
    """

    def __init__(self) -> None:
        super().__init__()
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._poll_task: asyncio.Task | None = None

    async def _tcp_connect(self, host: str, port: int) -> None:
        try:
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=self.CONNECT_TIMEOUT,
            )
        except (asyncio.TimeoutError, OSError) as exc:
            raise C2ConnectionError(
                f"Connexion TCP échouée vers {host}:{port} : {exc}"
            ) from exc

    async def _send_frame(self, frame_type: int, data: bytes) -> None:
        if not self._writer:
            raise C2ConnectionError("Writer TCP non initialisé")
        self._writer.write(pack_frame(frame_type, data))
        await self._writer.drain()

    async def _recv_frame(self) -> tuple[int, bytes]:
        if not self._reader:
            raise C2ConnectionError("Reader TCP non initialisé")
        header = await asyncio.wait_for(self._reader.readexactly(5), timeout=30.0)
        length = struct.unpack(">I", header[:4])[0]
        ftype  = header[4]
        data   = await asyncio.wait_for(
            self._reader.readexactly(length), timeout=60.0
        )
        return ftype, data

    async def disconnect(self) -> None:
        await self.stop_healthcheck()
        if self._poll_task:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
        if self._writer:
            self._writer.close()
            try:
                await self._writer.wait_closed()
            except Exception:
                pass
        self._reader = self._writer = None
        self._status = C2Status.DISCONNECTED

    async def get_status(self) -> C2Status:
        if not self._writer or self._writer.is_closing():
            return C2Status.DISCONNECTED
        try:
            await self._send_frame(FRAME_PING, b"ping")
            return C2Status.CONNECTED
        except Exception:
            return C2Status.ERROR
