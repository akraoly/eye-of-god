"""
STT — Speech-to-Text local via faster-whisper
Tout traitement est local. Aucun audio ne quitte la machine.
"""
from __future__ import annotations

import io
import threading
import time
from pathlib import Path
from typing import Optional

try:
    from core.tools.logger import get_logger
    logger = get_logger("voice.stt")
except Exception:
    import logging
    logger = logging.getLogger(__name__)

_model = None
_model_lock = threading.Lock()

MODELS_DIR = Path(__file__).parent.parent.parent / "data" / "voice_models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_MODEL = "small"   # tiny|base|small|medium|large


def _ensure_model_downloaded(model_size: str = DEFAULT_MODEL):
    """Télécharge le modèle si absent (au 1er appel seulement)."""
    try:
        from faster_whisper import download_model as _dl
        model_path = MODELS_DIR / f"models--Systran--faster-whisper-{model_size}"
        if not model_path.exists():
            logger.info("[Voice] Téléchargement modèle Whisper '%s' — patience...", model_size)
            _dl(model_size, cache_dir=str(MODELS_DIR))
            logger.info("[Voice] Modèle Whisper '%s' téléchargé", model_size)
    except Exception as e:
        logger.warning("[Voice] Téléchargement Whisper optionnel échoué: %s", e)


def _load_model(model_size: str = DEFAULT_MODEL):
    global _model
    with _model_lock:
        if _model is not None:
            return _model
        try:
            _ensure_model_downloaded(model_size)
            from faster_whisper import WhisperModel
            logger.info("Chargement Whisper %s (local, CPU)…", model_size)
            t0 = time.time()
            _model = WhisperModel(
                model_size,
                device="cpu",
                compute_type="int8",
                download_root=str(MODELS_DIR),
            )
            logger.info("Whisper chargé en %.1fs", time.time() - t0)
        except Exception as e:
            logger.error("Erreur chargement Whisper: %s", e)
            _model = None
    return _model


def transcribe_audio(
    audio_bytes: bytes,
    language: str = "fr",
    model_size: str = DEFAULT_MODEL,
) -> dict:
    """
    Transcrit un buffer PCM 16-bit 16kHz.
    Retourne { text, language, duration, segments }.
    Tout se passe en local — aucune donnée n'est envoyée à l'extérieur.
    """
    model = _load_model(model_size)
    if model is None:
        return {"text": "", "error": "Modèle Whisper non disponible"}

    try:
        import numpy as np
        # Convertir PCM16 → float32 normalisé
        audio_np = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0

        t0 = time.time()
        segments_gen, info = model.transcribe(
            audio_np,
            language=language,
            beam_size=5,
            condition_on_previous_text=False,
            vad_filter=True,
        )
        segments = list(segments_gen)
        text = " ".join(s.text.strip() for s in segments).strip()
        elapsed = time.time() - t0

        logger.debug("STT: '%s' (%.1fs, lang=%s)", text[:60], elapsed, info.language)
        return {
            "text": text,
            "language": info.language,
            "duration": round(info.duration, 2),
            "transcription_time": round(elapsed, 3),
            "segments": [{"start": s.start, "end": s.end, "text": s.text.strip()} for s in segments],
        }
    except Exception as e:
        logger.error("Transcription error: %s", e)
        return {"text": "", "error": str(e)}


def preload_model(model_size: str = DEFAULT_MODEL):
    """Précharge le modèle en arrière-plan au démarrage."""
    threading.Thread(target=_load_model, args=(model_size,), daemon=True).start()
