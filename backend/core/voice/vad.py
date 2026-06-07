"""
VAD — Voice Activity Detection locale via webrtcvad
Aucune donnée audio ne quitte la machine.
"""
from __future__ import annotations

import struct
from typing import Generator

try:
    import webrtcvad
    _HAS_VAD = True
except ImportError:
    _HAS_VAD = False

try:
    from core.tools.logger import get_logger
    logger = get_logger("voice.vad")
except Exception:
    import logging
    logger = logging.getLogger(__name__)

SAMPLE_RATE  = 16000   # Hz
FRAME_DURATION = 30    # ms — webrtcvad supporte 10|20|30ms
FRAME_SIZE   = int(SAMPLE_RATE * FRAME_DURATION / 1000)   # 480 samples pour 30ms
FRAME_BYTES  = FRAME_SIZE * 2   # int16 = 2 bytes/sample

# Seuil : nombre de frames consécutives silencieuses pour déclarer fin de parole
SILENCE_FRAMES_THRESHOLD = 30   # ~900ms


class VADPipeline:
    """
    Filtre VAD frame-by-frame sur un stream PCM 16-bit 16kHz.
    Yield des chunks audio contenant uniquement de la parole.
    """

    def __init__(self, aggressiveness: int = 2):
        self.aggressiveness = aggressiveness
        self._vad = None
        if _HAS_VAD:
            self._vad = webrtcvad.Vad(aggressiveness)
        else:
            logger.warning("webrtcvad non disponible — VAD désactivé")

    def is_speech(self, frame_bytes: bytes) -> bool:
        if self._vad is None:
            return True   # passthrough si pas de VAD
        if len(frame_bytes) != FRAME_BYTES:
            return False
        try:
            return self._vad.is_speech(frame_bytes, SAMPLE_RATE)
        except Exception:
            return False

    def segment_stream(self, pcm_stream: bytes) -> list[bytes]:
        """
        Découpe un stream PCM en segments de parole.
        Retourne une liste de buffers PCM prêts à transcrire.
        """
        frames = _split_frames(pcm_stream)
        segments: list[bytes] = []
        current: list[bytes] = []
        silence_count = 0

        for frame in frames:
            if self.is_speech(frame):
                current.append(frame)
                silence_count = 0
            else:
                silence_count += 1
                if current:
                    current.append(frame)   # inclure un peu de silence pour meilleure transcription
                if silence_count > SILENCE_FRAMES_THRESHOLD and current:
                    segments.append(b"".join(current))
                    current = []
                    silence_count = 0

        if current:
            segments.append(b"".join(current))

        return segments


def _split_frames(pcm: bytes) -> list[bytes]:
    """Découpe un buffer PCM en frames de FRAME_BYTES."""
    frames = []
    offset = 0
    while offset + FRAME_BYTES <= len(pcm):
        frames.append(pcm[offset:offset + FRAME_BYTES])
        offset += FRAME_BYTES
    return frames


# Instance partagée
vad_pipeline = VADPipeline(aggressiveness=2)
