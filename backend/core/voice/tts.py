"""
TTS — Text-to-Speech local via Piper TTS
Synthèse 100% locale, aucun audio ne quitte la machine.
Fallback vers espeak-ng si Piper non disponible.
"""
from __future__ import annotations

import io
import os
import subprocess
import threading
from pathlib import Path
from typing import Optional

try:
    from core.tools.logger import get_logger
    logger = get_logger("voice.tts")
except Exception:
    import logging
    logger = logging.getLogger(__name__)

MODELS_DIR = Path(__file__).parent.parent.parent / "data" / "voice_models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)

# Voix Piper recommandée pour le français
PIPER_VOICE_FR = "fr_FR-upmc-medium"
PIPER_MODEL_PATH = MODELS_DIR / f"{PIPER_VOICE_FR}.onnx"
PIPER_CONFIG_PATH = MODELS_DIR / f"{PIPER_VOICE_FR}.onnx.json"

_piper_available = None
_piper_lock = threading.Lock()


def _check_piper() -> bool:
    global _piper_available
    if _piper_available is not None:
        return _piper_available
    with _piper_lock:
        if _piper_available is not None:
            return _piper_available
        try:
            # Vérifier piper CLI
            result = subprocess.run(["piper", "--version"], capture_output=True, timeout=5)
            _piper_available = result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            _piper_available = False
        if not _piper_available:
            logger.info("piper CLI absent — utilisation espeak-ng en fallback")
        return _piper_available


def synthesize(text: str, voice: str = PIPER_VOICE_FR, speed: float = 1.0) -> bytes:
    """
    Synthétise du texte en audio WAV (bytes).
    Traitement 100% local — aucune donnée ne sort de la machine.
    """
    if not text.strip():
        return b""

    # Tentative Piper (voix naturelle)
    if _check_piper() and PIPER_MODEL_PATH.exists():
        return _synth_piper(text, speed)

    # Fallback espeak-ng (toujours disponible sur Linux)
    return _synth_espeak(text, speed)


def _synth_piper(text: str, speed: float = 1.0) -> bytes:
    """Synthèse via piper CLI — voix neuronale locale."""
    try:
        result = subprocess.run(
            ["piper", "--model", str(PIPER_MODEL_PATH), "--output-raw"],
            input=text.encode("utf-8"),
            capture_output=True,
            timeout=30,
        )
        if result.returncode == 0:
            return result.stdout
        logger.warning("piper exit %d: %s", result.returncode, result.stderr[:100])
    except subprocess.TimeoutExpired:
        logger.warning("piper: timeout sur '%s'", text[:40])
    except Exception as e:
        logger.error("piper error: %s", e)
    return _synth_espeak(text, speed)


def _synth_espeak(text: str, speed: float = 1.0) -> bytes:
    """Fallback espeak-ng — voix basique mais toujours disponible."""
    try:
        rate = int(175 * speed)
        result = subprocess.run(
            ["espeak-ng", "-v", "fr", "-s", str(rate), "--stdout", text],
            capture_output=True,
            timeout=15,
        )
        if result.returncode == 0:
            return result.stdout
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    except Exception as e:
        logger.error("espeak-ng error: %s", e)
    return b""


def download_piper_voice(voice: str = PIPER_VOICE_FR) -> bool:
    """
    Télécharge le modèle Piper si absent.
    Téléchargement unique depuis Hugging Face.
    """
    onnx_path = MODELS_DIR / f"{voice}.onnx"
    json_path  = MODELS_DIR / f"{voice}.onnx.json"

    if onnx_path.exists() and json_path.exists():
        logger.info("Modèle Piper %s déjà présent", voice)
        return True

    base_url = f"https://huggingface.co/rhasspy/piper-voices/resolve/main/fr/fr_FR/{voice.split('-')[2]}/{voice.replace('fr_FR-', '')}"
    try:
        import urllib.request
        for path, suffix in [(onnx_path, ".onnx"), (json_path, ".onnx.json")]:
            url = f"{base_url}/{voice}{suffix}"
            logger.info("Téléchargement %s…", url)
            urllib.request.urlretrieve(url, str(path))
        logger.info("Modèle Piper %s téléchargé", voice)
        return True
    except Exception as e:
        logger.warning("Impossible de télécharger le modèle Piper: %s", e)
        return False
