"""
Routes /api/voice — Transcription audio (STT) + synthèse vocale (TTS côté backend).
"""
from fastapi import APIRouter, UploadFile, File, HTTPException
from typing import Optional
import tempfile, os, subprocess

router = APIRouter()

# ── Résolution ffmpeg (binary bundlé via imageio-ffmpeg) ───────────────────
def _get_ffmpeg():
    try:
        import imageio_ffmpeg
        path = imageio_ffmpeg.get_ffmpeg_exe()
        if os.path.isfile(path):
            return path
    except ImportError:
        pass
    for candidate in ["ffmpeg", "/usr/bin/ffmpeg", "/usr/local/bin/ffmpeg"]:
        try:
            subprocess.run([candidate, "-version"], capture_output=True, check=True)
            return candidate
        except (FileNotFoundError, subprocess.CalledProcessError):
            pass
    return None


def _to_pcm_wav(src_path: str, dst_path: str, ffmpeg_bin: str) -> None:
    """Convertit n'importe quel format audio en PCM WAV 16kHz mono via ffmpeg."""
    result = subprocess.run(
        [ffmpeg_bin, "-y", "-i", src_path,
         "-ar", "16000", "-ac", "1", "-f", "wav", dst_path],
        capture_output=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.decode(errors="replace")[-400:])


@router.post("/transcribe")
async def transcribe_audio(
    file: UploadFile = File(...),
    language: str = "fr-FR",
):
    """
    Transcrit un fichier audio en texte.
    Accepte tout format supporté par ffmpeg (WAV, M4A, MP3, AAC, WEBM, OGG, 3GP…).
    """
    try:
        import speech_recognition as sr
    except ImportError:
        raise HTTPException(status_code=500, detail="SpeechRecognition non installé")

    ffmpeg_bin = _get_ffmpeg()

    # Sauvegarder l'upload
    suffix = os.path.splitext(file.filename or "audio.bin")[1].lower() or ".bin"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        content = await file.read()
        tmp.write(content)
        src_path = tmp.name

    wav_path = src_path + "_converted.wav"
    try:
        # Étape 1 : conversion vers PCM WAV 16kHz (toujours, même pour .wav entrants)
        if ffmpeg_bin:
            try:
                _to_pcm_wav(src_path, wav_path, ffmpeg_bin)
            except RuntimeError as e:
                raise HTTPException(status_code=422, detail=f"Conversion audio échouée : {e}")
        else:
            # Pas de ffmpeg : espère que le fichier est déjà PCM WAV
            wav_path = src_path

        # Étape 2 : reconnaissance vocale
        recognizer = sr.Recognizer()
        with sr.AudioFile(wav_path) as source:
            audio_data = recognizer.record(source)

        try:
            text = recognizer.recognize_google(audio_data, language=language)
            return {"text": text, "engine": "google", "language": language}
        except sr.UnknownValueError:
            return {"text": "", "engine": "google", "error": "Audio non reconnu — parle plus près du micro"}
        except sr.RequestError as e:
            raise HTTPException(status_code=503, detail=f"Service Google STT indisponible : {e}")

    finally:
        for p in [src_path, wav_path]:
            try:
                if os.path.exists(p):
                    os.unlink(p)
            except Exception:
                pass


@router.get("/status")
def voice_status():
    """Vérifie la disponibilité des services voix."""
    ffmpeg_bin = _get_ffmpeg()
    stt_ok = False
    try:
        import speech_recognition
        stt_ok = True
    except ImportError:
        pass

    return {
        "status": "online",
        "ffmpeg": ffmpeg_bin or "non trouvé",
        "stt_google": stt_ok,
        "tts_client": "expo-speech (mobile) / SpeechSynthesis (web)",
        "stt_pipeline": "expo-av → m4a → ffmpeg 16kHz PCM WAV → Google STT",
    }
