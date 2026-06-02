"""
Routes /api/autonomy — tâches planifiées + alertes proactives + moniteurs.
"""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from sqlalchemy.orm import Session

from app.dependencies import get_db
from database.models import ScheduledTask
from core.autonomy.scheduler import (
    get_scheduler, schedule_task, remove_task, run_task_now, list_jobs,
)
from core.autonomy.alert_store import alert_store
from core.autonomy.monitors import get_system_snapshot, MONITORS

router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────────

class TaskCreate(BaseModel):
    name:             str   = Field(..., min_length=1, max_length=255)
    description:      str   = Field("", max_length=500)
    kind:             str   = Field("shell", description="shell | http_check")
    command:          Optional[str] = None
    url:              Optional[str] = None
    schedule_type:    str   = Field("interval", description="interval | cron | once")
    interval_seconds: int   = Field(3600, ge=30)
    cron:             Optional[str] = None
    run_at:           Optional[str] = None


def _task_to_dict(t: ScheduledTask, jobs: list[dict]) -> dict:
    job = next((j for j in jobs if j["job_id"] == t.id), None)
    return {
        "id":               t.id,
        "name":             t.name,
        "description":      t.description or "",
        "kind":             t.kind,
        "command":          t.command,
        "url":              t.url,
        "schedule_type":    t.schedule_type,
        "interval_seconds": t.interval_seconds,
        "cron":             t.cron,
        "run_at":           t.run_at,
        "enabled":          t.enabled,
        "last_run":         t.last_run.isoformat() if t.last_run else None,
        "run_count":        t.run_count,
        "next_run":         job["next_run"] if job else None,
        "created_at":       t.created_at.isoformat() if t.created_at else None,
    }


# ── Tâches planifiées ─────────────────────────────────────────────────────────

@router.get("/tasks")
def list_tasks(db: Session = Depends(get_db)):
    tasks = db.query(ScheduledTask).order_by(ScheduledTask.created_at.desc()).all()
    jobs  = list_jobs()
    return {"tasks": [_task_to_dict(t, jobs) for t in tasks], "count": len(tasks)}


@router.post("/tasks", status_code=201)
def create_task(body: TaskCreate, db: Session = Depends(get_db)):
    if body.kind == "shell" and not body.command:
        raise HTTPException(400, "command requis pour kind=shell")
    if body.kind == "http_check" and not body.url:
        raise HTTPException(400, "url requis pour kind=http_check")
    if body.schedule_type == "cron" and not body.cron:
        raise HTTPException(400, "cron requis pour schedule_type=cron")
    if body.schedule_type == "once" and not body.run_at:
        raise HTTPException(400, "run_at requis pour schedule_type=once")

    task = ScheduledTask(
        name=body.name, description=body.description,
        kind=body.kind, command=body.command, url=body.url,
        schedule_type=body.schedule_type, interval_seconds=body.interval_seconds,
        cron=body.cron, run_at=body.run_at, enabled=True,
    )
    db.add(task); db.commit()

    schedule_task(task.__dict__ | {"id": task.id})
    return _task_to_dict(task, list_jobs())


@router.delete("/tasks/{task_id}")
def delete_task(task_id: str, db: Session = Depends(get_db)):
    task = db.query(ScheduledTask).filter(ScheduledTask.id == task_id).first()
    if not task:
        raise HTTPException(404, f"Tâche {task_id} introuvable")
    remove_task(task_id)
    db.delete(task); db.commit()
    return {"deleted": True, "id": task_id}


@router.post("/tasks/{task_id}/run")
def run_now(task_id: str, db: Session = Depends(get_db)):
    task = db.query(ScheduledTask).filter(ScheduledTask.id == task_id).first()
    if not task:
        raise HTTPException(404, f"Tâche {task_id} introuvable")
    task.last_run = datetime.now(timezone.utc)
    task.run_count += 1
    db.commit()
    run_task_now(task.__dict__ | {"id": task.id})
    return {"triggered": True, "id": task_id}


@router.patch("/tasks/{task_id}/toggle")
def toggle_task(task_id: str, db: Session = Depends(get_db)):
    task = db.query(ScheduledTask).filter(ScheduledTask.id == task_id).first()
    if not task:
        raise HTTPException(404, f"Tâche {task_id} introuvable")
    task.enabled = not task.enabled
    db.commit()
    if task.enabled:
        schedule_task(task.__dict__ | {"id": task.id})
    else:
        remove_task(task_id)
    return {"enabled": task.enabled, "id": task_id}


# ── Alertes proactives ────────────────────────────────────────────────────────

@router.get("/alerts")
def get_alerts(unread_only: bool = False, limit: int = 50):
    alerts = alert_store.get_all(unread_only=unread_only, limit=limit)
    return {
        "alerts": alerts,
        "count": len(alerts),
        "unread": alert_store.unread_count,
    }


@router.post("/alerts/{alert_id}/read")
def mark_read(alert_id: str):
    alert_store.mark_read(alert_id)
    return {"read": True, "unread": alert_store.unread_count}


@router.post("/alerts/read-all")
def mark_all_read():
    alert_store.mark_all_read()
    return {"read": True, "unread": 0}


@router.delete("/alerts/{alert_id}")
def dismiss_alert(alert_id: str):
    if not alert_store.dismiss(alert_id):
        raise HTTPException(404, "Alerte introuvable")
    return {"dismissed": True}


@router.delete("/alerts")
def clear_alerts():
    alert_store.clear()
    return {"cleared": True}


@router.get("/alerts/count")
def get_unread_count():
    return {"unread": alert_store.unread_count}


# ── Moniteurs ─────────────────────────────────────────────────────────────────

@router.get("/monitors")
def get_monitors():
    scheduler = get_scheduler()
    result = []
    for m in MONITORS:
        job_id = f"monitor_{m['id']}"
        job    = scheduler.get_job(job_id)
        result.append({
            "id":          m["id"],
            "name":        m["name"],
            "description": m["description"],
            "interval_seconds": m["interval_seconds"],
            "enabled":     job is not None,
            "next_run":    job.next_run_time.isoformat() if job and job.next_run_time else None,
        })
    return {"monitors": result}


@router.get("/snapshot")
def system_snapshot():
    return get_system_snapshot()
