"""
Routes /api/lab — Docker-based vulnerable lab environments.
"""
from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from core.engines.lab_manager import LabManager

router = APIRouter()
_manager = LabManager()


# ── Request models ────────────────────────────────────────────────────────────

class CreateLabRequest(BaseModel):
    template: str
    lab_name: Optional[str] = None


class ScanLabRequest(BaseModel):
    scan_type: str = "full"  # full | nmap | quick


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/templates")
async def get_templates():
    """List all available lab templates."""
    templates = await _manager.get_lab_templates()
    return {"templates": templates, "count": len(templates)}


@router.post("/create")
async def create_lab(req: CreateLabRequest):
    """Create a new lab instance from a template."""
    result = await _manager.create_lab(template=req.template, lab_name=req.lab_name)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    if result.get("available") is False:
        raise HTTPException(status_code=503, detail=result["message"])
    return result


@router.get("/instances")
async def list_instances():
    """List all running lab instances."""
    labs = await _manager.list_labs()
    return {"labs": labs, "count": len(labs)}


@router.get("/instance/{lab_id}")
async def get_instance(lab_id: str):
    """Get detailed status of a specific lab instance."""
    result = await _manager.get_lab_status(lab_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.post("/stop/{lab_id}")
async def stop_lab(lab_id: str):
    """Stop and remove a lab instance."""
    if _manager._check_docker():
        raise HTTPException(status_code=503, detail="Docker not available")
    success = await _manager.stop_lab(lab_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Lab {lab_id} not found or already stopped")
    return {"lab_id": lab_id, "stopped": True, "message": f"Lab {lab_id} stopped and removed"}


@router.post("/scan/{lab_id}")
async def scan_lab(lab_id: str, req: ScanLabRequest = ScanLabRequest()):
    """Launch a pentest scan against a lab instance."""
    result = await _manager.launch_scan_against_lab(lab_id=lab_id, scan_type=req.scan_type)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result
