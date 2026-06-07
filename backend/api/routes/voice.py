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
    """
    Convertit vers PCM WAV 16kHz mono avec :
    - normalisation du volume (afftdn = réduction bruit, loudnorm = volume stable)
    - filtrage passe-haut 80Hz (supprime grondements basse fréquence)
    - normalisation loudness pour STT optimal
    """
    result = subprocess.run(
        [ffmpeg_bin, "-y", "-i", src_path,
         "-ar", "16000", "-ac", "1",
         "-af", "highpass=f=80,afftdn=nf=-25,loudnorm=I=-16:LRA=11:TP=-1.5",
         "-f", "wav", dst_path],
        capture_output=True,
    )
    if result.returncode != 0:
        # Fallback sans filtres si le codec ne les supporte pas
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

        # Étape 2 : analyse de l'énergie vocale (ton, urgence, émotion)
        voice_energy = "normal"
        voice_duration = 0.0
        if ffmpeg_bin:
            try:
                stats = subprocess.run(
                    [ffmpeg_bin, "-i", wav_path, "-af", "astats=metadata=1:reset=1", "-f", "null", "-"],
                    capture_output=True,
                )
                stderr = stats.stderr.decode(errors="replace")
                # Extraire durée et volume RMS
                import re as _re
                dur_m = _re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", stderr)
                rms_m = _re.search(r"RMS level dB:\s*([-\d.]+)", stderr)
                if dur_m:
                    h, m, s = int(dur_m.group(1)), int(dur_m.group(2)), float(dur_m.group(3))
                    voice_duration = h * 3600 + m * 60 + s
                if rms_m:
                    rms = float(rms_m.group(1))
                    if rms > -15:
                        voice_energy = "intense"    # voix forte, urgente
                    elif rms > -25:
                        voice_energy = "normal"
                    else:
                        voice_energy = "calme"      # voix douce, posée
            except Exception:
                pass

        # Étape 3 : reconnaissance vocale
        recognizer = sr.Recognizer()
        with sr.AudioFile(wav_path) as source:
            audio_data = recognizer.record(source)

        try:
            text = recognizer.recognize_google(audio_data, language=language)
            return {
                "text": text,
                "engine": "google",
                "language": language,
                "voice_energy": voice_energy,
                "voice_duration": round(voice_duration, 2),
            }
        except sr.UnknownValueError:
            return {"text": "", "engine": "google", "error": "Audio non reconnu — parle plus près du micro",
                    "voice_energy": voice_energy, "voice_duration": round(voice_duration, 2)}
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
