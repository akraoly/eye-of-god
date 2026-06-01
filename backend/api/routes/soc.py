"""
Routes /api/soc — SOC complet : alertes, incidents, SIEM, SOAR, MITRE, dashboard.
"""
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session
from database.db import get_db
from core.soc.alert_engine    import alert_engine
from core.soc.incident_engine import incident_engine
from core.soc.siem_engine     import siem_engine
from core.soc.soar_engine     import soar_engine
from core.soc.mitre_engine    import mitre_engine

router = APIRouter()


# ── Dashboard ────────────────────────────────────────────────────────────────

@router.get("/dashboard")
def get_dashboard(db: Session = Depends(get_db)):
    return {
        "alerts":    alert_engine.stats(db, hours=24),
        "incidents": incident_engine.stats(db),
        "mitre":     mitre_engine.stats(),
        "soar":      {"playbooks": len(soar_engine.list_playbooks())},
        "siem":      {"rules": len(siem_engine.get_rules(db))},
    }


# ── Alertes ──────────────────────────────────────────────────────────────────

class AlertCreate(BaseModel):
    severity: str
    category: str
    title: str
    description: Optional[str] = None
    source_ip: Optional[str] = None
    destination_ip: Optional[str] = None
    port: Optional[int] = None
    protocol: Optional[str] = None
    mitre_tactic: Optional[str] = None
    mitre_technique: Optional[str] = None
    source_engine: str = "manual"
    raw_data: Optional[dict] = None


class AlertStatusUpdate(BaseModel):
    status: str
    incident_id: Optional[int] = None


@router.get("/alerts")
def list_alerts(
    severity: Optional[str] = Query(None),
    status: Optional[str]   = Query(None),
    category: Optional[str] = Query(None),
    hours: Optional[int]    = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, le=200),
    db: Session = Depends(get_db),
):
    return alert_engine.list(db, severity=severity, status=status,
                             category=category, hours=hours, page=page, per_page=per_page)


@router.post("/alerts")
def create_alert(body: AlertCreate, db: Session = Depends(get_db)):
    a = alert_engine.create(db, **body.model_dump())
    return alert_engine._to_dict(a)


@router.get("/alerts/stats")
def alert_stats(hours: int = Query(24), db: Session = Depends(get_db)):
    return alert_engine.stats(db, hours=hours)


@router.get("/alerts/{alert_id}")
def get_alert(alert_id: int, db: Session = Depends(get_db)):
    a = alert_engine.get(db, alert_id)
    if not a: return {"error": "Alerte introuvable"}
    return alert_engine._to_dict(a)


@router.patch("/alerts/{alert_id}")
def update_alert(alert_id: int, body: AlertStatusUpdate, db: Session = Depends(get_db)):
    a = alert_engine.update_status(db, alert_id, body.status, body.incident_id)
    if not a: return {"error": "Alerte introuvable"}
    return alert_engine._to_dict(a)


# ── Incidents ─────────────────────────────────────────────────────────────────

class IncidentCreate(BaseModel):
    title: str
    severity: str
    description: Optional[str] = None
    affected_systems: Optional[str] = None
    attack_vector: Optional[str] = None
    alert_ids: Optional[list] = None
    playbook_id: Optional[str] = None


class IncidentUpdate(BaseModel):
    status: Optional[str] = None
    priority: Optional[int] = None
    description: Optional[str] = None
    affected_systems: Optional[str] = None
    impact_assessment: Optional[str] = None
    remediation_steps: Optional[str] = None
    resolution_notes: Optional[str] = None
    mitre_tactics: Optional[str] = None
    playbook_id: Optional[str] = None


@router.get("/incidents")
def list_incidents(
    status: Optional[str]   = Query(None),
    severity: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, le=100),
    db: Session = Depends(get_db),
):
    return incident_engine.list(db, status=status, severity=severity,
                                page=page, per_page=per_page)


@router.post("/incidents")
def create_incident(body: IncidentCreate, db: Session = Depends(get_db)):
    inc = incident_engine.create(db, **body.model_dump())
    return incident_engine._to_dict(inc)


@router.get("/incidents/stats")
def incident_stats(db: Session = Depends(get_db)):
    return incident_engine.stats(db)


@router.get("/incidents/{incident_id}")
def get_incident(incident_id: int, db: Session = Depends(get_db)):
    inc = incident_engine.get(db, incident_id)
    if not inc: return {"error": "Incident introuvable"}
    return incident_engine._to_dict(inc)


@router.patch("/incidents/{incident_id}")
def update_incident(incident_id: int, body: IncidentUpdate, db: Session = Depends(get_db)):
    inc = incident_engine.update(db, incident_id, **body.model_dump(exclude_none=True))
    if not inc: return {"error": "Incident introuvable"}
    return incident_engine._to_dict(inc)


# ── SIEM ─────────────────────────────────────────────────────────────────────

class SiemIngest(BaseModel):
    event_type: str
    source: str
    src_ip: Optional[str] = None
    dst_ip: Optional[str] = None
    hostname: Optional[str] = None
    severity: str = "LOW"
    data: Optional[dict] = None


@router.post("/siem/events")
def ingest_event(body: SiemIngest, db: Session = Depends(get_db)):
    siem_engine.init_rules(db)
    return siem_engine.ingest(db, **body.model_dump())


@router.get("/siem/events")
def get_events(
    hours: int = Query(24), event_type: Optional[str] = Query(None),
    page: int = Query(1), per_page: int = Query(50, le=200),
    db: Session = Depends(get_db),
):
    return siem_engine.get_events(db, hours=hours, event_type=event_type,
                                  page=page, per_page=per_page)


@router.get("/siem/rules")
def get_rules(db: Session = Depends(get_db)):
    siem_engine.init_rules(db)
    return {"rules": siem_engine.get_rules(db)}


@router.post("/siem/init")
def init_siem(db: Session = Depends(get_db)):
    siem_engine.init_rules(db)
    return {"message": "SIEM initialisé", "rules": len(siem_engine.get_rules(db))}


@router.get("/siem/timeline")
def get_timeline(hours: int = Query(24), db: Session = Depends(get_db)):
    return {"timeline": siem_engine.timeline(db, hours=hours)}


# ── SOAR ─────────────────────────────────────────────────────────────────────

class SoarExecute(BaseModel):
    step: int
    context: Optional[dict] = None


@router.get("/soar/playbooks")
def list_playbooks(category: Optional[str] = Query(None)):
    return {"playbooks": soar_engine.list_playbooks(category)}


@router.get("/soar/playbooks/{playbook_id}")
def get_playbook(playbook_id: str):
    pb = soar_engine.get_playbook(playbook_id)
    if not pb: return {"error": "Playbook introuvable"}
    return pb


@router.get("/soar/recommend")
def recommend_playbook(category: str = Query(...), severity: str = Query("HIGH")):
    rec = soar_engine.recommend(category, severity)
    if not rec: return {"message": "Aucun playbook pour cette combinaison"}
    return rec


@router.post("/soar/playbooks/{playbook_id}/execute")
def execute_step(playbook_id: str, body: SoarExecute):
    return soar_engine.execute_step(playbook_id, body.step, body.context)


# ── MITRE ATT&CK ─────────────────────────────────────────────────────────────

@router.get("/mitre/matrix")
def get_matrix():
    return mitre_engine.get_matrix()


@router.get("/mitre/stats")
def mitre_stats():
    return mitre_engine.stats()


@router.get("/mitre/coverage")
def mitre_coverage():
    return mitre_engine.get_coverage()


@router.get("/mitre/technique/{technique_id}")
def get_technique(technique_id: str):
    t = mitre_engine.get_technique(technique_id)
    if not t: return {"error": "Technique introuvable"}
    return t


@router.post("/mitre/search")
def search_mitre(body: dict):
    query = body.get("q", "")
    if not query: return {"error": "Paramètre 'q' requis"}
    return {"results": mitre_engine.search(query)}
