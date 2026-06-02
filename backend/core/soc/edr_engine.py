"""
EDR Engine — Endpoint Detection & Response.
Portage depuis AEGIS AI v3.0, adapté à L'Œil de Dieu.
Détection comportementale, scoring de risque, réponse.
"""
from __future__ import annotations
import json, random
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from database.models import EdrAgent, EdrEvent, Alert
import logging

log = logging.getLogger("SOC.EDR")

# Mapping alerte → événement EDR (MITRE)
_ALERT_TO_EVENT = {
    "PORT_SCAN":           ("NETWORK_CONNECT",       "Discovery",            "TA0007", "T1046"),
    "BRUTE_FORCE":         ("SUSPICIOUS_CMD",         "Credential Access",    "TA0006", "T1110"),
    "DOS_ATTACK":          ("NETWORK_CONNECT",        "Impact",               "TA0040", "T1498"),
    "MALWARE":             ("MALWARE_DETECT",         "Execution",            "TA0002", "T1059"),
    "INTRUSION":           ("PRIVILEGE_ESCALATION",   "Privilege Escalation", "TA0004", "T1068"),
    "UNAUTHORIZED_ACCESS": ("SUSPICIOUS_CMD",         "Initial Access",       "TA0001", "T1078"),
    "DATA_EXFILTRATION":   ("DATA_EXFIL",             "Exfiltration",         "TA0010", "T1041"),
    "LATERAL_MOVEMENT":    ("LATERAL_MOVEMENT",       "Lateral Movement",     "TA0008", "T1021"),
    "RANSOMWARE":          ("MALWARE_DETECT",         "Impact",               "TA0040", "T1486"),
    "PRIVILEGE_ESCALATION":("PRIVILEGE_ESCALATION",   "Privilege Escalation", "TA0004", "T1548"),
    "C2":                  ("NETWORK_CONNECT",        "Command and Control",  "TA0011", "T1071"),
    "ANOMALY":             ("ANOMALY",                "Defense Evasion",      "TA0005", "T1036"),
    "OTHER":               ("PROCESS_CREATE",         "Execution",            "TA0002", "T1059"),
}

_SUSPICIOUS_PROCS = {
    "MALWARE_DETECT":       ["powershell.exe", "cmd.exe", "wscript.exe", "mshta.exe"],
    "PRIVILEGE_ESCALATION": ["net.exe", "whoami.exe", "runas.exe", "sudo"],
    "SUSPICIOUS_CMD":       ["mimikatz.exe", "psexec.exe", "nc.exe", "ncat"],
    "DATA_EXFIL":           ["curl", "wget", "ftp.exe", "scp"],
    "LATERAL_MOVEMENT":     ["psexec.exe", "wmic.exe", "mstsc.exe", "ssh"],
    "NETWORK_CONNECT":      ["nmap", "masscan", "zmap", "hping3"],
    "PROCESS_CREATE":       ["powershell.exe", "bash", "python3", "perl"],
    "ANOMALY":              ["unknown.exe", "svchost32.exe", "lsas.exe"],
}

_OS_LIST = ["Linux 6.1 (Debian)", "Ubuntu 22.04", "Windows Server 2022",
            "Windows 11", "Kali Linux 2024", "CentOS 8", "Fedora 39"]


class EdrEngine:

    # ── Agents ────────────────────────────────────────────────────────────
    def create_agent(self, db: Session, hostname: str, ip: str = None,
                     os: str = None, tags: list = None) -> EdrAgent:
        existing = db.query(EdrAgent).filter(EdrAgent.hostname == hostname).first()
        if existing:
            existing.last_seen = datetime.utcnow()
            if ip: existing.ip_address = ip
            db.commit()
            return existing
        agent = EdrAgent(
            hostname=hostname, ip_address=ip,
            os=os or random.choice(_OS_LIST),
            status="online", risk_score=0.0,
            tags=json.dumps(tags or []),
        )
        db.add(agent); db.commit(); db.refresh(agent)
        log.info(f"[EDR] Nouvel agent: {hostname}")
        return agent

    def list_agents(self, db: Session, page=1, per_page=20) -> dict:
        q = db.query(EdrAgent).order_by(desc(EdrAgent.risk_score))
        total = q.count()
        agents = q.offset((page-1)*per_page).limit(per_page).all()
        return {"total": total, "agents": [self._agent_dict(a) for a in agents]}

    def get_agent(self, db: Session, agent_id: int) -> Optional[EdrAgent]:
        return db.query(EdrAgent).filter(EdrAgent.id == agent_id).first()

    def update_status(self, db: Session, agent_id: int, status: str) -> Optional[EdrAgent]:
        a = self.get_agent(db, agent_id)
        if not a: return None
        a.status = status; a.last_seen = datetime.utcnow()
        db.commit(); db.refresh(a)
        return a

    # ── Événements ────────────────────────────────────────────────────────
    def ingest_event(self, db: Session, hostname: str, event_type: str,
                     severity: str = "MEDIUM", process: str = None,
                     cmdline: str = None, mitre_tactic: str = None,
                     mitre_tech: str = None, description: str = None,
                     alert_id: int = None) -> EdrEvent:
        # Trouver ou créer l'agent
        agent = db.query(EdrAgent).filter(EdrAgent.hostname == hostname).first()
        agent_id = agent.id if agent else None

        evt = EdrEvent(
            agent_id=agent_id, hostname=hostname,
            event_type=event_type.upper(), severity=severity.upper(),
            process_name=process, command_line=cmdline,
            mitre_tactic=mitre_tactic, mitre_tech=mitre_tech,
            description=description, alert_id=alert_id,
        )
        db.add(evt); db.commit(); db.refresh(evt)

        # Mettre à jour le risk_score de l'agent
        if agent:
            self._update_risk(db, agent)

        return evt

    def ingest_from_alert(self, db: Session, alert: Alert,
                          hostname: str = None) -> Optional[EdrEvent]:
        """Génère un événement EDR depuis une alerte SOC."""
        if not hostname:
            hostname = f"host-{alert.destination_ip or 'unknown'}"
        mapping = _ALERT_TO_EVENT.get(alert.category, ("PROCESS_CREATE", "Execution", "TA0002", "T1059"))
        evt_type, tactic_name, tactic_id, tech_id = mapping
        proc = random.choice(_SUSPICIOUS_PROCS.get(evt_type, ["unknown.exe"]))
        return self.ingest_event(
            db=db, hostname=hostname, event_type=evt_type,
            severity=alert.severity, process=proc,
            mitre_tactic=tactic_id, mitre_tech=tech_id,
            description=f"Dérivé de l'alerte #{alert.id}: {alert.title}",
            alert_id=alert.id,
        )

    def _update_risk(self, db: Session, agent: EdrAgent):
        """Recalcule le risk score d'un agent basé sur ses événements récents."""
        since  = datetime.utcnow() - timedelta(hours=24)
        evts   = db.query(EdrEvent).filter(
            EdrEvent.agent_id == agent.id,
            EdrEvent.timestamp >= since,
        ).all()
        sev_w  = {"LOW": 5, "MEDIUM": 15, "HIGH": 30, "CRITICAL": 50}
        score  = sum(sev_w.get(e.severity, 5) for e in evts)
        agent.risk_score = min(100.0, float(score))
        if score >= 70:
            agent.status = "compromised"
        db.commit()

    def list_events(self, db: Session, agent_id: int = None, hours: int = 24,
                    page=1, per_page=50) -> dict:
        since = datetime.utcnow() - timedelta(hours=hours)
        q = db.query(EdrEvent).filter(EdrEvent.timestamp >= since).order_by(desc(EdrEvent.timestamp))
        if agent_id: q = q.filter(EdrEvent.agent_id == agent_id)
        total = q.count()
        evts  = q.offset((page-1)*per_page).limit(per_page).all()
        return {"total": total, "events": [self._evt_dict(e) for e in evts]}

    def stats(self, db: Session) -> dict:
        total_agents    = db.query(EdrAgent).count()
        compromised     = db.query(EdrAgent).filter(EdrAgent.status == "compromised").count()
        isolated        = db.query(EdrAgent).filter(EdrAgent.status == "isolated").count()
        since24         = datetime.utcnow() - timedelta(hours=24)
        events_24h      = db.query(EdrEvent).filter(EdrEvent.timestamp >= since24).count()
        critical_events = db.query(EdrEvent).filter(
            EdrEvent.timestamp >= since24, EdrEvent.severity == "CRITICAL").count()
        high_risk_hosts = db.query(EdrAgent).filter(EdrAgent.risk_score >= 70).count()
        return {
            "total_agents": total_agents, "compromised": compromised,
            "isolated": isolated, "events_24h": events_24h,
            "critical_events_24h": critical_events,
            "high_risk_hosts": high_risk_hosts,
        }

    def _agent_dict(self, a: EdrAgent) -> dict:
        return {"id": a.id, "hostname": a.hostname, "ip": a.ip_address,
                "os": a.os, "status": a.status, "risk_score": a.risk_score,
                "last_seen": a.last_seen.isoformat() if a.last_seen else None,
                "tags": json.loads(a.tags) if a.tags else []}

    def _evt_dict(self, e: EdrEvent) -> dict:
        return {"id": e.id, "agent_id": e.agent_id, "hostname": e.hostname,
                "event_type": e.event_type, "severity": e.severity,
                "process": e.process_name, "cmdline": e.command_line,
                "mitre_tactic": e.mitre_tactic, "mitre_tech": e.mitre_tech,
                "description": e.description, "alert_id": e.alert_id,
                "timestamp": e.timestamp.isoformat() if e.timestamp else None}


edr_engine = EdrEngine()
