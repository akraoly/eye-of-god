"""
Routes /api/cameras — IP Camera Scanner (ONVIF + RTSP).

Scan networks, fingerprint cameras, test credentials, take snapshots, PTZ control,
check CVEs (Hikvision, Dahua).
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.engines.camera_scanner import camera_scanner_engine, _scan_jobs
from database.db import get_db

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Pydantic request models ───────────────────────────────────────────────────

class ScanRequest(BaseModel):
    subnet: str   # e.g. "192.168.1.0/24"


class FingerprintRequest(BaseModel):
    ip: str
    port: int = 80


class CredsTestRequest(BaseModel):
    ip: str
    port: int = 80


class SnapshotRequest(BaseModel):
    ip: str
    username: str = "admin"
    password: str = ""
    port: int = 80


class RtspRequest(BaseModel):
    ip: str
    port: int = 554
    username: str = "admin"
    password: str = ""


class PtzRequest(BaseModel):
    ip: str
    username: str = "admin"
    password: str = ""
    action: str = "center"   # up|down|left|right|zoom_in|zoom_out|center


class CveHikvisionRequest(BaseModel):
    ip: str
    port: int = 80


class CveDahuaRequest(BaseModel):
    ip: str
    port: int = 80


# ── Scan ──────────────────────────────────────────────────────────────────────

@router.post("/scan")
async def scan_subnet(req: ScanRequest, db: Session = Depends(get_db)):
    """
    Scan a subnet for IP cameras using nmap + ONVIF WS-Discovery.
    Returns a job_id; poll /scan/{job_id} for progress.
    """
    subnet = req.subnet.strip()
    if not subnet:
        raise HTTPException(status_code=400, detail="subnet cannot be empty")

    result = await camera_scanner_engine.scan_network(subnet)
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "Scan failed to start"))
    return result


@router.get("/scan/{job_id}")
async def get_scan_progress(job_id: str):
    """
    Get progress of a running or completed camera scan.
    Returns status, cameras_found, and partial results.
    """
    result = await camera_scanner_engine.get_scan_progress(job_id)
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("error", "Job not found"))
    return result


# ── Fingerprint ───────────────────────────────────────────────────────────────

@router.post("/fingerprint")
async def fingerprint_camera(req: FingerprintRequest):
    """
    Identify camera model, manufacturer, and firmware via HTTP banner + ONVIF.
    Supports Hikvision (ISAPI), Dahua (CGI), Axis (VAPIX), Foscam, generic ONVIF.
    """
    if not req.ip.strip():
        raise HTTPException(status_code=400, detail="ip cannot be empty")

    result = await camera_scanner_engine.fingerprint(req.ip, req.port)
    return result


# ── Default credentials ───────────────────────────────────────────────────────

@router.post("/creds-test")
async def test_default_credentials(req: CredsTestRequest, db: Session = Depends(get_db)):
    """
    Test 50+ default camera credential combinations against the target.
    Returns all working username/password pairs found.
    """
    if not req.ip.strip():
        raise HTTPException(status_code=400, detail="ip cannot be empty")

    result = await camera_scanner_engine.test_default_creds(req.ip, req.port)

    # Save to DB if creds found
    if result.get("working_creds"):
        try:
            from database.models import Camera
            from core.engines.camera_scanner import _encrypt_password
            for cred in result["working_creds"]:
                await camera_scanner_engine._save_camera_to_db({
                    "ip": req.ip,
                    "port": req.port,
                    "username": cred["username"],
                    "password_enc": _encrypt_password(cred["password"]),
                })
        except Exception as e:
            logger.warning(f"DB save error: {e}")

    return result


# ── Snapshot ──────────────────────────────────────────────────────────────────

@router.post("/snapshot")
async def take_snapshot(req: SnapshotRequest, db: Session = Depends(get_db)):
    """
    Take a camera snapshot via Hikvision ISAPI, Dahua CGI, or RTSP+ffmpeg fallback.
    Returns base64-encoded JPEG image and file path.
    """
    if not req.ip.strip():
        raise HTTPException(status_code=400, detail="ip cannot be empty")

    result = await camera_scanner_engine.take_snapshot(req.ip, req.username, req.password, req.port)

    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "Snapshot failed"))

    # Persist snapshot to DB
    try:
        from database.models import CameraSnapshot
        snap_id = result.get("snapshot_id", "")
        from datetime import datetime
        snap = CameraSnapshot(
            snapshot_id=snap_id,
            camera_id="",  # No camera_id without prior scan
            file_path=result.get("file_path", ""),
        )
        db.add(snap)
        db.commit()
    except Exception as e:
        logger.warning(f"Snapshot DB save error: {e}")

    return result


@router.get("/snapshot/download/{snapshot_id}")
async def download_snapshot(snapshot_id: str):
    """Download a previously taken camera snapshot image."""
    # Look for the file
    for p in camera_scanner_engine.CAMERAS_DIR.glob(f"{snapshot_id}*"):
        if p.exists():
            return FileResponse(str(p), media_type="image/jpeg", filename=p.name)
    raise HTTPException(status_code=404, detail=f"Snapshot {snapshot_id} not found")


# ── RTSP ──────────────────────────────────────────────────────────────────────

@router.post("/rtsp")
async def get_rtsp_url(req: RtspRequest):
    """
    Discover working RTSP stream URLs for a camera.
    Tests 20+ common RTSP path patterns using ffprobe.
    """
    if not req.ip.strip():
        raise HTTPException(status_code=400, detail="ip cannot be empty")

    result = await camera_scanner_engine.get_rtsp_url(req.ip, req.port, req.username, req.password)
    return result


# ── PTZ ───────────────────────────────────────────────────────────────────────

@router.post("/ptz")
async def control_ptz(req: PtzRequest):
    """
    PTZ camera control via ONVIF ContinuousMove / AbsoluteMove.
    Actions: up | down | left | right | zoom_in | zoom_out | center
    """
    valid_actions = ("up", "down", "left", "right", "zoom_in", "zoom_out", "center")
    if req.action not in valid_actions:
        raise HTTPException(status_code=400, detail=f"action must be one of: {', '.join(valid_actions)}")

    result = await camera_scanner_engine.control_ptz(req.ip, req.username, req.password, req.action)
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "PTZ control failed"))
    return result


# ── Camera list and detail ────────────────────────────────────────────────────

@router.get("/")
async def list_cameras(db: Session = Depends(get_db)):
    """List all discovered cameras from the database."""
    cameras = await camera_scanner_engine.list_cameras()
    return {"success": True, "cameras": cameras, "count": len(cameras)}


@router.get("/{camera_id}")
async def get_camera(camera_id: str, db: Session = Depends(get_db)):
    """Get details for a specific camera by camera_id."""
    try:
        from database.models import Camera
        import json
        cam = db.query(Camera).filter(Camera.camera_id == camera_id).first()
        if not cam:
            raise HTTPException(status_code=404, detail=f"Camera {camera_id} not found")
        return {
            "camera_id": cam.camera_id,
            "ip": cam.ip,
            "port": cam.port,
            "model": cam.model,
            "firmware": cam.firmware,
            "manufacturer": cam.manufacturer,
            "username": cam.username,
            "rtsp_url": cam.rtsp_url,
            "http_url": cam.http_url,
            "has_mic": cam.has_mic,
            "has_ptz": cam.has_ptz,
            "status": cam.status,
            "vulns": json.loads(cam.vulns) if cam.vulns else [],
            "scan_job_id": cam.scan_job_id,
            "discovered_at": cam.discovered_at.isoformat() if cam.discovered_at else None,
            "last_seen": cam.last_seen.isoformat() if cam.last_seen else None,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{camera_id}")
async def delete_camera(camera_id: str, db: Session = Depends(get_db)):
    """Remove a camera from the database."""
    try:
        from database.models import Camera
        cam = db.query(Camera).filter(Camera.camera_id == camera_id).first()
        if not cam:
            raise HTTPException(status_code=404, detail=f"Camera {camera_id} not found")
        db.delete(cam)
        db.commit()
        return {"success": True, "camera_id": camera_id, "deleted": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── CVE checks ────────────────────────────────────────────────────────────────

@router.post("/cve/hikvision")
async def check_hikvision_cve(req: CveHikvisionRequest, db: Session = Depends(get_db)):
    """
    Check for Hikvision CVE-2021-36260 (unauthenticated command injection via /SDK/webLanguage).
    Returns vulnerability status with evidence.
    """
    if not req.ip.strip():
        raise HTTPException(status_code=400, detail="ip cannot be empty")

    result = await camera_scanner_engine.check_hikvision_cve_2021_36260(req.ip, req.port)

    # Update vulns in DB if found
    if result.get("vulnerable"):
        try:
            from database.models import Camera
            import json
            cam = db.query(Camera).filter(Camera.ip == req.ip, Camera.port == req.port).first()
            if cam:
                vulns = json.loads(cam.vulns) if cam.vulns else []
                vuln_entry = {"cve": "CVE-2021-36260", "evidence": result.get("evidence")}
                if vuln_entry not in vulns:
                    vulns.append(vuln_entry)
                    cam.vulns = json.dumps(vulns)
                    db.commit()
        except Exception as e:
            logger.warning(f"Vuln DB update error: {e}")

    return result


@router.post("/cve/dahua")
async def check_dahua_cve(req: CveDahuaRequest, db: Session = Depends(get_db)):
    """
    Check for Dahua CVE-2021-33044 (authentication bypass via /RPC2 Magic field).
    Returns vulnerability status with evidence.
    """
    if not req.ip.strip():
        raise HTTPException(status_code=400, detail="ip cannot be empty")

    result = await camera_scanner_engine.check_dahua_cve_2021_33044(req.ip, req.port)

    # Update vulns in DB if found
    if result.get("vulnerable"):
        try:
            from database.models import Camera
            import json
            cam = db.query(Camera).filter(Camera.ip == req.ip, Camera.port == req.port).first()
            if cam:
                vulns = json.loads(cam.vulns) if cam.vulns else []
                vuln_entry = {"cve": "CVE-2021-33044", "evidence": result.get("evidence")}
                if vuln_entry not in vulns:
                    vulns.append(vuln_entry)
                    cam.vulns = json.dumps(vulns)
                    db.commit()
        except Exception as e:
            logger.warning(f"Vuln DB update error: {e}")

    return result
