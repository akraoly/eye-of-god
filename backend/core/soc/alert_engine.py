"""
AlertEngine — Création, gestion et statistiques des alertes de sécurité.
Portage depuis AEGIS AI, adapté à l'architecture L'Œil de Dieu.
"""
from __future__ import annotations
import json
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from database.models import Alert
import logging

log = logging.getLogger("SOC.Alert")

SEVERITIES = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
CATEGORIES = [
    "PORT_SCAN", "BRUTE_FORCE", "DOS_ATTACK", "ANOMALY",
    "MALWARE", "INTRUSION", "UNAUTHORIZED_ACCESS",
    "DATA_EXFILTRATION", "LATERAL_MOVEMENT", "PHISHING",
    "RANSOMWARE", "PRIVILEGE_ESCALATION", "C2", "OTHER",
]
STATUSES = ["NEW", "ACKNOWLEDGED", "IN_PROGRESS", "RESOLVED", "FALSE_POSITIVE"]


class AlertEngine:

    def create(self, db: Session, severity: str, category: str, title: str,
               description: str = None, source_ip: str = None,
               destination_ip: str = None, port: int = None,
               protocol: str = None, raw_data: dict = None,
               mitre_tactic: str = None, mitre_technique: str = None,
               source_engine: str = "manual") -> Alert:
        alert = Alert(
            severity=severity.upper(),
            category=category.upper(),
            title=title,
            description=description,
            source_ip=source_ip,
            destination_ip=destination_ip,
            affected_port=port,
            protocol=protocol,
            raw_data=json.dumps(raw_data) if raw_data else None,
            mitre_tactic=mitre_tactic,
            mitre_technique=mitre_technique,
            source_engine=source_engine,
            status="NEW",
        )
        db.add(alert)
        db.commit()
        db.refresh(alert)
        log.info(f"[ALERT] {severity} | {category} | {title}")
        return alert

    def list(self, db: Session, severity: str = None, status: str = None,
             category: str = None, hours: int = None,
             page: int = 1, per_page: int = 50) -> dict:
        q = db.query(Alert).order_by(desc(Alert.timestamp))
        if severity: q = q.filter(Alert.severity == severity.upper())
        if status:   q = q.filter(Alert.status   == status.upper())
        if category: q = q.filter(Alert.category == category.upper())
        if hours:
            since = datetime.utcnow() - timedelta(hours=hours)
            q = q.filter(Alert.timestamp >= since)

        total = q.count()
        alerts = q.offset((page - 1) * per_page).limit(per_page).all()
        return {"total": total, "page": page, "per_page": per_page,
                "alerts": [self._to_dict(a) for a in alerts]}

    def get(self, db: Session, alert_id: int) -> Optional[Alert]:
        return db.query(Alert).filter(Alert.id == alert_id).first()

    def update_status(self, db: Session, alert_id: int, status: str,
                      incident_id: int = None) -> Optional[Alert]:
        a = self.get(db, alert_id)
        if not a: return None
        a.status = status.upper()
        if incident_id: a.incident_id = incident_id
        db.commit()
        db.refresh(a)
        return a

    def stats(self, db: Session, hours: int = 24) -> dict:
        since = datetime.utcnow() - timedelta(hours=hours)
        q = db.query(Alert).filter(Alert.timestamp >= since)
        total = q.count()
        by_sev = {s: q.filter(Alert.severity == s).count() for s in SEVERITIES}
        by_cat = {}
        for row in db.query(Alert.category, func.count(Alert.id)).filter(
                Alert.timestamp >= since).group_by(Alert.category).all():
            by_cat[row[0]] = row[1]
        by_status = {s: q.filter(Alert.status == s).count() for s in STATUSES}
        # Top source IPs
        top_ips = db.query(Alert.source_ip, func.count(Alert.id).label("c")) \
            .filter(Alert.timestamp >= since, Alert.source_ip.isnot(None)) \
            .group_by(Alert.source_ip).order_by(desc("c")).limit(5).all()

        return {
            "period_hours": hours,
            "total": total,
            "by_severity": by_sev,
            "by_category": by_cat,
            "by_status": by_status,
            "top_source_ips": [{"ip": r[0], "count": r[1]} for r in top_ips],
            "critical_open": db.query(Alert).filter(
                Alert.severity == "CRITICAL", Alert.status == "NEW").count(),
        }

    def _to_dict(self, a: Alert) -> dict:
        return {
            "id": a.id, "uuid": a.alert_uuid,
            "timestamp": a.timestamp.isoformat() if a.timestamp else None,
            "severity": a.severity, "category": a.category,
            "title": a.title, "description": a.description,
            "source_ip": a.source_ip, "destination_ip": a.destination_ip,
            "port": a.affected_port, "protocol": a.protocol,
            "status": a.status,
            "mitre_tactic": a.mitre_tactic, "mitre_technique": a.mitre_technique,
            "incident_id": a.incident_id, "source_engine": a.source_engine,
        }


alert_engine = AlertEngine()
