"""
Routes /api/sdr — Software Defined Radio operations.
Hardware detection, frequency scan, listen, IQ capture, decode, replay, spectrum, gate detect, jam.
"""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.auth.dependencies import get_current_user
from database.db import get_db
from database.models_sdr import SDRRecording
from services.sdr.sdr_service import SDRService

router = APIRouter()
sdr_service = SDRService()

# In-memory task store for async scan results
_scan_tasks: dict[str, Any] = {}


# ── Pydantic Models ───────────────────────────────────────────────────────────

class ScanRequest(BaseModel):
    start_mhz: float = Field(default=88.0, ge=0.1, le=6000.0)
    end_mhz: float = Field(default=108.0, ge=0.1, le=6000.0)
    step_hz: int = Field(default=10000, ge=1000)
    gain: int = Field(default=40, ge=0, le=60)


class ListenRequest(BaseModel):
    frequency_mhz: float = Field(..., ge=0.1, le=6000.0)
    modulation: str = Field(default="fm")
    duration: int = Field(default=10, ge=1, le=300)
    gain: int = Field(default=40, ge=0, le=60)


class CaptureIQRequest(BaseModel):
    frequency_mhz: float = Field(..., ge=0.1, le=6000.0)
    sample_rate: int = Field(default=2_000_000, ge=250_000)
    duration: int = Field(default=5, ge=1, le=60)


class ReplayRequest(BaseModel):
    frequency_mhz: float = Field(..., ge=0.1, le=6000.0)
    repeat: int = Field(default=1, ge=1, le=10)


class GateDetectRequest(BaseModel):
    frequency_mhz: float = Field(default=433.92, ge=0.1, le=6000.0)


class JamRequest(BaseModel):
    frequency_mhz: float = Field(..., ge=0.1, le=6000.0)
    duration: int = Field(default=5, ge=1, le=60)
    authorized: bool = Field(default=False)


# ── Hardware ──────────────────────────────────────────────────────────────────

@router.get("/hardware")
async def get_hardware(
    _user=Depends(get_current_user),
):
    """Detect available SDR hardware."""
    result = await sdr_service.detect_hardware()
    return result


# ── Scan ──────────────────────────────────────────────────────────────────────

@router.post("/scan")
async def start_scan(
    req: ScanRequest,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    """
    Scan a frequency range and return power measurements.
    Stores result with a task_id for later retrieval.
    """
    if req.start_mhz >= req.end_mhz:
        raise HTTPException(status_code=400, detail="start_mhz must be less than end_mhz")

    task_id = str(uuid.uuid4())[:8]
    result = await sdr_service.scan_frequencies(
        start_mhz=req.start_mhz,
        end_mhz=req.end_mhz,
        step_hz=req.step_hz,
        gain=req.gain,
    )
    _scan_tasks[task_id] = {"status": "done", "result": result}
    return {"task_id": task_id, **result}


@router.get("/scan-status/{task_id}")
async def scan_status(
    task_id: str,
    _user=Depends(get_current_user),
):
    """Retrieve the result of a previously submitted scan."""
    task = _scan_tasks.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


# ── Listen ────────────────────────────────────────────────────────────────────

@router.post("/listen")
async def listen(
    req: ListenRequest,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Tune to a frequency and capture demodulated audio."""
    result = await sdr_service.listen_frequency(
        frequency_mhz=req.frequency_mhz,
        gain=req.gain,
        duration=req.duration,
        modulation=req.modulation,
    )

    # Persist to DB
    try:
        recording = SDRRecording(
            recording_id=result.get("recording_id", str(uuid.uuid4())[:8]),
            frequency_mhz=req.frequency_mhz,
            sample_rate=2_000_000,
            gain=req.gain,
            modulation=req.modulation,
            duration=req.duration,
            file_path=result.get("file_path"),
            file_size=result.get("file_size"),
            file_type="wav",
            simulated=result.get("simulated", False),
        )
        db.add(recording)
        db.commit()
        db.refresh(recording)
        result["db_id"] = recording.id
    except Exception:
        db.rollback()

    return result


# ── Recordings ────────────────────────────────────────────────────────────────

@router.get("/recordings")
async def list_recordings(
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    """List SDR recordings from the database."""
    recordings = (
        db.query(SDRRecording)
        .order_by(SDRRecording.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    total = db.query(SDRRecording).count()
    return {
        "recordings": [
            {
                "id": r.id,
                "recording_id": r.recording_id,
                "frequency_mhz": r.frequency_mhz,
                "modulation": r.modulation,
                "duration": r.duration,
                "file_size": r.file_size,
                "file_type": r.file_type,
                "protocol": r.protocol,
                "replay_count": r.replay_count,
                "simulated": r.simulated,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in recordings
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/recordings/{recording_id}")
async def get_recording(
    recording_id: int,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Get a single SDR recording by ID."""
    rec = db.query(SDRRecording).filter(SDRRecording.id == recording_id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Recording not found")
    return {
        "id": rec.id,
        "recording_id": rec.recording_id,
        "frequency_mhz": rec.frequency_mhz,
        "sample_rate": rec.sample_rate,
        "gain": rec.gain,
        "modulation": rec.modulation,
        "duration": rec.duration,
        "file_path": rec.file_path,
        "file_size": rec.file_size,
        "file_type": rec.file_type,
        "protocol": rec.protocol,
        "decoded_content": rec.decoded_content,
        "replay_count": rec.replay_count,
        "simulated": rec.simulated,
        "created_at": rec.created_at.isoformat() if rec.created_at else None,
    }


@router.delete("/recordings/{recording_id}")
async def delete_recording(
    recording_id: int,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Delete a SDR recording."""
    rec = db.query(SDRRecording).filter(SDRRecording.id == recording_id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Recording not found")

    # Remove file from disk if it exists
    if rec.file_path:
        try:
            p = Path(rec.file_path)
            if p.exists():
                p.unlink()
        except OSError:
            pass

    db.delete(rec)
    db.commit()
    return {"success": True, "deleted_id": recording_id}


@router.post("/recordings/{recording_id}/decode")
async def decode_recording(
    recording_id: int,
    protocol: str = Query(default="automatic"),
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Decode digital content from a recorded file."""
    rec = db.query(SDRRecording).filter(SDRRecording.id == recording_id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Recording not found")

    result = await sdr_service.decode_digital(
        input_file=rec.file_path or "",
        protocol=protocol,
    )

    # Update record
    try:
        rec.protocol = result.get("protocol", protocol)
        rec.decoded_content = result.get("messages", [])
        db.commit()
    except Exception:
        db.rollback()

    return result


@router.post("/recordings/{recording_id}/replay")
async def replay_recording(
    recording_id: int,
    req: ReplayRequest,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Replay a captured IQ recording via HackRF."""
    rec = db.query(SDRRecording).filter(SDRRecording.id == recording_id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Recording not found")

    result = await sdr_service.replay_signal(
        input_file=rec.file_path or "",
        frequency_mhz=req.frequency_mhz,
        repeat=req.repeat,
    )

    # Increment replay counter
    try:
        rec.replay_count = (rec.replay_count or 0) + 1
        db.commit()
    except Exception:
        db.rollback()

    return result


# ── Capture IQ ────────────────────────────────────────────────────────────────

@router.post("/capture-iq")
async def capture_iq(
    req: CaptureIQRequest,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Capture raw IQ samples."""
    result = await sdr_service.capture_raw_iq(
        frequency_mhz=req.frequency_mhz,
        sample_rate=req.sample_rate,
        duration=req.duration,
    )

    try:
        recording = SDRRecording(
            recording_id=result.get("recording_id", str(uuid.uuid4())[:8]),
            frequency_mhz=req.frequency_mhz,
            sample_rate=req.sample_rate,
            duration=req.duration,
            file_path=result.get("file_path"),
            file_size=result.get("file_size"),
            file_type="iq",
            simulated=result.get("simulated", False),
        )
        db.add(recording)
        db.commit()
        db.refresh(recording)
        result["db_id"] = recording.id
    except Exception:
        db.rollback()

    return result


# ── Spectrum ──────────────────────────────────────────────────────────────────

@router.get("/spectrum")
async def get_spectrum(
    start_mhz: float = Query(default=88.0, ge=0.1, le=6000.0),
    end_mhz: float = Query(default=108.0, ge=0.1, le=6000.0),
    fft_size: int = Query(default=1024),
    _user=Depends(get_current_user),
):
    """Analyze spectrum between two frequencies."""
    if start_mhz >= end_mhz:
        raise HTTPException(status_code=400, detail="start_mhz must be less than end_mhz")
    return await sdr_service.analyze_spectrum(
        start_mhz=start_mhz,
        end_mhz=end_mhz,
        fft_size=fft_size,
    )


# ── Gate Detect ───────────────────────────────────────────────────────────────

@router.post("/gate-detect")
async def gate_detect(
    req: GateDetectRequest,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Listen on 433.92 MHz to capture gate/garage door remote codes."""
    result = await sdr_service.detect_gate_remote(frequency_mhz=req.frequency_mhz)

    try:
        recording = SDRRecording(
            recording_id=str(uuid.uuid4())[:8],
            frequency_mhz=req.frequency_mhz,
            modulation="am",
            duration=5,
            file_path=result.get("raw_signal"),
            file_type="wav",
            protocol="OOK",
            decoded_content=result.get("captured_codes", []),
            simulated=result.get("simulated", False),
        )
        db.add(recording)
        db.commit()
    except Exception:
        db.rollback()

    return result


# ── Jam ───────────────────────────────────────────────────────────────────────

@router.post("/jam")
async def jam(
    req: JamRequest,
    _user=Depends(get_current_user),
):
    """
    Transmit broadband noise on a frequency (HackRF required).
    Requires authorized=True flag.
    """
    if not req.authorized:
        raise HTTPException(
            status_code=403,
            detail="Jamming requires explicit authorization (authorized=true). "
                   "Unauthorized RF jamming is illegal in most jurisdictions.",
        )
    return await sdr_service.jam_frequency(
        frequency_mhz=req.frequency_mhz,
        duration=req.duration,
    )


# ── ADS-B ─────────────────────────────────────────────────────────────────────

class ADSBRequest(BaseModel):
    duration_s: int = Field(30, ge=5, le=300)
    authorization_confirmed: bool = False


@router.post("/adsb/decode")
async def adsb_decode(req: ADSBRequest, _user=Depends(get_current_user)):
    """Decode ADS-B aircraft transponder messages at 1090 MHz."""
    if not req.authorization_confirmed:
        raise HTTPException(403, detail="ADS-B decode nécessite authorization_confirmed=true")
    return await sdr_service.decode_adsb(req.duration_s)


@router.get("/adsb/live")
async def adsb_live(_user=Depends(get_current_user)):
    """Info pour flux ADS-B live en temps réel."""
    return await sdr_service.listen_adsb_live()


# ── AIS ───────────────────────────────────────────────────────────────────────

class AISRequest(BaseModel):
    duration_s: int = Field(30, ge=5, le=300)
    authorization_confirmed: bool = False


@router.post("/ais/decode")
async def ais_decode(req: AISRequest, _user=Depends(get_current_user)):
    """Decode AIS vessel tracking messages at 162 MHz."""
    if not req.authorization_confirmed:
        raise HTTPException(403, detail="AIS decode nécessite authorization_confirmed=true")
    return await sdr_service.decode_ais(req.duration_s)


# ── Drones ────────────────────────────────────────────────────────────────────

class DroneDetectRequest(BaseModel):
    scan_duration_s: int = Field(20, ge=5, le=120)
    authorization_confirmed: bool = False


class DroneHijackRequest(BaseModel):
    target_mac: str
    frequency_mhz: float = 2404.5
    authorization_confirmed: bool = False


@router.post("/drones/detect")
async def drone_detect(req: DroneDetectRequest, _user=Depends(get_current_user)):
    """Scan for drone RF signals (OcuSync, ExpressLRS, WiFi-based)."""
    if not req.authorization_confirmed:
        raise HTTPException(403, detail="Drone detection nécessite authorization_confirmed=true")
    return await sdr_service.detect_drone_signals(req.scan_duration_s)


@router.post("/drones/hijack")
async def drone_hijack(req: DroneHijackRequest, _user=Depends(get_current_user)):
    """Attempt drone deauth / frequency disruption (pentest autorisé requis)."""
    if not req.authorization_confirmed:
        raise HTTPException(403, detail="Drone hijack nécessite authorization_confirmed=true")
    return await sdr_service.hijack_dji_drone(req.target_mac, req.frequency_mhz)


# ── Pagers ────────────────────────────────────────────────────────────────────

class PagerRequest(BaseModel):
    frequency_mhz: float = Field(153.350)
    duration_s: int = Field(60, ge=10, le=600)
    authorization_confirmed: bool = False


@router.post("/pagers/pocsag")
async def pager_pocsag(req: PagerRequest, _user=Depends(get_current_user)):
    """Decode POCSAG pager messages."""
    if not req.authorization_confirmed:
        raise HTTPException(403, detail="Décodage pagers nécessite authorization_confirmed=true")
    return await sdr_service.decode_pocsag(req.frequency_mhz, req.duration_s)


@router.post("/pagers/flex")
async def pager_flex(req: PagerRequest, _user=Depends(get_current_user)):
    """Decode FLEX pager messages."""
    if not req.authorization_confirmed:
        raise HTTPException(403, detail="Décodage FLEX nécessite authorization_confirmed=true")
    return await sdr_service.decode_flex(req.frequency_mhz, req.duration_s)


# ── ACARS ─────────────────────────────────────────────────────────────────────

class ACARSRequest(BaseModel):
    frequency_mhz: float = Field(129.125)
    duration_s: int = Field(60, ge=10, le=600)
    authorization_confirmed: bool = False


@router.post("/acars/decode")
async def acars_decode(req: ACARSRequest, _user=Depends(get_current_user)):
    """Decode ACARS aircraft data link messages."""
    if not req.authorization_confirmed:
        raise HTTPException(403, detail="ACARS decode nécessite authorization_confirmed=true")
    return await sdr_service.decode_acars(req.frequency_mhz, req.duration_s)


# ── Weather Satellite ─────────────────────────────────────────────────────────

class SatelliteRequest(BaseModel):
    satellite: str = Field("NOAA-19", description="NOAA-15 | NOAA-18 | NOAA-19 | Meteor-M2")
    duration_s: int = Field(840, ge=60, le=1200)
    authorization_confirmed: bool = False


@router.post("/satellite/receive")
async def satellite_receive(req: SatelliteRequest, _user=Depends(get_current_user)):
    """Receive APT/LRPT image from weather satellite pass."""
    if not req.authorization_confirmed:
        raise HTTPException(403, detail="Réception satellite nécessite authorization_confirmed=true")
    return await sdr_service.receive_weather_satellite(req.satellite, req.duration_s)
