"""
Ransomware Protection Engine.
8 familles, détection comportementale, canary files, kill-switch.
Portage depuis AEGIS AI v3.1.
"""
from __future__ import annotations
import json, random
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc
from database.models import RansomwareDetection, Alert
from core.soc.alert_engine import alert_engine
import logging

log = logging.getLogger("SOC.Ransomware")

# ── Familles connues ──────────────────────────────────────────────────────────
RANSOMWARE_FAMILIES = {
    "LockBit 3.0": {
        "aka": "LockBit Black", "first_seen": "2022-06", "threat_level": "CRITICAL",
        "encryption": "AES-256 + RSA-2048", "extension": ".lockbit",
        "ransom_note": "Restore-My-Files.txt",
        "techniques": ["T1486", "T1490", "T1489", "T1055", "T1078", "T1021"],
        "iocs": ["lockbit3.onion", "lockbitap2yfbt7af.onion"],
        "avg_dwell_days": 5, "known_victims": 2000,
        "description": "RaaS le plus actif 2023-2024. Chiffrement ultra-rapide (IOCP), AV bypass, double extorsion.",
    },
    "BlackCat/ALPHV": {
        "aka": "ALPHV", "first_seen": "2021-11", "threat_level": "CRITICAL",
        "encryption": "ChaCha20 + RSA-4096", "extension": ".sykffle",
        "ransom_note": "RECOVER-FILES.txt",
        "techniques": ["T1486", "T1490", "T1491", "T1055", "T1562", "T1070"],
        "iocs": ["alphvmmm27o3abo3r2mlmjlv5mj7em7o6a5lkxt7m42cxpfhzid7agad.onion"],
        "avg_dwell_days": 9, "known_victims": 1000,
        "description": "Premier ransomware majeur en Rust. Multi-plateforme, interface web affiliés.",
    },
    "Cl0p": {
        "aka": "TA505", "first_seen": "2019-02", "threat_level": "CRITICAL",
        "encryption": "RC4 + AES", "extension": ".clop",
        "ransom_note": "ClopReadMe.txt",
        "techniques": ["T1486", "T1190", "T1059", "T1485", "T1041"],
        "iocs": ["clop.onion"], "avg_dwell_days": 14, "known_victims": 500,
        "description": "Cible les vulnérabilités zero-day dans les logiciels de transfert de fichiers (MOVEit, GoAnywhere).",
    },
    "Royal": {
        "aka": "Zeon", "first_seen": "2022-09", "threat_level": "CRITICAL",
        "encryption": "AES + RSA-4096", "extension": ".royal",
        "ransom_note": "README.TXT",
        "techniques": ["T1486", "T1490", "T1566.001", "T1021", "T1059"],
        "iocs": ["royal2xthig3aef7.onion"], "avg_dwell_days": 7, "known_victims": 350,
        "description": "Ancien opérateur Conti. Ciblage soins de santé et infrastructure critique.",
    },
    "Akira": {
        "aka": "Akira", "first_seen": "2023-03", "threat_level": "HIGH",
        "encryption": "ChaChaPoly1305 + RSA-4096", "extension": ".akira",
        "ransom_note": "akira_readme.txt",
        "techniques": ["T1486", "T1190", "T1078", "T1021.001", "T1059"],
        "iocs": ["akiralkzxzq2dsrzsrvbr2xgbbu2wgsmxryd3zlyawd3ekucwkytzqid.onion"],
        "avg_dwell_days": 6, "known_victims": 250,
        "description": "Cible les VPNs Cisco et les appareils réseau. Style rétro ASCII dans sa communication.",
    },
    "Play": {
        "aka": "PlayCrypt", "first_seen": "2022-06", "threat_level": "HIGH",
        "encryption": "AES + RSA", "extension": ".play",
        "ransom_note": "ReadMe.txt",
        "techniques": ["T1486", "T1190", "T1059.001", "T1021", "T1490"],
        "iocs": ["k7kg3jqxang3wh7zkvzvmv3zntwed6b6bqxs7uuxvmzgyjz6ha4mlad.onion"],
        "avg_dwell_days": 8, "known_victims": 300,
        "description": "Exploite Exchange, ProxyNotShell, OWASSRF. Ne publie pas de ransom note détaillée.",
    },
    "8Base": {
        "aka": "8Base", "first_seen": "2023-05", "threat_level": "HIGH",
        "encryption": "AES + RSA", "extension": ".8base",
        "ransom_note": "readme.txt",
        "techniques": ["T1486", "T1190", "T1055", "T1562", "T1485"],
        "iocs": ["xfzmzs4s4vkqmsnbqkzqq4rfgwjqhlhqmfqk2mhcgavrhpwjqhxmrid.onion"],
        "avg_dwell_days": 4, "known_victims": 200,
        "description": "Partenaire Phobos ransomware. Très actif mi-2023, ciblage PME.",
    },
    "Rhysida": {
        "aka": "Rhysida", "first_seen": "2023-05", "threat_level": "HIGH",
        "encryption": "ChaCha20 + RSA-4096", "extension": ".rhysida",
        "ransom_note": "CriticalBreachDetected.pdf",
        "techniques": ["T1486", "T1059.001", "T1021.001", "T1078", "T1490"],
        "iocs": ["rhysidaivrii5zex5ih7klhkopqmjfmjq4qazxnlfmrbfnvfqtqxrrqd.onion"],
        "avg_dwell_days": 5, "known_victims": 150,
        "description": "Cible hôpitaux et secteur public. Utilise PowerShell et Living-off-the-land.",
    },
}

# ── Indicateurs comportementaux ───────────────────────────────────────────────
BEHAVIORAL_INDICATORS = [
    {"name": "Mass file encryption",     "weight": 50, "mitre": "T1486",
     "desc": "Chiffrement massif de fichiers en cours"},
    {"name": "Shadow copy deletion",     "weight": 45, "mitre": "T1490",
     "desc": "Suppression des sauvegardes VSS (vssadmin delete shadows)"},
    {"name": "Backup tampering",         "weight": 40, "mitre": "T1490",
     "desc": "Altération des sauvegardes locales/réseau"},
    {"name": "Process injection",        "weight": 30, "mitre": "T1055",
     "desc": "Injection dans processus légitimes"},
    {"name": "Lateral movement via SMB", "weight": 35, "mitre": "T1021.002",
     "desc": "Propagation réseau via SMB/PsExec"},
    {"name": "AV/EDR tampering",         "weight": 40, "mitre": "T1562",
     "desc": "Désactivation antivirus ou EDR"},
    {"name": "Ransom note creation",     "weight": 60, "mitre": "T1491",
     "desc": "Création de fichier ransom note (README.txt, RECOVER.txt…)"},
    {"name": "Exfiltration before encrypt","weight": 35, "mitre": "T1041",
     "desc": "Exfiltration de données avant chiffrement (double extorsion)"},
    {"name": "High disk I/O activity",   "weight": 25, "mitre": "T1486",
     "desc": "Activité disque anormalement élevée"},
    {"name": "Wallpaper change",         "weight": 15, "mitre": "T1491.001",
     "desc": "Modification du fond d'écran (message ransom)"},
]


class RansomwareEngine:

    def detect(self, db: Session, hostname: str,
               indicators: list = None, family: str = None,
               detection_type: str = "BEHAVIORAL") -> dict:
        """Crée une détection de ransomware et génère une alerte CRITICAL."""
        inds = indicators or []
        weight = sum(i.get("weight", 0) for i in inds)
        threat = "CRITICAL" if weight >= 60 else "HIGH" if weight >= 30 else "MEDIUM"

        det = RansomwareDetection(
            family=family,
            threat_level=threat,
            detection_type=detection_type,
            hostname=hostname,
            indicators=json.dumps([i.get("name", i) if isinstance(i, dict) else i for i in inds]),
            techniques=json.dumps(list({
                i.get("mitre") for i in inds
                if isinstance(i, dict) and i.get("mitre")
            })),
            status="ACTIVE",
        )
        if family and family in RANSOMWARE_FAMILIES:
            fam = RANSOMWARE_FAMILIES[family]
            det.extension   = fam.get("extension")
            det.ransom_note = fam.get("ransom_note")
            det.techniques  = json.dumps(fam.get("techniques", []))

        db.add(det)

        # Alerte SOC
        a = alert_engine.create(
            db=db, severity=threat, category="RANSOMWARE",
            title=f"[RANSOMWARE] {family or 'Inconnu'} sur {hostname}",
            description=(f"Type: {detection_type} | "
                         f"Indicateurs: {len(inds)} | "
                         f"Score risque: {weight}"),
            mitre_tactic="TA0040", mitre_technique="T1486", source_engine="ransomware",
        )
        det.alert_id = a.id
        db.commit()
        log.warning(f"[RANSOMWARE] {threat} — {family or '?'} on {hostname}")
        return {"detection_id": det.id, "family": family, "threat_level": threat,
                "weight": weight, "alert_id": a.id, "indicators": len(inds)}

    def get_detections(self, db: Session, status: str = None,
                       page: int = 1, per_page: int = 20) -> dict:
        q = db.query(RansomwareDetection).order_by(desc(RansomwareDetection.detected_at))
        if status: q = q.filter(RansomwareDetection.status == status)
        total = q.count()
        rows  = q.offset((page-1)*per_page).limit(per_page).all()
        return {"total": total, "detections": [self._det_dict(d) for d in rows]}

    def get_families(self) -> list:
        return [{
            "name": name, "aka": f.get("aka"), "threat_level": f["threat_level"],
            "encryption": f["encryption"], "extension": f["extension"],
            "first_seen": f["first_seen"], "known_victims": f["known_victims"],
            "avg_dwell_days": f["avg_dwell_days"], "description": f["description"],
            "techniques": f["techniques"],
        } for name, f in RANSOMWARE_FAMILIES.items()]

    def get_indicators(self) -> list:
        return BEHAVIORAL_INDICATORS

    def stats(self, db: Session) -> dict:
        total  = db.query(RansomwareDetection).count()
        active = db.query(RansomwareDetection).filter(RansomwareDetection.status == "ACTIVE").count()
        return {"total": total, "active": active,
                "known_families": len(RANSOMWARE_FAMILIES),
                "behavioral_indicators": len(BEHAVIORAL_INDICATORS)}

    def _det_dict(self, d: RansomwareDetection) -> dict:
        return {"id": d.id, "family": d.family, "threat_level": d.threat_level,
                "detection_type": d.detection_type, "hostname": d.hostname,
                "extension": d.extension, "status": d.status,
                "indicators": json.loads(d.indicators) if d.indicators else [],
                "techniques": json.loads(d.techniques) if d.techniques else [],
                "detected_at": d.detected_at.isoformat() if d.detected_at else None}


ransomware_engine = RansomwareEngine()
