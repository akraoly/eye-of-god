"""
Phishing & Email Security Engine.
Analyse SPF/DKIM/DMARC, BEC, lookalike domains, scoring.
Portage depuis AEGIS AI v3.1.
"""
from __future__ import annotations
import re, json, random
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc
from database.models import PhishingEmail, Alert
from core.soc.alert_engine import alert_engine
import logging

log = logging.getLogger("SOC.Phishing")

# ── Indicateurs et leurs scores ───────────────────────────────────────────────
INDICATORS = {
    "spf_fail":               {"score": 20, "label": "SPF : FAIL"},
    "dkim_fail":              {"score": 15, "label": "DKIM : FAIL"},
    "dmarc_fail":             {"score": 20, "label": "DMARC : FAIL"},
    "reply_to_mismatch":      {"score": 25, "label": "Reply-To ≠ expéditeur"},
    "lookalike_domain":       {"score": 35, "label": "Domaine lookalike détecté"},
    "urgency_keywords":       {"score": 15, "label": "Mots-clés d'urgence"},
    "credential_lure":        {"score": 30, "label": "Leurre de credentials"},
    "malicious_url":          {"score": 40, "label": "URL malveillante"},
    "suspicious_attachment":  {"score": 35, "label": "Pièce jointe suspecte"},
    "display_name_spoof":     {"score": 30, "label": "Usurpation du nom affiché"},
    "newly_registered":       {"score": 20, "label": "Domaine < 30 jours"},
    "free_email_provider":    {"score": 10, "label": "Email gratuit (gmail/yahoo)"},
    "executive_impersonation":{"score": 40, "label": "Usurpation dirigeant"},
    "invoice_fraud":          {"score": 35, "label": "Fraude à la facture"},
    "wire_transfer_request":  {"score": 45, "label": "Demande de virement"},
    "password_reset_lure":    {"score": 30, "label": "Faux reset de mot de passe"},
    "too_good_offer":         {"score": 15, "label": "Offre trop belle pour être vraie"},
}

_URGENCY_WORDS = re.compile(
    r"\b(urgent|immédiat|immediate|action required|compte bloqué|vérifiez|verify|"
    r"suspended|compromised|unusual activity|verify now|click here|limited time)\b",
    re.IGNORECASE
)
_CRED_LURE = re.compile(
    r"\b(mot de passe|password|login|credentials|sign in|identifiant|connexion|"
    r"compte|account|verify your|confirmer votre)\b",
    re.IGNORECASE
)
_EXEC_TITLES = re.compile(
    r"\b(CEO|CFO|COO|PDG|Directeur|Director|President|VP|CTO|CISO)\b",
    re.IGNORECASE
)
_WIRE_TRANSFER = re.compile(
    r"\b(virement|wire transfer|bank transfer|IBAN|RIB|swift|BIC|"
    r"compte bancaire|bank account|payment|paiement)\b",
    re.IGNORECASE
)
_INVOICE_FRAUD = re.compile(
    r"\b(facture|invoice|overdue|payment due|compte client|rappel de paiement)\b",
    re.IGNORECASE
)
_SUSP_EXTS = {".exe", ".bat", ".cmd", ".js", ".vbs", ".ps1", ".hta", ".iso", ".img", ".lnk"}
_FREE_PROVIDERS = {"gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "protonmail.com", "yopmail.com"}
_LOOKALIKE_PATTERNS = [
    (r"[0o]", "0/o"), (r"[1il]", "1/i/l"), (r"[vv]", "vv/w"),
    (r"-corp$|-inc$|-llc$|-ltd$", "suffixe corporatif"),
    (r"^security-", "security-préfixe"),
    (r"^paypal-|^amazon-|^microsoft-|^google-", "marque connue"),
]


def _score_email(sender: str, subject: str, body: str, headers: dict = None,
                 attachments: list = None, urls: list = None) -> dict:
    """Calcule le risk score d'un email et retourne les indicateurs déclenchés."""
    triggered = []
    score = 0
    headers = headers or {}
    subject_body = f"{subject} {body}"

    spf   = headers.get("spf",   "NONE")
    dkim  = headers.get("dkim",  "NONE")
    dmarc = headers.get("dmarc", "NONE")

    if spf   == "FAIL":  triggered.append("spf_fail");   score += INDICATORS["spf_fail"]["score"]
    if dkim  == "FAIL":  triggered.append("dkim_fail");  score += INDICATORS["dkim_fail"]["score"]
    if dmarc == "FAIL":  triggered.append("dmarc_fail"); score += INDICATORS["dmarc_fail"]["score"]

    reply_to = headers.get("reply_to", "")
    if reply_to and sender and reply_to.split("@")[-1] != sender.split("@")[-1]:
        triggered.append("reply_to_mismatch"); score += INDICATORS["reply_to_mismatch"]["score"]

    domain = sender.split("@")[-1] if "@" in sender else ""
    if domain in _FREE_PROVIDERS:
        triggered.append("free_email_provider"); score += INDICATORS["free_email_provider"]["score"]

    if _URGENCY_WORDS.search(subject_body):
        triggered.append("urgency_keywords"); score += INDICATORS["urgency_keywords"]["score"]
    if _CRED_LURE.search(subject_body):
        triggered.append("credential_lure"); score += INDICATORS["credential_lure"]["score"]
    if _EXEC_TITLES.search(sender + " " + subject):
        triggered.append("executive_impersonation"); score += INDICATORS["executive_impersonation"]["score"]
    if _WIRE_TRANSFER.search(subject_body):
        triggered.append("wire_transfer_request"); score += INDICATORS["wire_transfer_request"]["score"]
    if _INVOICE_FRAUD.search(subject_body):
        triggered.append("invoice_fraud"); score += INDICATORS["invoice_fraud"]["score"]

    if attachments:
        for att in attachments:
            ext = "." + att.rsplit(".", 1)[-1].lower() if "." in att else ""
            if ext in _SUSP_EXTS:
                triggered.append("suspicious_attachment"); score += INDICATORS["suspicious_attachment"]["score"]
                break

    score = min(100, score)
    verdict = "CLEAN"
    if score >= 70: verdict = "PHISHING"
    elif score >= 50: verdict = "SUSPICIOUS"
    elif "executive_impersonation" in triggered and "wire_transfer_request" in triggered:
        verdict = "BEC"

    return {"score": score, "verdict": verdict, "indicators": triggered}


class PhishingEngine:

    def analyze(self, db: Session, sender: str, subject: str,
                body: str = "", recipient: str = None,
                headers: dict = None, attachments: list = None,
                urls: list = None, create_alert: bool = True) -> dict:
        """Analyse un email et le sauvegarde."""
        result = _score_email(sender, subject, body, headers, attachments, urls)
        domain = sender.split("@")[-1] if "@" in sender else ""
        hdrs   = headers or {}

        email = PhishingEmail(
            sender=sender, sender_domain=domain,
            subject=subject, recipient=recipient,
            risk_score=result["score"],
            verdict=result["verdict"],
            indicators=json.dumps(result["indicators"]),
            spf=hdrs.get("spf", "NONE"), dkim=hdrs.get("dkim", "NONE"),
            dmarc=hdrs.get("dmarc", "NONE"),
            urls=json.dumps(urls or []),
            attachments=json.dumps(attachments or []),
        )
        db.add(email)

        if create_alert and result["score"] >= 50:
            sev = "CRITICAL" if result["score"] >= 70 else "HIGH"
            a = alert_engine.create(
                db=db, severity=sev, category="PHISHING",
                title=f"[PHISHING] {result['verdict']} — score {result['score']} — {subject[:60]}",
                description=f"De: {sender} | Indicateurs: {', '.join(result['indicators'][:4])}",
                mitre_tactic="TA0001", mitre_technique="T1566", source_engine="phishing",
            )
            email.alert_id = a.id

        db.commit()
        db.refresh(email)
        log.info(f"[PHISHING] {result['verdict']} ({result['score']}) — {sender}")
        return {**result, "email_id": email.id,
                "alert_id": email.alert_id,
                "indicators_detail": [
                    {"code": c, "label": INDICATORS.get(c, {}).get("label", c),
                     "score": INDICATORS.get(c, {}).get("score", 0)}
                    for c in result["indicators"]
                ]}

    def get_emails(self, db: Session, verdict: str = None,
                   page: int = 1, per_page: int = 50) -> dict:
        q = db.query(PhishingEmail).order_by(desc(PhishingEmail.analyzed_at))
        if verdict: q = q.filter(PhishingEmail.verdict == verdict)
        total = q.count()
        rows  = q.offset((page-1)*per_page).limit(per_page).all()
        return {"total": total, "emails": [self._email_dict(e) for e in rows]}

    def stats(self, db: Session) -> dict:
        total    = db.query(PhishingEmail).count()
        phishing = db.query(PhishingEmail).filter(PhishingEmail.verdict == "PHISHING").count()
        bec      = db.query(PhishingEmail).filter(PhishingEmail.verdict == "BEC").count()
        return {"total": total, "phishing": phishing, "bec": bec,
                "indicators": len(INDICATORS)}

    def list_indicators(self) -> list:
        return [{"code": k, **v} for k, v in INDICATORS.items()]

    def _email_dict(self, e: PhishingEmail) -> dict:
        return {"id": e.id, "sender": e.sender, "subject": e.subject,
                "recipient": e.recipient, "risk_score": e.risk_score,
                "verdict": e.verdict,
                "indicators": json.loads(e.indicators) if e.indicators else [],
                "spf": e.spf, "dkim": e.dkim, "dmarc": e.dmarc,
                "alert_id": e.alert_id,
                "analyzed_at": e.analyzed_at.isoformat() if e.analyzed_at else None}


phishing_engine = PhishingEngine()
