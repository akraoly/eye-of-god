"""
SIEM Engine — Security Information & Event Management.
Ingestion d'événements, règles de corrélation Sigma-like, génération d'alertes.
Portage depuis AEGIS AI v3.0.
"""
from __future__ import annotations
import json
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from database.models import SiemEvent, SiemRule, Alert
from core.soc.alert_engine import alert_engine
import logging

log = logging.getLogger("SOC.SIEM")

# ── Règles intégrées (portées depuis AEGIS AI) ────────────────────────────
BUILTIN_RULES = [
    {
        "name": "Brute Force Multi-Source",
        "description": "5+ tentatives depuis la même IP en 5 minutes",
        "rule_type": "THRESHOLD",
        "conditions": json.dumps({"event_types": ["BRUTE_FORCE"], "group_by": "src_ip"}),
        "timewindow": 300, "threshold": 5,
        "severity": "HIGH", "category": "BRUTE_FORCE",
        "mitre_tactic": "TA0006", "mitre_technique": "T1110",
    },
    {
        "name": "Reconnaissance → Exploitation",
        "description": "Scan de ports suivi d'une intrusion en 30 minutes",
        "rule_type": "SEQUENCE",
        "conditions": json.dumps({"sequence": ["PORT_SCAN", "INTRUSION"], "src_ip_match": True}),
        "timewindow": 1800, "threshold": 1,
        "severity": "CRITICAL", "category": "INTRUSION",
        "mitre_tactic": "TA0043", "mitre_technique": "T1046",
    },
    {
        "name": "Lateral Movement",
        "description": "Même IP sur 3+ hôtes en 10 minutes",
        "rule_type": "AGGREGATION",
        "conditions": json.dumps({"group_by": "src_ip", "count_distinct": "hostname", "min_count": 3}),
        "timewindow": 600, "threshold": 3,
        "severity": "CRITICAL", "category": "LATERAL_MOVEMENT",
        "mitre_tactic": "TA0008", "mitre_technique": "T1021",
    },
    {
        "name": "Data Exfiltration Burst",
        "description": "Exfiltration massive (10+ events en 5 min)",
        "rule_type": "THRESHOLD",
        "conditions": json.dumps({"event_types": ["DATA_EXFILTRATION"]}),
        "timewindow": 300, "threshold": 10,
        "severity": "CRITICAL", "category": "DATA_EXFILTRATION",
        "mitre_tactic": "TA0010", "mitre_technique": "T1048",
    },
    {
        "name": "Port Scan Détecté",
        "description": "Scan de ports depuis une IP externe",
        "rule_type": "THRESHOLD",
        "conditions": json.dumps({"event_types": ["PORT_SCAN"]}),
        "timewindow": 60, "threshold": 3,
        "severity": "MEDIUM", "category": "PORT_SCAN",
        "mitre_tactic": "TA0043", "mitre_technique": "T1595",
    },
    {
        "name": "Privilege Escalation",
        "description": "Tentative d'escalade de privilèges",
        "rule_type": "THRESHOLD",
        "conditions": json.dumps({"event_types": ["PRIVILEGE_ESCALATION"]}),
        "timewindow": 300, "threshold": 1,
        "severity": "HIGH", "category": "PRIVILEGE_ESCALATION",
        "mitre_tactic": "TA0004", "mitre_technique": "T1548",
    },
    {
        "name": "C2 Communication",
        "description": "Communication Command & Control détectée",
        "rule_type": "THRESHOLD",
        "conditions": json.dumps({"event_types": ["C2"]}),
        "timewindow": 300, "threshold": 1,
        "severity": "CRITICAL", "category": "C2",
        "mitre_tactic": "TA0011", "mitre_technique": "T1071",
    },
    {
        "name": "Malware Activity",
        "description": "Activité malware détectée",
        "rule_type": "THRESHOLD",
        "conditions": json.dumps({"event_types": ["MALWARE"]}),
        "timewindow": 300, "threshold": 1,
        "severity": "CRITICAL", "category": "MALWARE",
        "mitre_tactic": "TA0002", "mitre_technique": "T1059",
    },
]


class SiemEngine:

    def init_rules(self, db: Session):
        """Initialise les règles intégrées si absentes."""
        for rule_def in BUILTIN_RULES:
            exists = db.query(SiemRule).filter(SiemRule.name == rule_def["name"]).first()
            if not exists:
                rule = SiemRule(**rule_def, enabled=True)
                db.add(rule)
        db.commit()
        log.info(f"[SIEM] {len(BUILTIN_RULES)} règles initialisées")

    def ingest(self, db: Session, event_type: str, source: str,
               src_ip: str = None, dst_ip: str = None,
               hostname: str = None, severity: str = "LOW",
               data: dict = None) -> dict:
        """Ingère un événement et déclenche la corrélation."""
        event = SiemEvent(
            event_type=event_type.upper(),
            source=source,
            src_ip=src_ip,
            dst_ip=dst_ip,
            hostname=hostname,
            severity=severity.upper(),
            data=json.dumps(data or {}),
        )
        db.add(event)
        db.commit()
        db.refresh(event)

        # Tenter la corrélation
        triggered = self._correlate(db, event)
        return {"event_id": event.id, "correlated": len(triggered) > 0,
                "alerts_created": len(triggered)}

    def _correlate(self, db: Session, event: SiemEvent) -> list:
        """Applique les règles actives à l'événement ingéré."""
        rules = db.query(SiemRule).filter(SiemRule.enabled == True).all()
        triggered = []
        for rule in rules:
            try:
                cond = json.loads(rule.conditions)
                since = datetime.utcnow() - timedelta(seconds=rule.timewindow)

                if rule.rule_type == "THRESHOLD":
                    event_types = cond.get("event_types", [])
                    if event.event_type not in event_types:
                        continue
                    # Compter les événements récents du même type
                    q = db.query(SiemEvent).filter(
                        SiemEvent.event_type == event.event_type,
                        SiemEvent.timestamp >= since,
                    )
                    if cond.get("group_by") == "src_ip" and event.src_ip:
                        q = q.filter(SiemEvent.src_ip == event.src_ip)
                    count = q.count()
                    if count >= rule.threshold:
                        alert = alert_engine.create(
                            db=db,
                            severity=rule.severity,
                            category=rule.category,
                            title=f"[SIEM] {rule.name}",
                            description=f"{rule.description} — {count} événements en {rule.timewindow}s",
                            source_ip=event.src_ip,
                            mitre_tactic=rule.mitre_tactic,
                            mitre_technique=rule.mitre_technique,
                            source_engine="siem",
                        )
                        rule.hit_count = (rule.hit_count or 0) + 1
                        rule.last_hit = datetime.utcnow()
                        event.correlated = True
                        event.alert_id = alert.id
                        db.commit()
                        triggered.append(alert.id)

            except Exception as e:
                log.warning(f"[SIEM] Règle {rule.name} erreur: {e}")
        return triggered

    def get_events(self, db: Session, hours: int = 24, event_type: str = None,
                   page: int = 1, per_page: int = 50) -> dict:
        since = datetime.utcnow() - timedelta(hours=hours)
        q = db.query(SiemEvent).filter(SiemEvent.timestamp >= since).order_by(desc(SiemEvent.timestamp))
        if event_type: q = q.filter(SiemEvent.event_type == event_type.upper())
        total = q.count()
        events = q.offset((page - 1) * per_page).limit(per_page).all()
        return {
            "total": total, "page": page, "per_page": per_page,
            "events": [self._evt_dict(e) for e in events],
        }

    def get_rules(self, db: Session) -> list:
        rules = db.query(SiemRule).order_by(SiemRule.name).all()
        return [{
            "id": r.id, "name": r.name, "description": r.description,
            "rule_type": r.rule_type, "severity": r.severity,
            "category": r.category, "mitre_tactic": r.mitre_tactic,
            "mitre_technique": r.mitre_technique, "enabled": r.enabled,
            "hit_count": r.hit_count,
            "last_hit": r.last_hit.isoformat() if r.last_hit else None,
        } for r in rules]

    def timeline(self, db: Session, hours: int = 24) -> list:
        """Timeline des événements groupés par heure."""
        since = datetime.utcnow() - timedelta(hours=hours)
        rows = db.query(
            func.strftime('%Y-%m-%dT%H:00:00', SiemEvent.timestamp).label("hour"),
            SiemEvent.event_type,
            func.count(SiemEvent.id).label("count"),
        ).filter(SiemEvent.timestamp >= since).group_by("hour", SiemEvent.event_type).all()
        return [{"hour": r.hour, "event_type": r.event_type, "count": r.count} for r in rows]

    def _evt_dict(self, e: SiemEvent) -> dict:
        return {
            "id": e.id, "timestamp": e.timestamp.isoformat(),
            "event_type": e.event_type, "source": e.source,
            "src_ip": e.src_ip, "dst_ip": e.dst_ip, "hostname": e.hostname,
            "severity": e.severity, "correlated": e.correlated,
        }


siem_engine = SiemEngine()
