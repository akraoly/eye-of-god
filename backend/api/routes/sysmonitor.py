"""
Routes /api/sentinel — Surveillance système temps réel.
WebSocket push + REST pour métriques, événements, baselines, règles.
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.auth.jwt_handler import decode_access_token
from core.auth.dependencies import get_current_user
from database.db import get_db
import jwt as _jwt

router = APIRouter()


# ── WebSocket temps réel ──────────────────────────────────────────────────────

@router.websocket("/ws")
async def sentinel_ws(websocket: WebSocket, token: str = Query(...)):
    """Stream WebSocket des événements Sentinel en temps réel."""
    try:
        decode_access_token(token)
    except (_jwt.ExpiredSignatureError, _jwt.InvalidTokenError):
        await websocket.close(code=4001)
        return

    await websocket.accept()
    from core.monitor.event_bus import sentinel_bus
    queue: asyncio.Queue = asyncio.Queue(maxsize=200)
    sentinel_bus.subscribe(queue)

    # Envoyer l'historique récent
    for evt in sentinel_bus.get_history(50):
        try:
            await websocket.send_text(json.dumps(evt, ensure_ascii=False))
        except Exception:
            break

    try:
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=3.0)
                await websocket.send_text(json.dumps(event, ensure_ascii=False))
            except asyncio.TimeoutError:
                await websocket.send_text(json.dumps({"type": "ping"}))
    except (WebSocketDisconnect, Exception):
        pass
    finally:
        sentinel_bus.unsubscribe(queue)


# ── REST ──────────────────────────────────────────────────────────────────────

@router.get("/health", dependencies=[Depends(get_current_user)])
async def get_health(db: Session = Depends(get_db)):
    """Score de santé global + dernières métriques."""
    from core.monitor.metrics_collector import collect_metrics, get_history
    snapshot = collect_metrics(db=db)

    history = get_history(db, limit=60)
    recent_events = _get_recent_events(db, limit=5, min_severity="HIGH")

    from core.monitor.health_score import score_to_status, score_to_label
    score = snapshot.get("health_score", 100)

    return {
        "score": score,
        "status": score_to_status(score),
        "label": score_to_label(score),
        "snapshot": snapshot,
        "history": history[-20:],
        "recent_alerts": recent_events,
    }


@router.get("/metrics", dependencies=[Depends(get_current_user)])
def get_metrics_history(
    limit: int = Query(100, le=500),
    db: Session = Depends(get_db),
):
    from core.monitor.metrics_collector import get_history
    return {"metrics": get_history(db, limit=limit)}


@router.get("/events", dependencies=[Depends(get_current_user)])
def get_security_events(
    limit: int = Query(50, le=500),
    severity: str = Query("", description="Filtrer par sévérité"),
    category: str = Query("", description="Filtrer par catégorie"),
    hours: int = Query(24, description="Fenêtre temporelle en heures"),
    db: Session = Depends(get_db),
):
    from database.models import SecurityEventLog
    q = db.query(SecurityEventLog)
    if severity:
        q = q.filter(SecurityEventLog.severity == severity.upper())
    if category:
        q = q.filter(SecurityEventLog.category == category.upper())
    since = datetime.utcnow() - timedelta(hours=hours)
    q = q.filter(SecurityEventLog.timestamp >= since)
    rows = q.order_by(SecurityEventLog.timestamp.desc()).limit(limit).all()
    return {
        "events": [
            {
                "id": r.id,
                "timestamp": r.timestamp.isoformat(),
                "category": r.category,
                "severity": r.severity,
                "title": r.title,
                "description": r.description,
                "resolved": r.resolved,
            }
            for r in rows
        ],
        "count": len(rows),
    }


@router.post("/events/{event_id}/resolve", dependencies=[Depends(get_current_user)])
def resolve_event(event_id: int, db: Session = Depends(get_db)):
    from database.models import SecurityEventLog
    row = db.query(SecurityEventLog).filter(SecurityEventLog.id == event_id).first()
    if not row:
        from fastapi import HTTPException
        raise HTTPException(404, "Event not found")
    row.resolved = True
    db.commit()
    return {"ok": True}


@router.get("/processes", dependencies=[Depends(get_current_user)])
def get_processes():
    from core.monitor.process_guardian import get_process_list
    return {"processes": get_process_list()}


@router.get("/ports", dependencies=[Depends(get_current_user)])
def get_ports(db: Session = Depends(get_db)):
    from core.monitor.port_sentinel import get_ports_status
    return get_ports_status()


@router.get("/integrity", dependencies=[Depends(get_current_user)])
def get_integrity(db: Session = Depends(get_db)):
    from core.monitor.integrity_checker import get_integrity_status
    return get_integrity_status(db)


@router.post("/integrity/rebuild", dependencies=[Depends(get_current_user)])
def rebuild_integrity_baseline(db: Session = Depends(get_db)):
    from core.monitor.integrity_checker import build_baseline
    result = build_baseline(db)
    return {"ok": True, "files": len(result)}


@router.post("/baseline/rebuild", dependencies=[Depends(get_current_user)])
def rebuild_baselines(db: Session = Depends(get_db)):
    from core.monitor.process_guardian import build_baseline as bp
    from core.monitor.port_sentinel import build_baseline as bport
    from core.monitor.integrity_checker import build_baseline as bfile
    bp(db)
    bport(db)
    bfile(db)
    return {"ok": True}


# ── Whitelist réseau ──────────────────────────────────────────────────────────

class WhitelistEntry(BaseModel):
    entry: str  # IP ou IP:port

@router.post("/network/whitelist", dependencies=[Depends(get_current_user)])
def add_whitelist(body: WhitelistEntry, db: Session = Depends(get_db)):
    from core.monitor.network_sentinel import add_to_whitelist
    add_to_whitelist(db, body.entry)
    return {"ok": True, "entry": body.entry}


# ── Règles personnalisées ─────────────────────────────────────────────────────

class RuleCreate(BaseModel):
    name: str
    rule_type: str
    condition: dict
    action: str = "alert"
    description: str = ""

class RuleNaturalLanguage(BaseModel):
    text: str

@router.get("/rules", dependencies=[Depends(get_current_user)])
def list_rules(db: Session = Depends(get_db)):
    from database.models import CustomMonitorRule
    rows = db.query(CustomMonitorRule).order_by(CustomMonitorRule.created_at.desc()).all()
    return {
        "rules": [
            {
                "id": r.rule_id, "name": r.name, "rule_type": r.rule_type,
                "condition": json.loads(r.condition), "action": r.action,
                "enabled": r.enabled, "description": r.description,
            }
            for r in rows
        ]
    }


@router.post("/rules", dependencies=[Depends(get_current_user)])
def create_rule(body: RuleCreate, db: Session = Depends(get_db)):
    import uuid
    from database.models import CustomMonitorRule
    row = CustomMonitorRule(
        rule_id=str(uuid.uuid4()),
        name=body.name, description=body.description,
        rule_type=body.rule_type, condition=json.dumps(body.condition),
        action=body.action, enabled=True,
    )
    db.add(row)
    db.commit()
    from core.monitor.rules_engine import rules_engine
    rules_engine.load_rules(db)
    return {"id": row.rule_id, "name": row.name}


@router.post("/rules/natural", dependencies=[Depends(get_current_user)])
def create_rule_natural(body: RuleNaturalLanguage, db: Session = Depends(get_db)):
    from core.monitor.rules_engine import rules_engine
    result = rules_engine.create_rule_from_text(db, body.text)
    return result


@router.delete("/rules/{rule_id}", dependencies=[Depends(get_current_user)])
def delete_rule(rule_id: str, db: Session = Depends(get_db)):
    from database.models import CustomMonitorRule
    row = db.query(CustomMonitorRule).filter(CustomMonitorRule.rule_id == rule_id).first()
    if row:
        db.delete(row)
        db.commit()
    from core.monitor.rules_engine import rules_engine
    rules_engine.load_rules(db)
    return {"ok": True}


@router.patch("/rules/{rule_id}/toggle", dependencies=[Depends(get_current_user)])
def toggle_rule(rule_id: str, db: Session = Depends(get_db)):
    from database.models import CustomMonitorRule
    row = db.query(CustomMonitorRule).filter(CustomMonitorRule.rule_id == rule_id).first()
    if row:
        row.enabled = not row.enabled
        db.commit()
    from core.monitor.rules_engine import rules_engine
    rules_engine.load_rules(db)
    return {"ok": True, "enabled": row.enabled if row else False}


# ── Rapport 24h ──────────────────────────────────────────────────────────────

@router.get("/report", dependencies=[Depends(get_current_user)])
async def security_report(
    hours: int = Query(24),
    db: Session = Depends(get_db),
):
    """Rapport de sécurité des dernières N heures, analysé par Claude."""
    from database.models import SecurityEventLog, SystemMetricHistory
    since = datetime.utcnow() - timedelta(hours=hours)

    events = (
        db.query(SecurityEventLog)
        .filter(SecurityEventLog.timestamp >= since)
        .order_by(SecurityEventLog.timestamp.desc())
        .limit(100)
        .all()
    )

    metrics = (
        db.query(SystemMetricHistory)
        .filter(SystemMetricHistory.timestamp >= since)
        .order_by(SystemMetricHistory.timestamp.desc())
        .limit(5)
        .all()
    )

    # Statistiques
    counts = {}
    for e in events:
        counts[e.severity] = counts.get(e.severity, 0) + 1

    avg_cpu = sum(m.cpu_pct for m in metrics) / max(len(metrics), 1)
    avg_ram = sum(m.ram_pct for m in metrics) / max(len(metrics), 1)
    avg_score = sum(m.health_score for m in metrics) / max(len(metrics), 1)

    events_text = "\n".join(
        f"[{e.severity}] {e.category} — {e.title}"
        for e in events[:30]
    )

    from core.llm.client import llm_client
    try:
        analysis = await llm_client.complete(
            messages=[{
                "role": "user",
                "content": (
                    f"Rapport système des {hours} dernières heures.\n"
                    f"CPU moyen: {avg_cpu:.0f}% | RAM moyenne: {avg_ram:.0f}% | Score santé: {avg_score:.0f}/100\n"
                    f"Événements par sévérité: {counts}\n\n"
                    f"Événements détectés:\n{events_text or 'Aucun événement.'}"
                ),
            }],
            system=(
                "Tu es un analyste SOC expert. Analyse ces métriques et événements de sécurité. "
                "Donne : 1) État général du système, 2) Incidents notables, 3) Tendances, "
                "4) Recommandations prioritaires. Sois direct et concis."
            ),
            max_tokens=800,
        )
    except Exception as e:
        analysis = f"Analyse indisponible: {e}"

    return {
        "period_hours": hours,
        "stats": counts,
        "avg_cpu_pct": round(avg_cpu, 1),
        "avg_ram_pct": round(avg_ram, 1),
        "avg_health_score": round(avg_score, 1),
        "total_events": len(events),
        "analysis": analysis,
        "events": [
            {
                "timestamp": e.timestamp.isoformat(),
                "severity": e.severity,
                "category": e.category,
                "title": e.title,
            }
            for e in events[:50]
        ],
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_recent_events(db, limit=5, min_severity="HIGH") -> list[dict]:
    _order = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]
    _idx = _order.index(min_severity) if min_severity in _order else 0
    severities = _order[:_idx + 1]

    try:
        from database.models import SecurityEventLog
        rows = (
            db.query(SecurityEventLog)
            .filter(SecurityEventLog.severity.in_(severities))
            .order_by(SecurityEventLog.timestamp.desc())
            .limit(limit)
            .all()
        )
        return [{"title": r.title, "severity": r.severity, "ts": r.timestamp.isoformat()} for r in rows]
    except Exception:
        return []
