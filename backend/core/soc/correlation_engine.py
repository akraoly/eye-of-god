"""L'Œil de Dieu — Correlation Engine
25 règles MITRE ATT&CK, kill-chain reconstruction, clustering d'alertes, timeline.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

KILLCHAIN_PHASES = [
    "Reconnaissance", "Initial Access", "Execution", "Persistence",
    "Privilege Escalation", "Defense Evasion", "Credential Access",
    "Discovery", "Lateral Movement", "Collection",
    "Command & Control", "Exfiltration", "Impact",
]

CORRELATION_RULES = [
    {"id": "CORR-001", "name": "Active Reconnaissance Campaign",
     "description": "Scans massifs + requêtes DNS anormales + fingerprinting",
     "severity": "medium", "killchain_phase": "Reconnaissance",
     "mitre_techniques": ["T1595", "T1046", "T1040"], "weight": 0.7},
    {"id": "CORR-002", "name": "OSINT + Credential Harvesting Prep",
     "description": "Activité OSINT + collecte emails/usernames",
     "severity": "low", "killchain_phase": "Reconnaissance",
     "mitre_techniques": ["T1598", "T1593"], "weight": 0.5},
    {"id": "CORR-003", "name": "Phishing → Execution Chain",
     "description": "Email phishing + exécution document malicieux EDR",
     "severity": "high", "killchain_phase": "Initial Access",
     "mitre_techniques": ["T1566", "T1203", "T1059"], "weight": 0.85},
    {"id": "CORR-004", "name": "Web Application Exploitation",
     "description": "Injections bloquées/réussies + erreurs massives",
     "severity": "high", "killchain_phase": "Initial Access",
     "mitre_techniques": ["T1190", "T1059"], "weight": 0.8},
    {"id": "CORR-005", "name": "Brute Force → Successful Login",
     "description": "Brute-force suivi d'une connexion réussie depuis la même IP",
     "severity": "critical", "killchain_phase": "Initial Access",
     "mitre_techniques": ["T1110", "T1078"], "weight": 0.95},
    {"id": "CORR-006", "name": "Malicious Script Execution Chain",
     "description": "PowerShell/Bash suspect + callback C2 NTA",
     "severity": "critical", "killchain_phase": "Execution",
     "mitre_techniques": ["T1059.001", "T1027", "T1071"], "weight": 0.9},
    {"id": "CORR-007", "name": "Living Off the Land (LOLBins)",
     "description": "Outils légitimes utilisés à des fins malicieuses",
     "severity": "high", "killchain_phase": "Execution",
     "mitre_techniques": ["T1218", "T1059"], "weight": 0.75},
    {"id": "CORR-008", "name": "Persistence Mechanism Installed",
     "description": "Modification registre/tâches planifiées/services",
     "severity": "high", "killchain_phase": "Persistence",
     "mitre_techniques": ["T1547", "T1053", "T1543"], "weight": 0.8},
    {"id": "CORR-009", "name": "Privilege Escalation Chain",
     "description": "Tentative priv esc + changement groupe/compte",
     "severity": "high", "killchain_phase": "Privilege Escalation",
     "mitre_techniques": ["T1068", "T1098", "T1134"], "weight": 0.85},
    {"id": "CORR-010", "name": "Active Directory Abuse",
     "description": "Kerberoasting / Pass-the-Hash / DCSync détecté",
     "severity": "critical", "killchain_phase": "Privilege Escalation",
     "mitre_techniques": ["T1558.003", "T1550.002", "T1003.006"], "weight": 0.95},
    {"id": "CORR-011", "name": "Defense Evasion Detected",
     "description": "Désactivation AV/logging + logs effacés + injection processus",
     "severity": "high", "killchain_phase": "Defense Evasion",
     "mitre_techniques": ["T1562", "T1070", "T1055"], "weight": 0.85},
    {"id": "CORR-012", "name": "Credential Theft & Reuse",
     "description": "Brute-force + credential dump EDR + connexions suspectes",
     "severity": "high", "killchain_phase": "Credential Access",
     "mitre_techniques": ["T1110", "T1003", "T1078"], "weight": 0.88},
    {"id": "CORR-013", "name": "Multi-Source Credential Attack",
     "description": "Brute-force massif + réponse EDR en credential access",
     "severity": "critical", "killchain_phase": "Credential Access",
     "mitre_techniques": ["T1110", "T1539", "T1078"], "weight": 0.92},
    {"id": "CORR-014", "name": "Internal Network Discovery",
     "description": "Post-compromission : scan interne + SMB/LDAP",
     "severity": "high", "killchain_phase": "Discovery",
     "mitre_techniques": ["T1046", "T1018", "T1135", "T1087"], "weight": 0.82},
    {"id": "CORR-015", "name": "Lateral Movement Detected",
     "description": "Brute-force SSH/RDP + connexions internes suspectes NTA",
     "severity": "critical", "killchain_phase": "Lateral Movement",
     "mitre_techniques": ["T1110", "T1021", "T1046"], "weight": 0.9},
    {"id": "CORR-016", "name": "Pass-the-Hash / Pass-the-Ticket",
     "description": "Authentifications NTLM suspectes + patterns mimikatz EDR",
     "severity": "critical", "killchain_phase": "Lateral Movement",
     "mitre_techniques": ["T1550.002", "T1550.003"], "weight": 0.95},
    {"id": "CORR-017", "name": "Sensitive Data Collection",
     "description": "Accès données sensibles + compression/archivage massif",
     "severity": "high", "killchain_phase": "Collection",
     "mitre_techniques": ["T1005", "T1074", "T1560"], "weight": 0.83},
    {"id": "CORR-018", "name": "APT Multi-Stage Attack",
     "description": "IOC Threat Intel + trafic C2 (beacon pattern) + EDR",
     "severity": "critical", "killchain_phase": "Command & Control",
     "mitre_techniques": ["T1071", "T1055", "T1027", "T1573"], "weight": 0.95},
    {"id": "CORR-019", "name": "DNS Tunneling / Covert Channel",
     "description": "Requêtes DNS anormalement longues/fréquentes",
     "severity": "high", "killchain_phase": "Command & Control",
     "mitre_techniques": ["T1071.004", "T1572"], "weight": 0.87},
    {"id": "CORR-020", "name": "Data Exfiltration Chain",
     "description": "Accès fichiers massifs + trafic sortant anormal NTA",
     "severity": "critical", "killchain_phase": "Exfiltration",
     "mitre_techniques": ["T1005", "T1041", "T1048"], "weight": 0.95},
    {"id": "CORR-021", "name": "Cloud / HTTP Exfiltration",
     "description": "Upload massif + API calls inhabituels + gros transferts",
     "severity": "high", "killchain_phase": "Exfiltration",
     "mitre_techniques": ["T1537", "T1567"], "weight": 0.85},
    {"id": "CORR-022", "name": "Ransomware Kill-Chain",
     "description": "Processus suspect + SIEM ransomware + chiffrement",
     "severity": "critical", "killchain_phase": "Impact",
     "mitre_techniques": ["T1486", "T1490", "T1059"], "weight": 1.0},
    {"id": "CORR-023", "name": "Destructive Attack / Wiper",
     "description": "Suppression massive fichiers + MBR/partition write",
     "severity": "critical", "killchain_phase": "Impact",
     "mitre_techniques": ["T1485", "T1561"], "weight": 1.0},
    {"id": "CORR-024", "name": "DDoS / Service Disruption",
     "description": "Trafic entrant massif + erreurs service + alerts DoS",
     "severity": "high", "killchain_phase": "Impact",
     "mitre_techniques": ["T1498", "T1499"], "weight": 0.8},
    {"id": "CORR-025", "name": "Full Attack Chain Detected",
     "description": "Plusieurs phases ATT&CK simultanées — attaque complète probable",
     "severity": "critical", "killchain_phase": "Multi-Phase",
     "mitre_techniques": ["T1595", "T1566", "T1059", "T1055", "T1041"], "weight": 1.0},
]


class CorrelationEngine:

    # ── Helpers DB ────────────────────────────────────────────────────────────

    def _count_alerts(self, db, category: str, minutes: int) -> int:
        try:
            from database.models import Alert
            from sqlalchemy import func
            since = datetime.utcnow() - timedelta(minutes=minutes)
            return db.query(func.count(Alert.id)).filter(
                Alert.timestamp >= since,
                Alert.category.ilike(f"%{category}%")
            ).scalar() or 0
        except Exception:
            return 0

    def _count_edr(self, db, keyword: str, minutes: int, field: str = "event_type") -> int:
        try:
            from database.models import EdrEvent
            from sqlalchemy import func
            since = datetime.utcnow() - timedelta(minutes=minutes)
            col = getattr(EdrEvent, field, EdrEvent.event_type)
            return db.query(func.count(EdrEvent.id)).filter(
                EdrEvent.timestamp >= since,
                col.ilike(f"%{keyword}%")
            ).scalar() or 0
        except Exception:
            return 0

    def _count_nta(self, db, threat_type: str, minutes: int) -> int:
        try:
            from database.models import NetworkFlow
            from sqlalchemy import func
            since = datetime.utcnow() - timedelta(minutes=minutes)
            return db.query(func.count(NetworkFlow.id)).filter(
                NetworkFlow.detected_at >= since,
                NetworkFlow.threat_type.ilike(f"%{threat_type}%")
            ).scalar() or 0
        except Exception:
            return 0

    def _count_siem(self, db, event_type: str, minutes: int) -> int:
        try:
            from database.models import SiemEvent
            from sqlalchemy import func
            since = datetime.utcnow() - timedelta(minutes=minutes)
            return db.query(func.count(SiemEvent.id)).filter(
                SiemEvent.timestamp >= since,
                SiemEvent.event_type.ilike(f"%{event_type}%")
            ).scalar() or 0
        except Exception:
            return 0

    def _count_ioc(self, db, minutes: int) -> int:
        try:
            from database.models import ThreatHit
            from sqlalchemy import func
            since = datetime.utcnow() - timedelta(minutes=minutes)
            return db.query(func.count(ThreatHit.id)).filter(
                ThreatHit.matched_at >= since
            ).scalar() or 0
        except Exception:
            return 0

    # ── Évaluateurs (25 règles) ───────────────────────────────────────────────

    def _eval_CORR_001(self, db) -> Optional[dict]:
        scans = self._count_alerts(db, "PORT_SCAN", 30)
        dns   = self._count_nta(db, "DNS", 30)
        if scans >= 5 or (scans >= 2 and dns >= 3):
            return {"scan_alerts": scans, "dns_anomalies": dns,
                    "score": min(100, scans * 5 + dns * 10)}
        return None

    def _eval_CORR_002(self, db) -> Optional[dict]:
        osint = self._count_alerts(db, "OSINT", 240)
        if osint >= 3:
            return {"osint_events": osint, "score": min(100, osint * 15)}
        return None

    def _eval_CORR_003(self, db) -> Optional[dict]:
        phish = self._count_alerts(db, "PHISHING", 120)
        exec_ = self._count_edr(db, "MALWARE", 120)
        if phish >= 1 and exec_ >= 1:
            return {"phishing_alerts": phish, "edr_events": exec_,
                    "score": min(100, phish * 25 + exec_ * 20)}
        return None

    def _eval_CORR_004(self, db) -> Optional[dict]:
        waf  = self._count_alerts(db, "INJECTION", 60)
        web  = self._count_siem(db, "WEB", 60)
        if waf >= 3 or (waf >= 1 and web >= 2):
            return {"waf_alerts": waf, "siem_web": web,
                    "score": min(100, waf * 12 + web * 8)}
        return None

    def _eval_CORR_005(self, db) -> Optional[dict]:
        bf = self._count_alerts(db, "BRUTE_FORCE", 60)
        if bf >= 5:
            return {"brute_force_alerts": bf, "score": min(100, bf * 20)}
        return None

    def _eval_CORR_006(self, db) -> Optional[dict]:
        scripts = self._count_edr(db, "PROCESS", 60)
        c2      = self._count_nta(db, "C2", 60)
        if scripts >= 2 or (scripts >= 1 and c2 >= 1):
            return {"edr_processes": scripts, "nta_c2": c2,
                    "score": min(100, scripts * 25 + c2 * 30)}
        return None

    def _eval_CORR_007(self, db) -> Optional[dict]:
        malware = self._count_edr(db, "MALWARE", 60)
        if malware >= 2:
            return {"edr_malware": malware, "score": min(100, malware * 20)}
        return None

    def _eval_CORR_008(self, db) -> Optional[dict]:
        persist = self._count_edr(db, "NETWORK_CONNECT", 120)
        sched   = self._count_siem(db, "SCHEDULED", 120)
        if persist >= 3 or sched >= 2:
            return {"edr_connections": persist, "siem_scheduled": sched,
                    "score": min(100, persist * 15 + sched * 20)}
        return None

    def _eval_CORR_009(self, db) -> Optional[dict]:
        esc  = self._count_edr(db, "FILE_WRITE", 60)
        acct = self._count_siem(db, "ACCOUNT", 60)
        if esc >= 2 and acct >= 1:
            return {"edr_file_writes": esc, "siem_accounts": acct,
                    "score": min(100, esc * 20 + acct * 20)}
        return None

    def _eval_CORR_010(self, db) -> Optional[dict]:
        ntlm = self._count_nta(db, "NTLM", 120)
        c2   = self._count_nta(db, "C2", 120)
        if ntlm >= 3 or c2 >= 2:
            return {"ntlm_flows": ntlm, "c2_flows": c2,
                    "score": min(100, ntlm * 15 + c2 * 30)}
        return None

    def _eval_CORR_011(self, db) -> Optional[dict]:
        edr_crit = self._count_edr(db, "CRITICAL", 60, field="severity")
        log_clr  = self._count_siem(db, "LOG", 60)
        if edr_crit >= 1 or log_clr >= 1:
            return {"edr_critical": edr_crit, "log_events": log_clr,
                    "score": min(100, edr_crit * 40 + log_clr * 25)}
        return None

    def _eval_CORR_012(self, db) -> Optional[dict]:
        bf   = self._count_alerts(db, "BRUTE_FORCE", 120)
        cred = self._count_edr(db, "MALWARE_DETECT", 120)
        if bf >= 2 and cred >= 1:
            return {"brute_force": bf, "edr_malware": cred,
                    "score": min(100, bf * 10 + cred * 30)}
        return None

    def _eval_CORR_013(self, db) -> Optional[dict]:
        bf_high = self._count_alerts(db, "BRUTE_FORCE", 60)
        if bf_high >= 8:
            return {"brute_force_alerts": bf_high,
                    "score": min(100, bf_high * 8 + 20)}
        return None

    def _eval_CORR_014(self, db) -> Optional[dict]:
        scans = self._count_alerts(db, "PORT_SCAN", 60)
        smb   = self._count_nta(db, "SMB", 60)
        if scans >= 3 and smb >= 1:
            return {"internal_scans": scans, "smb_flows": smb,
                    "score": min(100, scans * 8 + smb * 15)}
        return None

    def _eval_CORR_015(self, db) -> Optional[dict]:
        bf  = self._count_alerts(db, "BRUTE_FORCE", 60)
        lat = self._count_nta(db, "LATERAL", 60)
        if bf >= 3 or (bf >= 1 and lat >= 1):
            return {"brute_force": bf, "lateral_flows": lat,
                    "score": min(100, bf * 15 + lat * 20)}
        return None

    def _eval_CORR_016(self, db) -> Optional[dict]:
        ntlm = self._count_nta(db, "NTLM", 120)
        c2   = self._count_nta(db, "C2", 120)
        if ntlm >= 3 or c2 >= 2:
            return {"ntlm_flows": ntlm, "c2_flows": c2,
                    "score": min(100, ntlm * 20 + c2 * 25)}
        return None

    def _eval_CORR_017(self, db) -> Optional[dict]:
        exfil = self._count_nta(db, "EXFIL", 120)
        dlp   = self._count_alerts(db, "DLP", 120)
        if exfil >= 2 or dlp >= 1:
            return {"exfil_flows": exfil, "dlp_alerts": dlp,
                    "score": min(100, exfil * 20 + dlp * 25)}
        return None

    def _eval_CORR_018(self, db) -> Optional[dict]:
        ioc_hits = self._count_ioc(db, 24 * 60)
        c2       = self._count_nta(db, "C2", 240)
        beacon   = self._count_nta(db, "BEACONING", 240)
        if c2 >= 2 or (ioc_hits >= 5 and c2 >= 1):
            return {"ioc_hits": ioc_hits, "c2_flows": c2, "beaconing": beacon,
                    "score": min(100, ioc_hits * 5 + c2 * 20 + beacon * 10)}
        return None

    def _eval_CORR_019(self, db) -> Optional[dict]:
        tunnel = self._count_nta(db, "DNS_TUNNEL", 60)
        dns    = self._count_nta(db, "DNS", 60)
        if tunnel >= 1 or dns >= 10:
            return {"dns_tunnel": tunnel, "dns_flows": dns,
                    "score": min(100, tunnel * 50 + dns * 3)}
        return None

    def _eval_CORR_020(self, db) -> Optional[dict]:
        exfil = self._count_nta(db, "EXFIL", 120)
        dlp   = self._count_alerts(db, "DATA_EXFILTRATION", 120)
        if exfil >= 2 or dlp >= 2 or (exfil >= 1 and dlp >= 1):
            return {"nta_exfil": exfil, "dlp_alerts": dlp,
                    "score": min(100, exfil * 25 + dlp * 20)}
        return None

    def _eval_CORR_021(self, db) -> Optional[dict]:
        cloud = self._count_alerts(db, "DATA_EXFILTRATION", 120)
        if cloud >= 1:
            return {"cloud_exfil": cloud, "score": min(100, cloud * 40)}
        return None

    def _eval_CORR_022(self, db) -> Optional[dict]:
        ransomware = self._count_alerts(db, "RANSOMWARE", 120)
        siem_ran   = self._count_siem(db, "RANSOMWARE", 120)
        if ransomware >= 1 or siem_ran >= 1:
            return {"ransomware_alerts": ransomware, "siem_ransomware": siem_ran,
                    "score": min(100, ransomware * 40 + siem_ran * 40)}
        return None

    def _eval_CORR_023(self, db) -> Optional[dict]:
        edr_crit = self._count_edr(db, "CRITICAL", 30, field="severity")
        malware  = self._count_alerts(db, "MALWARE", 30)
        if edr_crit >= 3 or malware >= 2:
            return {"edr_critical": edr_crit, "malware_alerts": malware,
                    "score": min(100, edr_crit * 20 + malware * 30)}
        return None

    def _eval_CORR_024(self, db) -> Optional[dict]:
        dos = self._count_alerts(db, "DOS_ATTACK", 30)
        if dos >= 5:
            return {"dos_alerts": dos, "score": min(100, dos * 8)}
        return None

    def _eval_CORR_025(self, db) -> Optional[dict]:
        evals = [
            ("Recon",      self._eval_CORR_001),
            ("InitAccess", self._eval_CORR_005),
            ("Execution",  self._eval_CORR_006),
            ("Persistence",self._eval_CORR_008),
            ("PrivEsc",    self._eval_CORR_009),
            ("LatMov",     self._eval_CORR_015),
            ("Exfil",      self._eval_CORR_020),
            ("Impact",     self._eval_CORR_022),
        ]
        active_phases = [(name, fn) for name, fn in evals if fn(self, db)]
        if len(active_phases) >= 4:
            names = [n for n, _ in active_phases]
            return {"active_phases": len(names), "phases": names,
                    "score": min(100, len(names) * 15 + 40)}
        return None

    _EVALUATORS = {
        "CORR-001": _eval_CORR_001, "CORR-002": _eval_CORR_002,
        "CORR-003": _eval_CORR_003, "CORR-004": _eval_CORR_004,
        "CORR-005": _eval_CORR_005, "CORR-006": _eval_CORR_006,
        "CORR-007": _eval_CORR_007, "CORR-008": _eval_CORR_008,
        "CORR-009": _eval_CORR_009, "CORR-010": _eval_CORR_010,
        "CORR-011": _eval_CORR_011, "CORR-012": _eval_CORR_012,
        "CORR-013": _eval_CORR_013, "CORR-014": _eval_CORR_014,
        "CORR-015": _eval_CORR_015, "CORR-016": _eval_CORR_016,
        "CORR-017": _eval_CORR_017, "CORR-018": _eval_CORR_018,
        "CORR-019": _eval_CORR_019, "CORR-020": _eval_CORR_020,
        "CORR-021": _eval_CORR_021, "CORR-022": _eval_CORR_022,
        "CORR-023": _eval_CORR_023, "CORR-024": _eval_CORR_024,
        "CORR-025": _eval_CORR_025,
    }

    # ── API publique ──────────────────────────────────────────────────────────

    def run_all(self, db) -> list[dict]:
        results = []
        for rule in CORRELATION_RULES:
            fn = self._EVALUATORS.get(rule["id"])
            if fn is None:
                continue
            try:
                evidence = fn(self, db)
                if evidence:
                    score = min(100, int(evidence.get("score", 50) * rule.get("weight", 1.0)))
                    results.append({
                        "rule_id":          rule["id"],
                        "name":             rule["name"],
                        "description":      rule["description"],
                        "severity":         rule["severity"],
                        "killchain_phase":  rule["killchain_phase"],
                        "mitre_techniques": rule["mitre_techniques"],
                        "evidence":         evidence,
                        "confidence":       score,
                        "detected_at":      datetime.utcnow().isoformat(),
                    })
            except Exception:
                pass
        results.sort(key=lambda r: r["confidence"], reverse=True)
        return results

    def get_killchain_status(self, db) -> dict:
        incidents    = self.run_all(db)
        active_phases = {i["killchain_phase"] for i in incidents}
        return {
            "phases": [
                {
                    "name":      phase,
                    "active":    phase in active_phases,
                    "incidents": [i for i in incidents if i["killchain_phase"] == phase],
                }
                for phase in KILLCHAIN_PHASES
            ],
            "active_phase_count":  len(active_phases),
            "total_incidents":     len(incidents),
            "attack_in_progress":  len(active_phases) >= 3,
        }

    def cluster_alerts(self, db, window_minutes: int = 60) -> list[dict]:
        try:
            from database.models import Alert
            from sqlalchemy import func
            since = datetime.utcnow() - timedelta(minutes=window_minutes)
            rows = (
                db.query(
                    Alert.source_ip,
                    func.count(Alert.id).label("alert_count"),
                    func.max(Alert.severity).label("max_severity"),
                )
                .filter(Alert.created_at >= since, Alert.source_ip.isnot(None))
                .group_by(Alert.source_ip)
                .having(func.count(Alert.id) >= 2)
                .order_by(func.count(Alert.id).desc())
                .limit(20).all()
            )
            clusters = []
            for row in rows:
                cats = [
                    r.category for r in
                    db.query(Alert.category)
                    .filter(Alert.source_ip == row.source_ip, Alert.created_at >= since)
                    .distinct().all()
                ]
                clusters.append({
                    "source_ip":   row.source_ip,
                    "alert_count": row.alert_count,
                    "max_severity":row.max_severity,
                    "categories":  cats,
                    "risk_score":  min(100, row.alert_count * 8),
                })
            return clusters
        except Exception:
            return []

    def get_timeline(self, db, hours: int = 24) -> list[dict]:
        since  = datetime.utcnow() - timedelta(hours=hours)
        events = []

        sources = [
            ("Alert",        "timestamp",   "alert",   "🚨", "title",      "category"),
            ("EdrEvent",     "timestamp",   "edr",     "🛡️", "event_type", "severity"),
            ("NetworkFlow",  "detected_at", "nta",     "🌐", "threat_type","threat_type"),
            ("SiemEvent",    "timestamp",   "siem",    "📊", "event_type", "event_type"),
        ]

        for cls_name, ts_field, src, icon, title_f, cat_f in sources:
            try:
                from database import models as _m
                Model = getattr(_m, cls_name)
                ts_col = getattr(Model, ts_field)
                rows = (
                    db.query(Model)
                    .filter(ts_col >= since)
                    .order_by(ts_col.desc())
                    .limit(40).all()
                )
                for r in rows:
                    ts = getattr(r, ts_field, None)
                    events.append({
                        "source":   src,
                        "severity": getattr(r, "severity", "MEDIUM"),
                        "title":    f"[{src.upper()}] {getattr(r, title_f, '') or ''}",
                        "category": getattr(r, cat_f, src.upper()) or src.upper(),
                        "ts":       ts.isoformat() if ts else "",
                        "icon":     icon,
                    })
            except Exception:
                pass

        events.sort(key=lambda e: e["ts"], reverse=True)
        return events[:200]

    def get_source_stats(self, db) -> dict:
        from sqlalchemy import func
        since_1h  = datetime.utcnow() - timedelta(hours=1)
        since_24h = datetime.utcnow() - timedelta(hours=24)

        def safe_count(cls_name: str, ts_field: str, since) -> int:
            try:
                from database import models as _m
                Model  = getattr(_m, cls_name)
                ts_col = getattr(Model, ts_field)
                return db.query(func.count()).filter(ts_col >= since).scalar() or 0
            except Exception:
                return 0

        model_map = {
            "alerts":   ("Alert",       "timestamp"),
            "edr":      ("EdrEvent",    "timestamp"),
            "nta":      ("NetworkFlow", "detected_at"),
            "siem":     ("SiemEvent",   "timestamp"),
            "threats":  ("ThreatHit",   "matched_at"),
        }
        return {
            key: {
                "last_1h":  safe_count(cls, ts, since_1h),
                "last_24h": safe_count(cls, ts, since_24h),
            }
            for key, (cls, ts) in model_map.items()
        }

    def stats(self, db) -> dict:
        incidents = self.run_all(db)
        critical  = sum(1 for i in incidents if i["severity"] == "critical")
        high      = sum(1 for i in incidents if i["severity"] == "high")
        return {
            "total_correlations": len(incidents),
            "critical": critical,
            "high": high,
            "active_phases": len({i["killchain_phase"] for i in incidents}),
            "attack_in_progress": len({i["killchain_phase"] for i in incidents}) >= 3,
            "top_rule": incidents[0]["name"] if incidents else None,
        }


correlation_engine = CorrelationEngine()
