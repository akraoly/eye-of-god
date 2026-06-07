"""
Routes /api/honeypots — High-interaction honeypot management.
"""
from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from core.engines.honeypot_engine import HoneypotEngine

router = APIRouter()
_engine = HoneypotEngine()


# ── Request models ────────────────────────────────────────────────────────────

SUPPORTED_SERVICES = ("ssh", "http", "ftp", "smb", "telnet", "smtp")


class StartHoneypotRequest(BaseModel):
    port: int
    service_type: str  # ssh | http | ftp | smb | telnet | smtp
    fake_banner: Optional[str] = None


class AnalyzeInteractionRequest(BaseModel):
    raw_data: str
    service_type: str = "unknown"
    attacker_ip: Optional[str] = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/start")
async def start_honeypot(req: StartHoneypotRequest):
    """Start a honeypot listener on the given port."""
    if req.service_type not in SUPPORTED_SERVICES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported service type '{req.service_type}'. Supported: {SUPPORTED_SERVICES}",
        )
    if req.port < 1 or req.port > 65535:
        raise HTTPException(status_code=400, detail="Port must be between 1 and 65535")

    result = await _engine.start_honeypot(
        port=req.port,
        service_type=req.service_type,
        fake_banner=req.fake_banner,
    )
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/stop/{port}")
async def stop_honeypot(port: int):
    """Stop honeypot on the given port."""
    if port < 1 or port > 65535:
        raise HTTPException(status_code=400, detail="Invalid port number")
    stopped = await _engine.stop_honeypot(port)
    return {
        "port": port,
        "stopped": stopped,
        "message": f"Honeypot on port {port} {'stopped' if stopped else 'was not active'}",
    }


@router.get("/")
async def list_honeypots():
    """List all active honeypot listeners."""
    honeypots = await _engine.list_honeypots()
    return {"honeypots": honeypots, "count": len(honeypots)}


@router.get("/captures")
async def get_all_captures(
    honeypot_id: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
):
    """Get all attacker captures, optionally filtered by honeypot_id."""
    captures = await _engine.get_captures(honeypot_id=honeypot_id, limit=limit)
    return {"captures": captures, "count": len(captures)}


@router.get("/captures/{capture_id}")
async def get_capture(capture_id: str):
    """Get details of a specific capture."""
    from database.db import SessionLocal
    from database.models import HoneypotCapture
    import json
    from core.engines.honeypot_engine import _decrypt

    db = SessionLocal()
    try:
        capture = db.query(HoneypotCapture).filter_by(capture_id=capture_id).first()
        if not capture:
            raise HTTPException(status_code=404, detail=f"Capture {capture_id} not found")

        creds = {}
        try:
            creds = json.loads(_decrypt(capture.parsed_credentials or ""))
        except Exception:
            pass

        return {
            "capture_id": capture.capture_id,
            "honeypot_id": capture.honeypot_id,
            "attacker_ip": capture.attacker_ip,
            "attacker_port": capture.attacker_port,
            "timestamp": capture.timestamp.isoformat() if capture.timestamp else None,
            "raw_data": capture.raw_data,
            "credentials": creds,
            "mitre_techniques": json.loads(capture.mitre_techniques or "[]"),
            "severity": capture.severity,
        }
    finally:
        db.close()


@router.get("/analytics")
async def get_analytics():
    """Get TTP analytics and statistics from all captures."""
    return await _engine.get_analytics()


@router.post("/analyze")
async def analyze_interaction(req: AnalyzeInteractionRequest):
    """Analyze a captured interaction for MITRE ATT&CK TTPs."""
    result = await _engine.analyze_interaction({
        "raw_data": req.raw_data,
        "service_type": req.service_type,
        "attacker_ip": req.attacker_ip,
    })
    return result
