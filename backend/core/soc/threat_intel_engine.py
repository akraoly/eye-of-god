"""
Threat Intelligence Engine — IOC database, matching, sources externes.
Portage depuis AEGIS AI v3.0.
"""
from __future__ import annotations
import hashlib
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from database.models import ThreatIOC, ThreatHit, Alert
import logging

log = logging.getLogger("SOC.ThreatIntel")

# ── IOCs curatés (connus malveillants + exemples demo) ────────────────────
DEFAULT_IOCS = [
    {"ioc_type":"IP",       "value":"192.168.99.99",  "threat_type":"BOTNET",     "confidence":90, "severity":"HIGH",     "source":"AEGIS Internal", "description":"IP test SOC"},
    {"ioc_type":"IP",       "value":"45.33.32.156",   "threat_type":"SCANNER",    "confidence":85, "severity":"MEDIUM",   "source":"Shodan",         "description":"Shodan scanner"},
    {"ioc_type":"IP",       "value":"198.20.69.74",   "threat_type":"SCANNER",    "confidence":85, "severity":"MEDIUM",   "source":"Shodan",         "description":"Shodan scanner"},
    {"ioc_type":"IP",       "value":"185.220.101.1",  "threat_type":"TOR_EXIT",   "confidence":95, "severity":"HIGH",     "source":"TorProject",     "description":"TOR exit node"},
    {"ioc_type":"IP",       "value":"194.165.16.11",  "threat_type":"C2",         "confidence":88, "severity":"CRITICAL", "source":"VirusTotal",     "description":"Botnet C2 server"},
    {"ioc_type":"DOMAIN",   "value":"malware-c2.ru",  "threat_type":"C2",         "confidence":95, "severity":"CRITICAL", "source":"VirusTotal",     "description":"C2 server APT"},
    {"ioc_type":"DOMAIN",   "value":"phish-bank.xyz", "threat_type":"PHISHING",   "confidence":92, "severity":"CRITICAL", "source":"PhishTank",      "description":"Phishing banque"},
    {"ioc_type":"DOMAIN",   "value":"evil-dl.ru",     "threat_type":"MALWARE",    "confidence":90, "severity":"CRITICAL", "source":"URLhaus",        "description":"Malware distribution"},
    {"ioc_type":"DOMAIN",   "value":"dga-ransomware.xyz","threat_type":"RANSOMWARE","confidence":88,"severity":"CRITICAL", "source":"AnyRun",        "description":"Ransomware DGA domain"},
    {"ioc_type":"URL",      "value":"http://evil-dl.ru/payload.exe","threat_type":"MALWARE","confidence":97,"severity":"CRITICAL","source":"URLhaus","description":"Malware dropper"},
    {"ioc_type":"HASH_MD5", "value":"d41d8cd98f00b204e9800998ecf8427e","threat_type":"MALWARE","confidence":80,"severity":"HIGH","source":"MalwareBazaar","description":"Trojan dropper"},
    {"ioc_type":"HASH_SHA256","value":"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855","threat_type":"RANSOMWARE","confidence":88,"severity":"CRITICAL","source":"MalwareBazaar","description":"Ransomware payload"},
    {"ioc_type":"CVE",      "value":"CVE-2024-1234",  "threat_type":"EXPLOIT",    "confidence":85, "severity":"HIGH",     "source":"NVD",            "description":"Critical RCE"},
    {"ioc_type":"CVE",      "value":"CVE-2023-44487",  "threat_type":"EXPLOIT",   "confidence":95, "severity":"CRITICAL", "source":"NVD",            "description":"HTTP/2 Rapid Reset"},
    {"ioc_type":"CVE",      "value":"CVE-2024-3400",  "threat_type":"EXPLOIT",    "confidence":98, "severity":"CRITICAL", "source":"NVD",            "description":"PAN-OS RCE 0-day"},
    {"ioc_type":"EMAIL",    "value":"phisher@evil.ru", "threat_type":"PHISHING",  "confidence":78, "severity":"HIGH",     "source":"PhishTank",      "description":"Email phishing"},
    {"ioc_type":"EMAIL",    "value":"ceo-spoof@company-secure.xyz","threat_type":"BEC","confidence":82,"severity":"HIGH","source":"Manual",         "description":"Business Email Compromise"},
]


class ThreatIntelEngine:

    def init_iocs(self, db: Session) -> int:
        """Charge les IOCs par défaut si la table est vide."""
        existing = db.query(ThreatIOC).count()
        if existing > 0:
            return existing
        for ioc_def in DEFAULT_IOCS:
            ioc = ThreatIOC(**ioc_def)
            db.add(ioc)
        db.commit()
        log.info(f"[TI] {len(DEFAULT_IOCS)} IOCs initialisés")
        return len(DEFAULT_IOCS)

    def add_ioc(self, db: Session, ioc_type: str, value: str,
                threat_type: str = None, severity: str = "MEDIUM",
                confidence: int = 70, source: str = "manual",
                description: str = None) -> ThreatIOC:
        existing = db.query(ThreatIOC).filter(
            ThreatIOC.ioc_type == ioc_type.upper(),
            ThreatIOC.value == value,
        ).first()
        if existing:
            existing.confidence  = max(existing.confidence, confidence)
            existing.last_seen   = datetime.utcnow()
            existing.hit_count  += 1
            db.commit()
            return existing
        ioc = ThreatIOC(
            ioc_type=ioc_type.upper(), value=value,
            threat_type=threat_type, severity=severity.upper(),
            confidence=confidence, source=source, description=description,
        )
        db.add(ioc); db.commit(); db.refresh(ioc)
        log.info(f"[TI] IOC ajouté: {ioc_type}={value}")
        return ioc

    def check_ip(self, db: Session, ip: str) -> Optional[dict]:
        """Vérifie si une IP est dans la base IOC."""
        ioc = db.query(ThreatIOC).filter(
            ThreatIOC.ioc_type == "IP", ThreatIOC.value == ip,
            ThreatIOC.active == True,
        ).first()
        return self._ioc_dict(ioc) if ioc else None

    def check_domain(self, db: Session, domain: str) -> Optional[dict]:
        ioc = db.query(ThreatIOC).filter(
            ThreatIOC.ioc_type == "DOMAIN", ThreatIOC.value == domain,
            ThreatIOC.active == True,
        ).first()
        return self._ioc_dict(ioc) if ioc else None

    def check_hash(self, db: Session, hash_val: str) -> Optional[dict]:
        ht = "HASH_MD5" if len(hash_val) == 32 else "HASH_SHA256"
        ioc = db.query(ThreatIOC).filter(
            ThreatIOC.ioc_type == ht, ThreatIOC.value == hash_val,
            ThreatIOC.active == True,
        ).first()
        return self._ioc_dict(ioc) if ioc else None

    def match_alert(self, db: Session, alert: Alert) -> list:
        """Recherche des IOCs correspondant à une alerte."""
        hits = []
        if alert.source_ip:
            ioc = self.check_ip(db, alert.source_ip)
            if ioc:
                hits.append(ioc)
                self._record_hit(db, ioc["id"], "alert", alert.id)
        return hits

    def scan_all_alerts(self, db: Session, hours: int = 24) -> dict:
        """Scanne toutes les alertes récentes contre la base IOC."""
        since  = datetime.utcnow() - timedelta(hours=hours)
        alerts = db.query(Alert).filter(Alert.created_at >= since).all()
        total_hits, matched_alerts = 0, set()
        for alert in alerts:
            hits = self.match_alert(db, alert)
            if hits:
                matched_alerts.add(alert.id)
                total_hits += len(hits)
        return {"scanned": len(alerts), "matched": len(matched_alerts),
                "total_hits": total_hits}

    def _record_hit(self, db: Session, ioc_id: int, entity_type: str, entity_id: int):
        hit = ThreatHit(ioc_id=ioc_id, entity_type=entity_type, entity_id=entity_id)
        db.add(hit)
        ioc = db.query(ThreatIOC).filter(ThreatIOC.id == ioc_id).first()
        if ioc:
            ioc.hit_count   += 1
            ioc.last_seen    = datetime.utcnow()
        db.commit()

    def list_iocs(self, db: Session, ioc_type: str = None, threat_type: str = None,
                  page: int = 1, per_page: int = 50) -> dict:
        q = db.query(ThreatIOC).filter(ThreatIOC.active == True).order_by(desc(ThreatIOC.confidence))
        if ioc_type:    q = q.filter(ThreatIOC.ioc_type    == ioc_type.upper())
        if threat_type: q = q.filter(ThreatIOC.threat_type == threat_type.upper())
        total = q.count()
        iocs  = q.offset((page-1)*per_page).limit(per_page).all()
        return {"total": total, "iocs": [self._ioc_dict(i) for i in iocs]}

    def get_recent_hits(self, db: Session, hours: int = 24, limit: int = 20) -> list:
        since = datetime.utcnow() - timedelta(hours=hours)
        hits  = db.query(ThreatHit).filter(ThreatHit.matched_at >= since) \
                  .order_by(desc(ThreatHit.matched_at)).limit(limit).all()
        results = []
        for h in hits:
            ioc = db.query(ThreatIOC).filter(ThreatIOC.id == h.ioc_id).first()
            results.append({"ioc": self._ioc_dict(ioc) if ioc else None,
                             "entity_type": h.entity_type, "entity_id": h.entity_id,
                             "matched_at": h.matched_at.isoformat()})
        return results

    def stats(self, db: Session) -> dict:
        total_iocs = db.query(ThreatIOC).filter(ThreatIOC.active == True).count()
        by_type    = {}
        for row in db.query(ThreatIOC.ioc_type, func.count(ThreatIOC.id)).group_by(ThreatIOC.ioc_type).all():
            by_type[row[0]] = row[1]
        total_hits = db.query(ThreatHit).count()
        critical   = db.query(ThreatIOC).filter(ThreatIOC.severity == "CRITICAL", ThreatIOC.active == True).count()
        return {"total_iocs": total_iocs, "by_type": by_type,
                "total_hits": total_hits, "critical_iocs": critical}

    def _ioc_dict(self, i: ThreatIOC) -> dict:
        if not i: return {}
        return {"id": i.id, "type": i.ioc_type, "value": i.value,
                "threat_type": i.threat_type, "severity": i.severity,
                "confidence": i.confidence, "source": i.source,
                "description": i.description, "hit_count": i.hit_count,
                "last_seen": i.last_seen.isoformat() if i.last_seen else None}


threat_intel_engine = ThreatIntelEngine()
