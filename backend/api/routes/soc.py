"""
Routes /api/soc — SOC complet Phase 1 + 2 :
  alertes, incidents, SIEM, SOAR, MITRE, ML anomaly, EDR, NTA, threat intel, IDS, dashboard.
"""
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy.orm import Session
from database.db import get_db
from core.soc.alert_engine        import alert_engine
from core.soc.incident_engine     import incident_engine
from core.soc.siem_engine         import siem_engine
from core.soc.soar_engine         import soar_engine
from core.soc.mitre_engine        import mitre_engine
from core.soc.ml_engine           import ml_engine
from core.soc.edr_engine          import edr_engine
from core.soc.nta_engine          import nta_engine
from core.soc.threat_intel_engine import threat_intel_engine
from core.soc.ids_engine          import ids_engine

router = APIRouter()


# ── Dashboard (Phase 1+2 — défini en bas du fichier) ─────────────────────────


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


# ── ML ANOMALY ───────────────────────────────────────────────────────────────

@router.post("/ml/train")
def ml_train(db: Session = Depends(get_db)):
    return ml_engine.train(db)


@router.get("/ml/anomalies")
def ml_anomalies(
    hours: int = Query(24), min_score: float = Query(0),
    page: int = Query(1), per_page: int = Query(50, le=200),
    db: Session = Depends(get_db),
):
    return ml_engine.get_anomalies(db, hours=hours, min_score=min_score, page=page, per_page=per_page)


@router.get("/ml/stats")
def ml_stats(db: Session = Depends(get_db)):
    return ml_engine.stats(db)


# ── EDR ──────────────────────────────────────────────────────────────────────

class EdrAgentCreate(BaseModel):
    hostname: str
    ip: Optional[str] = None
    os: Optional[str] = None
    tags: Optional[List[str]] = None


class EdrEventCreate(BaseModel):
    hostname: str
    event_type: str
    severity: str = "MEDIUM"
    process: Optional[str] = None
    cmdline: Optional[str] = None
    mitre_tactic: Optional[str] = None
    mitre_tech: Optional[str] = None
    description: Optional[str] = None
    alert_id: Optional[int] = None


@router.get("/edr/agents")
def list_edr_agents(page: int = Query(1), per_page: int = Query(20),
                    db: Session = Depends(get_db)):
    return edr_engine.list_agents(db, page=page, per_page=per_page)


@router.post("/edr/agents")
def create_edr_agent(body: EdrAgentCreate, db: Session = Depends(get_db)):
    a = edr_engine.create_agent(db, hostname=body.hostname, ip=body.ip,
                                 os=body.os, tags=body.tags)
    return edr_engine._agent_dict(a)


@router.patch("/edr/agents/{agent_id}/status")
def update_edr_status(agent_id: int, body: dict, db: Session = Depends(get_db)):
    a = edr_engine.update_status(db, agent_id, body.get("status", "online"))
    if not a: return {"error": "Agent introuvable"}
    return edr_engine._agent_dict(a)


@router.get("/edr/events")
def list_edr_events(hours: int = Query(24), agent_id: Optional[int] = Query(None),
                    page: int = Query(1), per_page: int = Query(50),
                    db: Session = Depends(get_db)):
    return edr_engine.list_events(db, agent_id=agent_id, hours=hours, page=page, per_page=per_page)


@router.post("/edr/events")
def create_edr_event(body: EdrEventCreate, db: Session = Depends(get_db)):
    evt = edr_engine.ingest_event(db, **body.model_dump())
    return edr_engine._evt_dict(evt)


@router.get("/edr/stats")
def edr_stats(db: Session = Depends(get_db)):
    return edr_engine.stats(db)


# ── NTA ──────────────────────────────────────────────────────────────────────

class FlowCreate(BaseModel):
    src_ip: str
    dst_ip: str
    src_port: int = 0
    dst_port: int = 0
    protocol: str = "TCP"
    bytes_out: int = 0
    bytes_in:  int = 0
    packets:   int = 0
    duration_s: float = 0.0
    direction: str = "out"
    alert_id: Optional[int] = None


@router.post("/nta/flows")
def ingest_flow(body: FlowCreate, db: Session = Depends(get_db)):
    return nta_engine.ingest_flow(db, **body.model_dump())


@router.get("/nta/flows")
def get_nta_flows(hours: int = Query(24), threat_only: bool = Query(False),
                  page: int = Query(1), per_page: int = Query(50),
                  db: Session = Depends(get_db)):
    return nta_engine.get_flows(db, hours=hours, threat_only=threat_only, page=page, per_page=per_page)


@router.get("/nta/beaconing")
def detect_beaconing(hours: int = Query(6), db: Session = Depends(get_db)):
    return {"beaconing": nta_engine.detect_beaconing(db, hours=hours)}


@router.get("/nta/top-talkers")
def top_talkers(hours: int = Query(24), limit: int = Query(10),
                db: Session = Depends(get_db)):
    return {"top_talkers": nta_engine.top_talkers(db, hours=hours, limit=limit)}


@router.get("/nta/stats")
def nta_stats(hours: int = Query(24), db: Session = Depends(get_db)):
    return nta_engine.stats(db, hours=hours)


# ── THREAT INTELLIGENCE ───────────────────────────────────────────────────────

class IocCreate(BaseModel):
    ioc_type:    str
    value:       str
    threat_type: Optional[str] = None
    severity:    str = "MEDIUM"
    confidence:  int = 70
    source:      str = "manual"
    description: Optional[str] = None


@router.post("/threat-intel/init")
def init_iocs(db: Session = Depends(get_db)):
    n = threat_intel_engine.init_iocs(db)
    return {"message": f"{n} IOCs chargés"}


@router.get("/threat-intel/iocs")
def list_iocs(ioc_type: Optional[str] = Query(None),
              threat_type: Optional[str] = Query(None),
              page: int = Query(1), per_page: int = Query(50),
              db: Session = Depends(get_db)):
    return threat_intel_engine.list_iocs(db, ioc_type=ioc_type, threat_type=threat_type,
                                          page=page, per_page=per_page)


@router.post("/threat-intel/iocs")
def add_ioc(body: IocCreate, db: Session = Depends(get_db)):
    ioc = threat_intel_engine.add_ioc(db, **body.model_dump())
    return threat_intel_engine._ioc_dict(ioc)


@router.get("/threat-intel/check/ip/{ip}")
def check_ip(ip: str, db: Session = Depends(get_db)):
    result = threat_intel_engine.check_ip(db, ip)
    return result or {"status": "clean", "ip": ip}


@router.get("/threat-intel/check/domain/{domain}")
def check_domain(domain: str, db: Session = Depends(get_db)):
    result = threat_intel_engine.check_domain(db, domain)
    return result or {"status": "clean", "domain": domain}


@router.post("/threat-intel/scan")
def scan_alerts(hours: int = Query(24), db: Session = Depends(get_db)):
    return threat_intel_engine.scan_all_alerts(db, hours=hours)


@router.get("/threat-intel/hits")
def recent_hits(hours: int = Query(24), limit: int = Query(20),
                db: Session = Depends(get_db)):
    return {"hits": threat_intel_engine.get_recent_hits(db, hours=hours, limit=limit)}


@router.get("/threat-intel/stats")
def ti_stats(db: Session = Depends(get_db)):
    return threat_intel_engine.stats(db)


# ── IDS ──────────────────────────────────────────────────────────────────────

class IdsAnalyze(BaseModel):
    event_type: str
    src_ip: Optional[str] = None
    dst_port: Optional[int] = None
    data: Optional[dict] = None


@router.get("/ids/signatures")
def get_ids_signatures():
    return {"signatures": ids_engine.get_signatures()}


@router.post("/ids/analyze")
def ids_analyze(body: IdsAnalyze, db: Session = Depends(get_db)):
    triggered = ids_engine.analyze_event(db, **body.model_dump())
    return {"triggered": triggered, "count": len(triggered)}


@router.get("/ids/stats")
def ids_stats(db: Session = Depends(get_db)):
    return ids_engine.stats(db)


# ── DASHBOARD PHASE 2 ─────────────────────────────────────────────────────────

@router.get("/dashboard")
def get_dashboard(db: Session = Depends(get_db)):
    return {
        # Phase 1
        "alerts":    alert_engine.stats(db, hours=24),
        "incidents": incident_engine.stats(db),
        "mitre":     mitre_engine.stats(),
        "soar":      {"playbooks": len(soar_engine.list_playbooks())},
        "siem":      {"rules": len(siem_engine.get_rules(db))},
        # Phase 2
        "ml":        ml_engine.stats(db),
        "edr":       edr_engine.stats(db),
        "nta":       nta_engine.stats(db, hours=24),
        "threat_intel": threat_intel_engine.stats(db),
        "ids":       ids_engine.stats(db),
    }
