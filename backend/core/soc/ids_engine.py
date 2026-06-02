"""
IDS Engine — Intrusion Detection System.
Détection réseau légère (pas de Scapy live — analyse de paquets simulée ou depuis alertes).
Portage adapté depuis AEGIS AI scapy_engine.py.
"""
from __future__ import annotations
import json, re
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from database.models import SiemEvent, Alert
from core.soc.alert_engine import alert_engine
import logging

log = logging.getLogger("SOC.IDS")

# ── Signatures IDS ────────────────────────────────────────────────────────
IDS_SIGNATURES = [
    {
        "sid": "1001", "name": "Port Scan TCP SYN Flood",
        "pattern": {"event_type": "PORT_SCAN", "threshold": 20, "window": 60},
        "severity": "HIGH", "category": "PORT_SCAN",
        "mitre": ("TA0043", "T1595"), "description": "Scan SYN massif détecté",
    },
    {
        "sid": "1002", "name": "SSH Brute Force",
        "pattern": {"event_type": "BRUTE_FORCE", "port": 22, "threshold": 10, "window": 60},
        "severity": "HIGH", "category": "BRUTE_FORCE",
        "mitre": ("TA0006", "T1110"), "description": "Brute force SSH détecté (10+ tentatives/min)",
    },
    {
        "sid": "1003", "name": "RDP Brute Force",
        "pattern": {"event_type": "BRUTE_FORCE", "port": 3389, "threshold": 5, "window": 60},
        "severity": "HIGH", "category": "BRUTE_FORCE",
        "mitre": ("TA0006", "T1110"), "description": "Brute force RDP détecté",
    },
    {
        "sid": "1004", "name": "C2 Beacon Detected",
        "pattern": {"event_type": "C2", "threshold": 1, "window": 300},
        "severity": "CRITICAL", "category": "C2",
        "mitre": ("TA0011", "T1071"), "description": "Communication C2 détectée",
    },
    {
        "sid": "1005", "name": "Malware Callback",
        "pattern": {"event_type": "MALWARE", "threshold": 1, "window": 60},
        "severity": "CRITICAL", "category": "MALWARE",
        "mitre": ("TA0002", "T1059"), "description": "Activité malware détectée",
    },
    {
        "sid": "1006", "name": "Data Exfiltration",
        "pattern": {"event_type": "DATA_EXFILTRATION", "threshold": 1, "window": 300},
        "severity": "CRITICAL", "category": "DATA_EXFILTRATION",
        "mitre": ("TA0010", "T1048"), "description": "Exfiltration de données détectée",
    },
    {
        "sid": "1007", "name": "Lateral Movement",
        "pattern": {"event_type": "LATERAL_MOVEMENT", "threshold": 1, "window": 300},
        "severity": "HIGH", "category": "LATERAL_MOVEMENT",
        "mitre": ("TA0008", "T1021"), "description": "Mouvement latéral détecté",
    },
    {
        "sid": "1008", "name": "Privilege Escalation",
        "pattern": {"event_type": "PRIVILEGE_ESCALATION", "threshold": 1, "window": 60},
        "severity": "HIGH", "category": "PRIVILEGE_ESCALATION",
        "mitre": ("TA0004", "T1548"), "description": "Escalade de privilèges détectée",
    },
    {
        "sid": "1009", "name": "SQL Injection Probe",
        "pattern": {"event_type": "INTRUSION", "threshold": 3, "window": 60},
        "severity": "HIGH", "category": "INTRUSION",
        "mitre": ("TA0001", "T1190"), "description": "Probe d'injection SQL détecté",
    },
    {
        "sid": "1010", "name": "Ransomware Activity",
        "pattern": {"event_type": "RANSOMWARE", "threshold": 1, "window": 60},
        "severity": "CRITICAL", "category": "RANSOMWARE",
        "mitre": ("TA0040", "T1486"), "description": "Activité ransomware détectée",
    },
]


class IdsEngine:

    def analyze_event(self, db: Session, event_type: str, src_ip: str = None,
                      dst_port: int = None, data: dict = None) -> list:
        """
        Analyse un événement réseau et déclenche les signatures IDS.
        Retourne la liste des alertes créées.
        """
        triggered = []
        since_60  = datetime.utcnow() - timedelta(seconds=60)
        since_300 = datetime.utcnow() - timedelta(seconds=300)

        for sig in IDS_SIGNATURES:
            p = sig["pattern"]
            if p["event_type"] != event_type.upper():
                continue

            window = timedelta(seconds=p.get("window", 60))
            since  = datetime.utcnow() - window
            threshold = p.get("threshold", 1)

            # Compter les événements récents du même type
            q = db.query(SiemEvent).filter(
                SiemEvent.event_type == event_type.upper(),
                SiemEvent.timestamp  >= since,
            )
            if src_ip:
                q = q.filter(SiemEvent.src_ip == src_ip)
            count = q.count()

            if count >= threshold:
                # Vérifier qu'on n'a pas déjà déclenché cette alerte récemment
                recent = db.query(Alert).filter(
                    Alert.title.like(f"%[IDS SID:{sig['sid']}]%"),
                    Alert.created_at >= since,
                    Alert.source_ip  == src_ip,
                ).count()
                if recent == 0:
                    alert = alert_engine.create(
                        db=db,
                        severity=sig["severity"],
                        category=sig["category"],
                        title=f"[IDS SID:{sig['sid']}] {sig['name']}",
                        description=f"{sig['description']} — {count} événements en {p['window']}s",
                        source_ip=src_ip,
                        mitre_tactic=sig["mitre"][0],
                        mitre_technique=sig["mitre"][1],
                        source_engine="ids",
                    )
                    triggered.append({"sid": sig["sid"], "name": sig["name"],
                                      "alert_id": alert.id})
                    log.info(f"[IDS] SID:{sig['sid']} {sig['name']} → alerte #{alert.id}")
        return triggered

    def get_signatures(self) -> list:
        return [{"sid": s["sid"], "name": s["name"],
                 "severity": s["severity"], "category": s["category"],
                 "mitre_tactic": s["mitre"][0], "mitre_tech": s["mitre"][1],
                 "description": s["description"],
                 "threshold": s["pattern"].get("threshold", 1),
                 "window_s": s["pattern"].get("window", 60)} for s in IDS_SIGNATURES]

    def stats(self, db: Session) -> dict:
        since24 = datetime.utcnow() - timedelta(hours=24)
        ids_alerts = db.query(Alert).filter(
            Alert.title.like("%[IDS SID:%"),
            Alert.created_at >= since24,
        ).count()
        return {
            "total_signatures": len(IDS_SIGNATURES),
            "ids_alerts_24h": ids_alerts,
        }


ids_engine = IdsEngine()
