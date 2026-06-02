"""
DLP Engine — Data Loss Prevention.
Détecte fuites PII, secrets, credentials, données sensibles.
Portage depuis AEGIS AI v3.1.
"""
from __future__ import annotations
import re, json, hashlib
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc
from database.models import DlpIncident, Alert
from core.soc.alert_engine import alert_engine
import logging

log = logging.getLogger("SOC.DLP")

# ── Patterns de détection ─────────────────────────────────────────────────────
DLP_PATTERNS = {
    "CREDIT_CARD": {
        "regex":    r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|6(?:011|5[0-9]{2})[0-9]{12})\b",
        "label":    "Numéro de carte bancaire",
        "severity": "CRITICAL", "mitre": "T1530",
    },
    "IBAN": {
        "regex":    r"\b[A-Z]{2}[0-9]{2}[A-Z0-9]{4}[0-9]{7}(?:[A-Z0-9]{0,16})\b",
        "label":    "Numéro IBAN",
        "severity": "CRITICAL", "mitre": "T1530",
    },
    "SSN": {
        "regex":    r"\b(?!000|666|9\d{2})\d{3}-(?!00)\d{2}-(?!0000)\d{4}\b",
        "label":    "SSN (Numéro sécurité sociale US)",
        "severity": "CRITICAL", "mitre": "T1213",
    },
    "AWS_KEY": {
        "regex":    r"\b(?:AKIA|AIPA|ASIA|ABIA|ACCA)[A-Z0-9]{16}\b",
        "label":    "Clé d'accès AWS",
        "severity": "CRITICAL", "mitre": "T1552.001",
    },
    "GITHUB_TOKEN": {
        "regex":    r"\bghp_[A-Za-z0-9]{36}\b|\bgho_[A-Za-z0-9]{36}\b",
        "label":    "Token GitHub",
        "severity": "CRITICAL", "mitre": "T1552.001",
    },
    "PRIVATE_KEY": {
        "regex":    r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
        "label":    "Clé privée RSA/PEM",
        "severity": "CRITICAL", "mitre": "T1552.004",
    },
    "API_KEY_GENERIC": {
        "regex":    r"\b(?:api[_-]?key|apikey|api[_-]?secret|access[_-]?token)\s*[=:]\s*['\"]?[A-Za-z0-9/+]{20,}['\"]?",
        "label":    "Clé API générique",
        "severity": "HIGH",   "mitre": "T1552.001",
    },
    "PASSWORD_PLAINTEXT": {
        "regex":    r"\b(?:password|passwd|mot_de_passe|mdp)\s*[=:]\s*['\"]?[^\s'\"]{6,}['\"]?",
        "label":    "Mot de passe en clair",
        "severity": "HIGH",   "mitre": "T1552",
    },
    "EMAIL_BULK": {
        "regex":    r"\b[A-Za-z0-9._%+-]{1,64}@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
        "label":    "Adresse email (bulk)",
        "severity": "MEDIUM", "mitre": "T1114",
        "min_count": 10,      # Déclenche seulement si 10+ emails
    },
    "PHONE_FR": {
        "regex":    r"\b0[1-9](?:[0-9]{8})\b|\+33\s?[1-9](?:\s?[0-9]{2}){4}",
        "label":    "Numéro de téléphone français",
        "severity": "MEDIUM", "mitre": "T1589",
    },
    "MEDICAL_FR": {
        "regex":    r"\b[12][0-9]{2}(?:0[1-9]|1[0-2])[0-9]{5}[0-9]{3}\b",
        "label":    "Numéro de sécurité sociale français",
        "severity": "CRITICAL", "mitre": "T1213",
    },
    "ANTHROPIC_KEY": {
        "regex":    r"\bsk-ant-[A-Za-z0-9\-_]{80,}\b",
        "label":    "Clé API Anthropic",
        "severity": "CRITICAL", "mitre": "T1552.001",
    },
    "OPENAI_KEY": {
        "regex":    r"\bsk-[A-Za-z0-9]{48}\b",
        "label":    "Clé API OpenAI",
        "severity": "CRITICAL", "mitre": "T1552.001",
    },
}

CHANNELS = ["EMAIL", "HTTP_UPLOAD", "FTP", "USB", "GIT_COMMIT", "API_CALL",
            "FILE_SHARE", "PRINT", "CLOUD_SYNC", "CLIPBOARD", "MANUAL"]

_compiled = {name: re.compile(p["regex"], re.IGNORECASE) for name, p in DLP_PATTERNS.items()}


def _mask(text: str, pattern_name: str) -> str:
    """Masque partiellement la donnée sensible pour l'affichage."""
    m = _compiled[pattern_name].search(text)
    if not m:
        return "[MASQUÉ]"
    found = m.group(0)
    if len(found) <= 4:
        return "*" * len(found)
    visible = max(2, len(found) // 5)
    return found[:visible] + "*" * (len(found) - visible * 2) + found[-visible:]


class DlpEngine:

    def scan_text(self, db: Session, text: str, source: str = "manual",
                  channel: str = "MANUAL", create_alert: bool = True) -> dict:
        """Scanne un texte et retourne tous les patterns détectés."""
        findings = []
        for name, pdef in DLP_PATTERNS.items():
            matches = _compiled[name].findall(text)
            min_count = pdef.get("min_count", 1)
            if len(matches) < min_count:
                continue
            if not matches:
                continue
            snippet = _mask(text, name)
            inc = DlpIncident(
                policy_name=name,
                severity=pdef["severity"],
                channel=channel,
                source=source,
                data_type=pdef["label"],
                match_count=len(matches),
                snippet=snippet,
                mitre_tech=pdef["mitre"],
            )
            db.add(inc)

            if create_alert:
                a = alert_engine.create(
                    db=db,
                    severity=pdef["severity"],
                    category="DATA_EXFILTRATION",
                    title=f"[DLP] {pdef['label']} détecté",
                    description=f"Canal: {channel} | Source: {source} | Matches: {len(matches)}",
                    mitre_tactic="TA0010",
                    mitre_technique=pdef["mitre"],
                    source_engine="dlp",
                )
                inc.alert_id = a.id

            findings.append({
                "policy": name, "label": pdef["label"],
                "severity": pdef["severity"], "count": len(matches),
                "snippet": snippet, "mitre": pdef["mitre"],
            })
            log.info(f"[DLP] {name} ({len(matches)} matches) — {source}")

        db.commit()
        return {"source": source, "channel": channel,
                "findings": findings, "total": len(findings),
                "has_critical": any(f["severity"] == "CRITICAL" for f in findings)}

    def get_incidents(self, db: Session, status: str = None, policy: str = None,
                      hours: int = 168, page: int = 1, per_page: int = 50) -> dict:
        since = datetime.utcnow() - timedelta(hours=hours)
        q = db.query(DlpIncident).filter(DlpIncident.detected_at >= since).order_by(desc(DlpIncident.detected_at))
        if status: q = q.filter(DlpIncident.status == status)
        if policy: q = q.filter(DlpIncident.policy_name == policy)
        total = q.count()
        rows  = q.offset((page-1)*per_page).limit(per_page).all()
        return {"total": total, "incidents": [self._inc_dict(i) for i in rows]}

    def stats(self, db: Session) -> dict:
        total    = db.query(DlpIncident).count()
        critical = db.query(DlpIncident).filter(DlpIncident.severity == "CRITICAL").count()
        open_    = db.query(DlpIncident).filter(DlpIncident.status == "OPEN").count()
        return {"total": total, "critical": critical, "open": open_,
                "policies": list(DLP_PATTERNS.keys()), "channels": CHANNELS}

    def list_policies(self) -> list:
        return [{"name": n, "label": d["label"], "severity": d["severity"],
                 "mitre": d["mitre"]} for n, d in DLP_PATTERNS.items()]

    def _inc_dict(self, i: DlpIncident) -> dict:
        return {"id": i.id, "policy": i.policy_name, "severity": i.severity,
                "channel": i.channel, "source": i.source, "data_type": i.data_type,
                "match_count": i.match_count, "snippet": i.snippet,
                "status": i.status, "mitre": i.mitre_tech, "alert_id": i.alert_id,
                "detected_at": i.detected_at.isoformat() if i.detected_at else None}


dlp_engine = DlpEngine()
