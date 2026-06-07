"""
Routes /api/implants — ImplantManager (Module 6).

All endpoints are JWT-protected via the main router.
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database.db import get_db
from core.engines.implant_manager import ImplantManager

router = APIRouter()
_manager = ImplantManager()


# ── Request models ─────────────────────────────────────────────────────────────

class GenerateImplantRequest(BaseModel):
    os_type: str = Field("linux", description="windows | linux")
    protocol: str = Field("tcp", description="tcp | https | dns")
    lhost: str = Field(..., description="C2 listener IP / hostname")
    lport: int = Field(4444, ge=1, le=65535)
    persistence_method: str = Field(
        "crontab",
        description="Windows: scheduled_task|registry_run|service|dll_hijack  Linux: crontab|systemd|bashrc|ld_preload",
    )


class PersistenceRequest(BaseModel):
    os_type: str = Field("linux", description="windows | linux")
    method: str = Field(..., description="See GenerateImplantRequest.persistence_method")
    payload_path: str = Field(..., description="Path to the payload on the target")
    interval: int = Field(0, ge=0, description="Re-execution interval in seconds (0=on login/boot)")


class RegisterBeaconRequest(BaseModel):
    hostname: str
    ip: str
    os: str = Field("linux", description="OS type")
    arch: str = Field("x64", description="Architecture")
    privilege: str = Field("user", description="user | admin | system | root")
    protocol: str = Field("tcp", description="tcp | https | dns")
    c2_host: str = ""
    c2_port: int = Field(0, ge=0, le=65535)
    tags: Optional[List[str]] = None
    notes: str = ""


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("/")
async def list_beacons(db: Session = Depends(get_db)):
    """List all registered beacons."""
    try:
        from database.models import ImplantBeacon
        beacons = (
            db.query(ImplantBeacon)
            .order_by(ImplantBeacon.last_seen.desc())
            .all()
        )
        return {
            "count": len(beacons),
            "beacons": [
                {
                    "id": b.id,
                    "beacon_id": b.beacon_id,
                    "hostname": b.hostname,
                    "ip": b.ip,
                    "os_type": b.os_type,
                    "arch": b.arch,
                    "privilege": b.privilege,
                    "protocol": b.protocol,
                    "status": b.status,
                    "last_seen": b.last_seen.isoformat() if b.last_seen else None,
                    "first_seen": b.first_seen.isoformat() if b.first_seen else None,
                    "c2_host": b.c2_host,
                    "c2_port": b.c2_port,
                    "tags": b.tags or [],
                    "notes": b.notes,
                }
                for b in beacons
            ],
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/generate")
async def generate_implant(req: GenerateImplantRequest):
    """
    Generate a full implant: msfvenom payload + persistence commands.
    Returns the msfvenom command, output path, and persistence setup steps.
    """
    result = await _manager.generate_implant(
        os_type=req.os_type,
        protocol=req.protocol,
        lhost=req.lhost,
        lport=req.lport,
        persistence_method=req.persistence_method,
    )
    if result.get("available") is False:
        raise HTTPException(status_code=503, detail=result.get("error", "msfvenom unavailable"))
    return result


@router.post("/persistence")
async def generate_persistence(req: PersistenceRequest):
    """
    Generate persistence commands for a given OS and method.
    Returns ordered command list + cleanup instructions.
    """
    result = await _manager.generate_persistence(
        os_type=req.os_type,
        method=req.method,
        payload_path=req.payload_path,
        interval=req.interval,
    )
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Persistence generation failed"))
    return result


@router.post("/beacon/register")
async def register_beacon(req: RegisterBeaconRequest):
    """Register a new beacon / implant check-in."""
    beacon_id = await _manager.register_beacon(
        hostname=req.hostname,
        ip=req.ip,
        os=req.os,
        arch=req.arch,
        privilege=req.privilege,
        protocol=req.protocol,
        c2_host=req.c2_host,
        c2_port=req.c2_port,
        tags=req.tags,
        notes=req.notes,
    )
    return {"beacon_id": beacon_id, "status": "registered"}


@router.delete("/beacon/{beacon_id}")
async def remove_beacon(beacon_id: str, db: Session = Depends(get_db)):
    """Remove a beacon by beacon_id (UUID)."""
    try:
        from database.models import ImplantBeacon
        deleted = (
            db.query(ImplantBeacon)
            .filter(ImplantBeacon.beacon_id == beacon_id)
            .delete()
        )
        db.commit()
        if not deleted:
            raise HTTPException(status_code=404, detail="Beacon not found")
        return {"message": f"Beacon {beacon_id} removed"}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.patch("/beacon/{beacon_id}/status")
async def update_beacon_status(
    beacon_id: str,
    status: str,
    db: Session = Depends(get_db),
):
    """Update beacon status: active | inactive | lost."""
    valid = {"active", "inactive", "lost"}
    if status not in valid:
        raise HTTPException(status_code=400, detail=f"Status must be one of: {valid}")
    try:
        from database.models import ImplantBeacon
        from datetime import datetime
        beacon = db.query(ImplantBeacon).filter(ImplantBeacon.beacon_id == beacon_id).first()
        if not beacon:
            raise HTTPException(status_code=404, detail="Beacon not found")
        beacon.status = status
        if status == "active":
            beacon.last_seen = datetime.utcnow()
        db.commit()
        return {"beacon_id": beacon_id, "status": status}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/sessions/active")
async def list_active_sessions():
    """List all active C2 sessions from the database."""
    sessions = await _manager.list_active_sessions()
    return {"count": len(sessions), "sessions": sessions}
