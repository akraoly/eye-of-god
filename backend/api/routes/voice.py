"""
Routes /api/voice — STT + TTS + WebSocket pipeline vocal local.
- /transcribe   : transcription Google (legacy)
- /local/transcribe : faster-whisper 100% local
- /local/tts    : Piper TTS ou espeak-ng local
- /ws/stream    : WebSocket STT temps réel (PCM → Whisper → JSON)
- /status       : état des moteurs
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
    """Conversion rapide vers PCM WAV 16kHz mono — filtre léger uniquement."""
    result = subprocess.run(
        [ffmpeg_bin, "-y", "-i", src_path,
         "-ar", "16000", "-ac", "1",
         "-af", "highpass=f=80",   # filtre léger (~10ms) — supprime grondements
         "-f", "wav", dst_path],
        capture_output=True,
    )
    if result.returncode != 0:
        result = subprocess.run(
            [ffmpeg_bin, "-y", "-i", src_path,
             "-ar", "16000", "-ac", "1", "-f", "wav", dst_path],
            capture_output=True,
        )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.decode(errors="replace")[-400:])


def _wav_energy(wav_path: str):
    """Calcule RMS et durée depuis le WAV en Python pur — pas de 2ème processus."""
    import wave, struct, math
    try:
        with wave.open(wav_path, 'rb') as w:
            frames = w.getnframes()
            rate   = w.getframerate()
            raw    = w.readframes(frames)
        duration = frames / rate
        samples  = struct.unpack('<' + 'h' * (len(raw) // 2), raw)
        if not samples:
            return "normal", 0.0
        rms_linear = math.sqrt(sum(s * s for s in samples) / len(samples))
        rms_db = 20 * math.log10(max(rms_linear, 1) / 32768)
        if rms_db > -15:
            energy = "intense"
        elif rms_db > -28:
            energy = "normal"
        else:
            energy = "calme"
        return energy, round(duration, 2)
    except Exception:
        return "normal", 0.0


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

        # Étape 2 : énergie vocale via Python pur (pas de 2ème process ffmpeg)
        voice_energy, voice_duration = _wav_energy(wav_path)

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
    tts_ok = False
    try:
        import edge_tts  # noqa
        tts_ok = True
    except ImportError:
        pass

    return {
        "status": "online",
        "ffmpeg": ffmpeg_bin or "non trouvé",
        "stt_google": stt_ok,
        "tts_backend": tts_ok,
        "tts_voice": "fr-FR-HenriNeural (Male)",
        "stt_pipeline": "expo-av → m4a → ffmpeg 16kHz PCM WAV → Google STT",
    }


# ── TTS backend — voix masculine Henri (Microsoft Neural) ─────────────────────
from fastapi import Request as FastAPIRequest
from fastapi.responses import StreamingResponse as _StreamingResponse
from pydantic import BaseModel as _BaseModel


class TTSRequest(_BaseModel):
    text: str
    voice: str = "fr-FR-HenriNeural"   # voix masculine par défaut
    rate: str  = "+20%"                 # +20 % = rate 1.20
    pitch: str = "-10Hz"                # légèrement plus grave


@router.post("/tts")
async def backend_tts(req: TTSRequest):
    """
    Synthèse vocale backend via edge-tts (Microsoft Neural).
    Retourne un flux MP3 directement jouable côté client.
    Voix masculine : fr-FR-HenriNeural ou fr-FR-RemyMultilingualNeural.
    """
    try:
        import edge_tts
    except ImportError:
        raise HTTPException(status_code=503, detail="edge-tts non installé")

    text = req.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Texte vide")

    communicate = edge_tts.Communicate(text, req.voice, rate=req.rate, pitch=req.pitch)

    async def audio_stream():
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                yield chunk["data"]

    return _StreamingResponse(
        audio_stream(),
        media_type="audio/mpeg",
        headers={"Cache-Control": "no-cache"},
    )


# ════════════════════════════════════════════════════════════════════════════════
# Routes locales — Whisper STT + Piper TTS (100% offline)
# Aucun audio ne quitte jamais la machine.
# ════════════════════════════════════════════════════════════════════════════════

from fastapi import WebSocket, WebSocketDisconnect, Query
from fastapi.responses import Response as _Response
import json as _json


@router.post("/local/transcribe")
async def local_transcribe(
    file: UploadFile = File(...),
    language: str = "fr",
    model: str = "small",
):
    """
    Transcription 100% locale via faster-whisper.
    Accepte PCM WAV 16kHz mono ou tout format ffmpeg.
    Aucun audio ne quitte la machine.
    """
    from core.voice.stt import transcribe_audio
    from core.voice.intent import classify_intent

    content = await file.read()

    # Conversion ffmpeg → PCM 16kHz mono si nécessaire
    ffmpeg_bin = _get_ffmpeg()
    pcm_bytes = content
    if ffmpeg_bin and not file.filename.endswith(".pcm"):
        import tempfile as _tmpmod
        suffix = os.path.splitext(file.filename or "audio.bin")[1].lower() or ".bin"
        with _tmpmod.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(content); src_path = tmp.name
        wav_path = src_path + "_16k.wav"
        try:
            _to_pcm_wav(src_path, wav_path, ffmpeg_bin)
            with open(wav_path, "rb") as f:
                pcm_bytes = f.read()
        except Exception:
            pcm_bytes = content
        finally:
            for p in [src_path, wav_path]:
                try: os.unlink(p)
                except Exception: pass

    result = transcribe_audio(pcm_bytes, language=language, model_size=model)
    if result.get("text"):
        result["intent"] = classify_intent(result["text"])
    return result


@router.post("/local/tts")
async def local_tts(req: TTSRequest):
    """
    Synthèse vocale 100% locale via Piper TTS ou espeak-ng.
    Aucune donnée ne quitte la machine.
    Retourne un flux WAV/PCM jouable directement.
    """
    from core.voice.tts import synthesize
    text = req.text.strip()
    if not text:
        raise HTTPException(400, "Texte vide")
    audio = synthesize(text, speed=1.0)
    if not audio:
        raise HTTPException(503, "Synthèse vocale locale indisponible")
    # Détecter le format (WAV si espeak produit un WAV)
    media = "audio/wav" if audio[:4] == b"RIFF" else "audio/x-raw"
    return _Response(content=audio, media_type=media)


@router.get("/local/status")
def local_voice_status():
    """État du pipeline vocal local."""
    import shutil
    whisper_ok = False
    try:
        from faster_whisper import WhisperModel
        whisper_ok = True
    except ImportError:
        pass

    piper_ok = bool(shutil.which("piper"))
    espeak_ok = bool(shutil.which("espeak-ng"))
    vad_ok = False
    try:
        import webrtcvad; vad_ok = True
    except ImportError:
        pass
    wake_ok = False
    try:
        import openwakeword; wake_ok = True
    except ImportError:
        pass

    return {
        "whisper":     {"available": whisper_ok, "model": "small", "backend": "cpu/int8"},
        "piper_tts":   {"available": piper_ok},
        "espeak_tts":  {"available": espeak_ok},
        "webrtcvad":   {"available": vad_ok},
        "openwakeword":{"available": wake_ok},
        "local_only":  True,
        "audio_exits_machine": False,
    }


@router.websocket("/ws/stream")
async def voice_stream_ws(
    websocket: WebSocket,
    token: str = Query(""),
    language: str = Query("fr"),
    model: str = Query("small"),
):
    """
    WebSocket STT temps réel.
    Client envoie des chunks PCM 16-bit 16kHz, serveur retourne du JSON.

    Protocole :
    - Client → binaire : chunk PCM (n × 2 bytes, 16kHz)
    - Client → text JSON : { "cmd": "transcribe" } pour forcer la transcription
    - Serveur → text JSON : { "type": "partial"|"final"|"command"|"error", ... }
    """
    from core.auth.jwt_handler import decode_access_token
    from core.voice.stt import transcribe_audio
    from core.voice.vad import vad_pipeline, FRAME_BYTES
    from core.voice.intent import classify_intent, handle_voice_command

    # Authentification WebSocket
    try:
        decode_access_token(token)
    except Exception:
        await websocket.close(code=4001)
        return

    await websocket.accept()
    buffer = bytearray()
    silence_frames = 0
    SILENCE_THRESHOLD = 25   # ~750ms de silence → transcription auto
    MIN_SPEECH_BYTES = FRAME_BYTES * 10  # au moins ~300ms de parole

    try:
        while True:
            data = await websocket.receive()

            # Chunk PCM binaire
            if "bytes" in data and data["bytes"]:
                chunk = data["bytes"]
                buffer.extend(chunk)

                # VAD frame-par-frame
                for i in range(0, len(chunk) - FRAME_BYTES + 1, FRAME_BYTES):
                    frame = chunk[i:i + FRAME_BYTES]
                    if vad_pipeline.is_speech(frame):
                        silence_frames = 0
                    else:
                        silence_frames += 1

                # Auto-transcription si silence prolongé et buffer assez long
                if silence_frames >= SILENCE_THRESHOLD and len(buffer) >= MIN_SPEECH_BYTES:
                    pcm_copy = bytes(buffer)
                    buffer.clear()
                    silence_frames = 0

                    result = transcribe_audio(pcm_copy, language=language, model_size=model)
                    text = result.get("text", "")

                    if text:
                        intent = classify_intent(text)
                        response = {
                            "type":   "final",
                            "text":   text,
                            "intent": intent,
                            "duration": result.get("duration"),
                            "transcription_time": result.get("transcription_time"),
                        }
                        # Commandes vocales système
                        if intent.get("intent") == "voice_command":
                            cmd_resp = handle_voice_command(intent["command"])
                            response["voice_response"] = cmd_resp
                        await websocket.send_text(_json.dumps(response))
                    else:
                        await websocket.send_text(_json.dumps({"type": "silence"}))

            # Commande texte JSON
            elif "text" in data and data["text"]:
                try:
                    msg = _json.loads(data["text"])
                    cmd = msg.get("cmd")

                    if cmd == "transcribe" and len(buffer) >= MIN_SPEECH_BYTES:
                        pcm_copy = bytes(buffer)
                        buffer.clear()
                        result = transcribe_audio(pcm_copy, language=language, model_size=model)
                        text = result.get("text", "")
                        intent = classify_intent(text) if text else {}
                        await websocket.send_text(_json.dumps({
                            "type": "final", "text": text, "intent": intent
                        }))

                    elif cmd == "clear":
                        buffer.clear(); silence_frames = 0
                        await websocket.send_text(_json.dumps({"type": "cleared"}))

                    elif cmd == "ping":
                        await websocket.send_text(_json.dumps({"type": "pong"}))

                except Exception:
                    await websocket.send_text(_json.dumps({"type": "error", "message": "Message invalide"}))

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_text(_json.dumps({"type": "error", "message": str(e)}))
        except Exception:
            pass
