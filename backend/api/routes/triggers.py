"""
Routes /api/triggers — Automation & Intelligent Triggers (Module 22).

Rule-based IF→THEN automation engine.
All endpoints are JWT-protected via the main router.
"""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database.db import get_db
from core.engines.trigger_engine import trigger_engine, CONDITION_TYPES, ACTION_TYPES

router = APIRouter()


# ── Request models ─────────────────────────────────────────────────────────────

class CreateTriggerRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    condition_type: str = Field(..., description=f"One of: {CONDITION_TYPES}")
    condition: dict = Field(..., description="Condition parameters (type-specific)")
    action_type: str = Field(..., description=f"One of: {ACTION_TYPES}")
    action: dict = Field(..., description="Action parameters (type-specific)")
    enabled: bool = True


class UpdateTriggerRequest(BaseModel):
    name: Optional[str] = None
    condition_type: Optional[str] = None
    condition: Optional[dict] = None
    action_type: Optional[str] = None
    action: Optional[dict] = None
    enabled: Optional[bool] = None


class EvaluateTriggerRequest(BaseModel):
    trigger_id: str
    event_data: dict = Field(default_factory=dict)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/")
async def create_trigger(
    req: CreateTriggerRequest,
    db: Session = Depends(get_db),
):
    """Create a new IF→THEN automation rule."""
    try:
        trigger_id = await trigger_engine.create_trigger(
            name=req.name,
            condition_type=req.condition_type,
            condition=req.condition,
            action_type=req.action_type,
            action=req.action,
            enabled=req.enabled,
            db=db,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return {
        "trigger_id": trigger_id,
        "name": req.name,
        "condition_type": req.condition_type,
        "action_type": req.action_type,
        "enabled": req.enabled,
        "status": "created",
    }


@router.get("/")
async def list_triggers(db: Session = Depends(get_db)):
    """List all automation triggers with execution stats."""
    try:
        return await trigger_engine.list_triggers(db=db)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/conditions/types")
async def get_condition_types():
    """Return available condition types with descriptions."""
    descriptions = {
        "audio_level":      "Microphone audio level exceeds threshold",
        "motion_detection": "Camera motion detected",
        "network_device":   "New device appears on network",
        "keyword_detected": "Keyword found in audio transcription or text",
        "scheduled_time":   "Cron expression (5-field: min hour dom month dow)",
        "file_changed":     "File modification detected at watched path",
        "alert_created":    "New SOC alert created (severity filter)",
        "beacon_connected": "New C2 beacon connects",
    }
    return [
        {"type": t, "description": descriptions.get(t, "")}
        for t in CONDITION_TYPES
    ]


@router.get("/actions/types")
async def get_action_types():
    """Return available action types with parameter schemas."""
    schemas = {
        "take_snapshot":      {"session_id": "str"},
        "start_recording":    {"duration": "int (seconds)", "device": "str"},
        "send_alert":         {"severity": "LOW|MEDIUM|HIGH|CRITICAL", "title": "str", "category": "str"},
        "execute_c2_command": {"session_id": "str", "command": "str"},
        "start_scan":         {"target": "str (IP or CIDR)"},
        "exfiltrate_data":    {"data_b64": "str", "channel": "dns|http", "config": "dict"},
        "send_notification":  {"message": "str"},
        "run_script":         {"script": "str (bash)"},
    }
    return [
        {"type": t, "params": schemas.get(t, {})}
        for t in ACTION_TYPES
    ]


@router.get("/{trigger_id}")
async def get_trigger(
    trigger_id: str,
    db: Session = Depends(get_db),
):
    """Get full details for a single trigger."""
    result = await trigger_engine.get_trigger(trigger_id, db=db)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Trigger {trigger_id} not found")
    return result


@router.put("/{trigger_id}")
async def update_trigger(
    trigger_id: str,
    req: UpdateTriggerRequest,
    db: Session = Depends(get_db),
):
    """Update a trigger's configuration."""
    updates = req.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    result = await trigger_engine.update_trigger(trigger_id, updates, db=db)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Trigger {trigger_id} not found")
    return result


@router.delete("/{trigger_id}")
async def delete_trigger(
    trigger_id: str,
    db: Session = Depends(get_db),
):
    """Delete a trigger and cancel any associated scheduler job."""
    deleted = await trigger_engine.delete_trigger(trigger_id, db=db)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Trigger {trigger_id} not found")
    return {"trigger_id": trigger_id, "deleted": True}


@router.post("/{trigger_id}/toggle")
async def toggle_trigger(
    trigger_id: str,
    db: Session = Depends(get_db),
):
    """Enable or disable a trigger."""
    result = await trigger_engine.toggle_trigger(trigger_id, db=db)
    if "error" in result:
        status_code = 404 if result["error"] == "not_found" else 500
        raise HTTPException(status_code=status_code, detail=result["error"])
    return result


@router.post("/{trigger_id}/test")
async def test_trigger(
    trigger_id: str,
    db: Session = Depends(get_db),
):
    """Force-fire a trigger for testing with synthetic event data."""
    result = await trigger_engine.test_trigger(trigger_id, db=db)
    if "error" in result:
        status_code = 404 if result["error"] == "trigger not found" else 500
        raise HTTPException(status_code=status_code, detail=result["error"])
    return result


@router.get("/{trigger_id}/logs")
async def get_trigger_logs(
    trigger_id: str,
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """Get execution history for a trigger."""
    # Validate trigger exists
    trigger = await trigger_engine.get_trigger(trigger_id, db=db)
    if trigger is None:
        raise HTTPException(status_code=404, detail=f"Trigger {trigger_id} not found")

    logs = await trigger_engine.get_trigger_logs(trigger_id=trigger_id, limit=limit, db=db)
    return {
        "trigger_id": trigger_id,
        "trigger_name": trigger.get("name"),
        "logs": logs,
        "count": len(logs),
    }


@router.post("/evaluate")
async def evaluate_trigger(
    req: EvaluateTriggerRequest,
    db: Session = Depends(get_db),
):
    """
    Manually evaluate a trigger condition against provided event data.
    Returns whether the trigger fired and the action result.
    """
    fired = await trigger_engine.evaluate_trigger(
        req.trigger_id, req.event_data, db=db
    )
    return {
        "trigger_id": req.trigger_id,
        "fired": fired,
        "event_data": req.event_data,
    }


@router.get("/logs/all")
async def get_all_trigger_logs(
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """Get global trigger execution history (all triggers)."""
    logs = await trigger_engine.get_trigger_logs(trigger_id=None, limit=limit, db=db)
    return {"logs": logs, "count": len(logs)}
