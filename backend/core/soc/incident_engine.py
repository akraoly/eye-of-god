"""
IncidentEngine — Gestion des incidents de sécurité.
"""
from __future__ import annotations
import json
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc
from database.models import Incident, Alert
import logging

log = logging.getLogger("SOC.Incident")

STATUSES = ["OPEN", "INVESTIGATING", "CONTAINED", "RESOLVED", "CLOSED"]
SEVERITIES = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]


class IncidentEngine:

    def create(self, db: Session, title: str, severity: str,
               description: str = None, affected_systems: str = None,
               attack_vector: str = None, alert_ids: list = None,
               playbook_id: str = None) -> Incident:
        inc = Incident(
            title=title,
            severity=severity.upper(),
            description=description,
            affected_systems=affected_systems,
            attack_vector=attack_vector,
            alert_ids=json.dumps(alert_ids or []),
            playbook_id=playbook_id,
            status="OPEN",
            opened_at=datetime.utcnow(),
        )
        db.add(inc)
        db.commit()
        db.refresh(inc)

        # Lier les alertes à cet incident
        if alert_ids:
            db.query(Alert).filter(Alert.id.in_(alert_ids)).update(
                {"incident_id": inc.id}, synchronize_session=False)
            db.commit()

        log.info(f"[INCIDENT] #{inc.id} {severity} | {title}")
        return inc

    def list(self, db: Session, status: str = None, severity: str = None,
             page: int = 1, per_page: int = 20) -> dict:
        q = db.query(Incident).order_by(desc(Incident.opened_at))
        if status:   q = q.filter(Incident.status   == status.upper())
        if severity: q = q.filter(Incident.severity == severity.upper())
        total = q.count()
        items = q.offset((page - 1) * per_page).limit(per_page).all()
        return {"total": total, "page": page, "per_page": per_page,
                "incidents": [self._to_dict(i) for i in items]}

    def get(self, db: Session, incident_id: int) -> Optional[Incident]:
        return db.query(Incident).filter(Incident.id == incident_id).first()

    def update(self, db: Session, incident_id: int, **kwargs) -> Optional[Incident]:
        inc = self.get(db, incident_id)
        if not inc: return None
        allowed = {"status", "priority", "description", "affected_systems",
                   "attack_vector", "impact_assessment", "remediation_steps",
                   "resolution_notes", "mitre_tactics", "playbook_id"}
        for k, v in kwargs.items():
            if k in allowed and v is not None:
                if k == "status":
                    v = v.upper()
                    if v in ("RESOLVED", "CLOSED"):
                        inc.resolved_at = datetime.utcnow()
                setattr(inc, k, v)
        inc.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(inc)
        return inc

    def stats(self, db: Session) -> dict:
        total = db.query(Incident).count()
        open_ = db.query(Incident).filter(Incident.status == "OPEN").count()
        by_sev = {s: db.query(Incident).filter(Incident.severity == s).count()
                  for s in SEVERITIES}
        by_status = {s: db.query(Incident).filter(Incident.status == s).count()
                     for s in STATUSES}
        return {"total": total, "open": open_,
                "by_severity": by_sev, "by_status": by_status}

    def _to_dict(self, i: Incident) -> dict:
        return {
            "id": i.id, "uuid": i.incident_uuid,
            "title": i.title, "description": i.description,
            "severity": i.severity, "status": i.status, "priority": i.priority,
            "affected_systems": i.affected_systems, "attack_vector": i.attack_vector,
            "impact_assessment": i.impact_assessment,
            "remediation_steps": i.remediation_steps,
            "resolution_notes": i.resolution_notes,
            "mitre_tactics": json.loads(i.mitre_tactics) if i.mitre_tactics else [],
            "alert_ids": json.loads(i.alert_ids) if i.alert_ids else [],
            "playbook_id": i.playbook_id,
            "opened_at": i.opened_at.isoformat() if i.opened_at else None,
            "resolved_at": i.resolved_at.isoformat() if i.resolved_at else None,
        }


incident_engine = IncidentEngine()
