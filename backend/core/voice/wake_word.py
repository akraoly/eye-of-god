"""
Wake Word Detection locale via openWakeWord
Détecte "Hey AEGIS" (ou variantes) dans le flux audio en temps réel.
Tout traitement est local — aucun audio ne quitte la machine.
"""
from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Callable, Optional

try:
    from core.tools.logger import get_logger
    logger = get_logger("voice.wake")
except Exception:
    import logging
    logger = logging.getLogger(__name__)

MODELS_DIR = Path(__file__).parent.parent.parent / "data" / "voice_models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)

# Seuil de confiance (0-1)
DETECTION_THRESHOLD = 0.5

_oww_model = None
_oww_lock  = threading.Lock()


def _load_oww():
    global _oww_model
    with _oww_lock:
        if _oww_model is not None:
            return _oww_model
        try:
            import openwakeword
            from openwakeword.model import Model as OWWModel
            # Utilise le modèle "hey_jarvis" comme proxy
            # (modèle personnalisé "hey_aegis" peut être ajouté plus tard)
            openwakeword.utils.download_models(["hey_jarvis_v0.1"])
            _oww_model = OWWModel(wakeword_models=["hey_jarvis_v0.1"])
            logger.info("openWakeWord chargé (hey_jarvis proxy)")
        except Exception as e:
            logger.warning("openWakeWord non disponible: %s", e)
            _oww_model = None
    return _oww_model


class WakeWordDetector:
    """
    Détecteur de mot de déclenchement — tourne dans un thread dédié.
    Appelle on_detected() quand le mot de déclenchement est détecté.
    """

    def __init__(self):
        self._active = False
        self._thread: Optional[threading.Thread] = None
        self._callback: Optional[Callable] = None
        self._model = None

    def start(self, on_detected: Callable):
        """Démarre la détection en arrière-plan."""
        if self._active:
            return
        self._callback = on_detected
        self._active = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        logger.info("Wake word detector démarré")

    def stop(self):
        self._active = False
        logger.info("Wake word detector arrêté")

    def _loop(self):
        try:
            import sounddevice as sd
            import numpy as np
            model = _load_oww()

            CHUNK = 1280  # ~80ms à 16kHz
            with sd.InputStream(samplerate=16000, channels=1, dtype="int16", blocksize=CHUNK) as stream:
                logger.info("Wake word: écoute sur le micro système")
                while self._active:
                    audio_chunk, _ = stream.read(CHUNK)
                    if model is not None:
                        audio_np = audio_chunk.flatten().astype(np.float32) / 32768.0
                        scores = model.predict(audio_np)
                        for name, score in scores.items():
                            if score >= DETECTION_THRESHOLD:
                                logger.info("Wake word détecté '%s' (score %.2f)", name, score)
                                if self._callback:
                                    self._callback({"word": name, "score": float(score)})
                                time.sleep(2)   # délai anti-double-déclenchement
        except ImportError:
            logger.warning("sounddevice non disponible — wake word désactivé")
        except Exception as e:
            logger.error("Wake word loop error: %s", e)


# Singleton
wake_detector = WakeWordDetector()


def detect_in_audio(audio_bytes: bytes, chunk_size: int = 1280) -> list[dict]:
    """
    Détecte les wake words dans un buffer audio complet (mode batch).
    Retourne la liste des détections.
    """
    model = _load_oww()
    if model is None:
        return []

    detections = []
    try:
        import numpy as np
        audio_np = (
            np.frombuffer(audio_bytes, dtype=np.int16)
            .astype(np.float32) / 32768.0
        )
        for i in range(0, len(audio_np) - chunk_size, chunk_size):
            chunk = audio_np[i:i + chunk_size]
            scores = model.predict(chunk)
            for name, score in scores.items():
                if score >= DETECTION_THRESHOLD:
                    detections.append({
                        "word": name, "score": float(score),
                        "offset_ms": int(i / 16),
                    })
    except Exception as e:
        logger.error("batch wake word detection error: %s", e)

    return detections
