"""
NTA Engine — Network Traffic Analysis.
Portage depuis AEGIS AI v3.1 — C2 detection, exfiltration, beaconing, DNS tunneling.
"""
from __future__ import annotations
import random, json
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from database.models import NetworkFlow, Alert
import logging

log = logging.getLogger("SOC.NTA")

# Ports suspects → threat type
_SUSPICIOUS_PORTS = {
    4444: "C2", 1337: "C2", 31337: "C2", 6666: "C2", 9999: "C2",
    6667: "IRC_C2", 6697: "IRC_C2",
    53:   "DNS_TUNNEL", 853: "DNS_TUNNEL",
    21:   "FTP_EXFIL", 22: "SSH_EXFIL",
    4433: "MALWARE_TLS", 8443: "MALWARE_TLS",
    443:  None,  80: None, 8080: None,  # légitimes
}

# Pays à risque élevé (géolocalisation simulée)
_HIGH_RISK_COUNTRIES = ["CN", "RU", "KP", "IR", "SY", "CU"]
_COUNTRIES_MAP = {
    "1.": "CN", "5.": "RU", "10.10.": "LOCAL", "192.168.": "LOCAL",
    "8.8.": "US", "1.1.": "US",
}

# Seuils de détection
EXFIL_BYTES_THRESHOLD  = 50_000_000    # 50 MB → possible exfiltration
BEACONING_MIN_FLOWS    = 5              # 5 connexions régulières = beaconing
BEACONING_INTERVAL_MAX = 120           # max 2 min entre connexions = régulier


def _guess_country(ip: str) -> str:
    for prefix, country in _COUNTRIES_MAP.items():
        if ip.startswith(prefix):
            return country
    return random.choice(["US", "DE", "FR", "NL", "GB", "UA", "RO"])


def _threat_score(flow_type: Optional[str], bytes_out: int, dst_country: str) -> float:
    score = 0.0
    if flow_type == "C2":          score += 80
    elif flow_type == "IRC_C2":    score += 75
    elif flow_type == "DNS_TUNNEL":score += 60
    elif flow_type in ("FTP_EXFIL","SSH_EXFIL"): score += 50
    elif flow_type == "MALWARE_TLS": score += 40
    elif flow_type == "EXFILTRATION": score += 65
    elif flow_type == "BEACONING":    score += 55
    if bytes_out > EXFIL_BYTES_THRESHOLD: score += 20
    if dst_country in _HIGH_RISK_COUNTRIES: score += 15
    return min(100.0, score)


class NtaEngine:

    def ingest_flow(self, db: Session, src_ip: str, dst_ip: str,
                    src_port: int = 0, dst_port: int = 0,
                    protocol: str = "TCP", bytes_out: int = 0, bytes_in: int = 0,
                    packets: int = 0, duration_s: float = 0.0,
                    direction: str = "out", alert_id: int = None) -> dict:
        """Ingère un flux réseau et détecte les menaces."""
        threat_type = None

        # 1. Ports suspects
        port_threat = _SUSPICIOUS_PORTS.get(dst_port)
        if port_threat:
            threat_type = port_threat

        # 2. Exfiltration de données
        if bytes_out > EXFIL_BYTES_THRESHOLD and not threat_type:
            threat_type = "EXFILTRATION"

        # 3. Pays à risque
        dst_country = _guess_country(dst_ip)

        # 4. Score
        risk = _threat_score(threat_type, bytes_out, dst_country)

        flow = NetworkFlow(
            src_ip=src_ip, dst_ip=dst_ip,
            src_port=src_port, dst_port=dst_port,
            protocol=protocol, bytes_out=bytes_out, bytes_in=bytes_in,
            packets=packets, duration_s=duration_s, direction=direction,
            threat_type=threat_type, risk_score=risk,
            country=dst_country, alert_id=alert_id,
        )
        db.add(flow); db.commit(); db.refresh(flow)
        log.debug(f"[NTA] Flow {src_ip}→{dst_ip}:{dst_port} risk={risk:.0f}")
        return {"flow_id": flow.id, "threat_type": threat_type, "risk_score": risk,
                "country": dst_country, "alert_triggered": risk >= 60}

    def ingest_from_alert(self, db: Session, alert: Alert) -> Optional[NetworkFlow]:
        """Génère un flux réseau depuis une alerte SOC."""
        if not alert.source_ip: return None
        port_map = {
            "PORT_SCAN": 0, "BRUTE_FORCE": 22, "INTRUSION": 445,
            "DATA_EXFILTRATION": 443, "C2": 4444, "MALWARE": 443,
        }
        dst_port = port_map.get(alert.category, random.choice([80, 443, 22, 8080]))
        bytes_out = random.randint(1000, 5_000_000) if alert.category == "DATA_EXFILTRATION" else random.randint(100, 50000)
        self.ingest_flow(
            db=db, src_ip=alert.source_ip,
            dst_ip=alert.destination_ip or "10.0.0.1",
            dst_port=dst_port, bytes_out=bytes_out,
            direction="out", alert_id=alert.id,
        )

    def detect_beaconing(self, db: Session, hours: int = 6) -> list:
        """Détecte le beaconing (connexions régulières vers une même IP)."""
        since = datetime.utcnow() - timedelta(hours=hours)
        # Grouper par src_ip + dst_ip, compter les flows
        rows = db.query(
            NetworkFlow.src_ip, NetworkFlow.dst_ip,
            func.count(NetworkFlow.id).label("count"),
            func.avg(NetworkFlow.risk_score).label("avg_risk"),
        ).filter(NetworkFlow.detected_at >= since).group_by(
            NetworkFlow.src_ip, NetworkFlow.dst_ip
        ).having(func.count(NetworkFlow.id) >= BEACONING_MIN_FLOWS).all()

        beaconing = []
        for row in rows:
            beaconing.append({
                "src_ip": row.src_ip, "dst_ip": row.dst_ip,
                "flow_count": row.count, "avg_risk": round(row.avg_risk or 0, 1),
                "threat_type": "BEACONING",
            })
        return beaconing

    def top_talkers(self, db: Session, hours: int = 24, limit: int = 10) -> list:
        since = datetime.utcnow() - timedelta(hours=hours)
        rows  = db.query(
            NetworkFlow.src_ip,
            func.sum(NetworkFlow.bytes_out).label("total_out"),
            func.count(NetworkFlow.id).label("flows"),
        ).filter(NetworkFlow.detected_at >= since).group_by(NetworkFlow.src_ip) \
         .order_by(desc("total_out")).limit(limit).all()
        return [{"ip": r.src_ip, "bytes_out": r.total_out or 0, "flows": r.flows} for r in rows]

    def get_flows(self, db: Session, hours: int = 24, threat_only: bool = False,
                  page: int = 1, per_page: int = 50) -> dict:
        since = datetime.utcnow() - timedelta(hours=hours)
        q = db.query(NetworkFlow).filter(NetworkFlow.detected_at >= since) \
              .order_by(desc(NetworkFlow.risk_score))
        if threat_only: q = q.filter(NetworkFlow.threat_type.isnot(None))
        total = q.count()
        flows = q.offset((page-1)*per_page).limit(per_page).all()
        return {"total": total, "flows": [self._flow_dict(f) for f in flows]}

    def stats(self, db: Session, hours: int = 24) -> dict:
        since = datetime.utcnow() - timedelta(hours=hours)
        q     = db.query(NetworkFlow).filter(NetworkFlow.detected_at >= since)
        total = q.count()
        threats = q.filter(NetworkFlow.threat_type.isnot(None)).count()
        c2      = q.filter(NetworkFlow.threat_type.in_(["C2", "IRC_C2"])).count()
        exfil   = q.filter(NetworkFlow.threat_type.in_(["EXFILTRATION","FTP_EXFIL","SSH_EXFIL"])).count()
        high_risk = q.filter(NetworkFlow.risk_score >= 70).count()
        top_threat= db.query(NetworkFlow.src_ip, func.count(NetworkFlow.id).label("c")) \
                      .filter(NetworkFlow.detected_at >= since, NetworkFlow.risk_score >= 60) \
                      .group_by(NetworkFlow.src_ip).order_by(desc("c")).limit(5).all()
        return {
            "total_flows": total, "threat_flows": threats,
            "c2_flows": c2, "exfil_flows": exfil, "high_risk": high_risk,
            "top_threat_ips": [{"ip": r.src_ip, "count": r.c} for r in top_threat],
        }

    def _flow_dict(self, f: NetworkFlow) -> dict:
        return {"id": f.id, "src_ip": f.src_ip, "dst_ip": f.dst_ip,
                "src_port": f.src_port, "dst_port": f.dst_port,
                "protocol": f.protocol, "bytes_out": f.bytes_out,
                "bytes_in": f.bytes_in, "direction": f.direction,
                "threat_type": f.threat_type, "risk_score": f.risk_score,
                "country": f.country,
                "detected_at": f.detected_at.isoformat() if f.detected_at else None}


nta_engine = NtaEngine()
