"""
Zero Trust Engine — politiques d'accès, évaluation de confiance, sessions.
Portage depuis AEGIS AI v3.0.
"""
from __future__ import annotations
import json
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc
from database.models import ZeroTrustPolicy, ZeroTrustSession, ZeroTrustAccessLog
import logging

log = logging.getLogger("SOC.ZeroTrust")

# Politiques par défaut
DEFAULT_POLICIES = [
    {"name": "Deny foreign high-risk IPs", "description": "Bloquer les IPs des pays à haut risque",
     "action": "DENY", "priority": 10,
     "conditions": json.dumps({"countries": ["CN", "RU", "KP", "IR"], "reason": "High-risk origin"})},
    {"name": "MFA required for admin", "description": "MFA obligatoire pour tous les comptes admin",
     "action": "MFA_REQUIRED", "priority": 20,
     "conditions": json.dumps({"account_types": ["ADMIN"], "privilege_levels": ["SUPER_ADMIN", "PRIVILEGED"]})},
    {"name": "Block after-hours privileged access", "description": "Accès privilégiés bloqués hors horaires (22h-6h)",
     "action": "DENY", "priority": 30,
     "conditions": json.dumps({"hours_blocked": [22, 23, 0, 1, 2, 3, 4, 5], "account_types": ["ADMIN"]})},
    {"name": "Audit service accounts", "description": "Journaliser toutes les actions des comptes de service",
     "action": "AUDIT", "priority": 40,
     "conditions": json.dumps({"account_types": ["SERVICE"]})},
    {"name": "Allow VPN users", "description": "Accès autorisé depuis le VPN interne",
     "action": "ALLOW", "priority": 50,
     "conditions": json.dumps({"ip_ranges": ["10.0.0.0/8", "172.16.0.0/12"], "require_mfa": False})},
    {"name": "Default deny all", "description": "Bloquer tout accès non explicitement autorisé",
     "action": "DENY", "priority": 999,
     "conditions": json.dumps({"catch_all": True})},
]

# Facteurs de risque et leur impact sur le trust score
_RISK_FACTORS = {
    "no_mfa":          -25, "foreign_ip":      -20, "after_hours":     -15,
    "failed_logins":   -20, "dormant_account": -30, "unknown_device":  -10,
    "privileged_user": -10, "tor_exit":        -40, "known_bad_ip":    -50,
    "vpn_connected":   +20, "mfa_verified":    +30, "known_device":    +15,
    "business_hours":  +10, "low_risk_account":+10,
}


def _evaluate_trust(user: str, source_ip: str, resource: str,
                    account: dict = None, db: Session = None) -> tuple[float, list, str]:
    """Calcule le trust score (0-100) et retourne (score, risk_factors, decision)."""
    score   = 50.0  # baseline
    factors = []
    now     = datetime.utcnow()

    if account:
        if not account.get("mfa_enabled"):
            score += _RISK_FACTORS["no_mfa"]; factors.append("no_mfa")
        if account.get("is_dormant"):
            score += _RISK_FACTORS["dormant_account"]; factors.append("dormant_account")
        if account.get("account_type") == "SERVICE":
            factors.append("service_account")
        fails = account.get("failed_logins", 0)
        if fails >= 3:
            score += _RISK_FACTORS["failed_logins"]; factors.append("failed_logins")

    # Heure
    if 8 <= now.hour < 20:
        score += _RISK_FACTORS["business_hours"]; factors.append("business_hours")
    elif now.hour < 6 or now.hour >= 22:
        score += _RISK_FACTORS["after_hours"]; factors.append("after_hours")

    # IP
    if source_ip:
        first = source_ip.split(".")[0] if "." in source_ip else ""
        if first in ("10", "172", "192"):
            score += _RISK_FACTORS["vpn_connected"]; factors.append("vpn_connected")

    score = max(0.0, min(100.0, score))

    # Décision
    if score >= 70:   decision = "ALLOW"
    elif score >= 50: decision = "MFA_REQUIRED"
    elif score >= 30: decision = "AUDIT"
    else:             decision = "DENY"

    return round(score, 1), factors, decision


class ZeroTrustEngine:

    def init_policies(self, db: Session) -> int:
        existing = db.query(ZeroTrustPolicy).count()
        if existing > 0: return existing
        for p in DEFAULT_POLICIES:
            policy = ZeroTrustPolicy(**p, enabled=True)
            db.add(policy)
        db.commit()
        log.info(f"[ZT] {len(DEFAULT_POLICIES)} politiques initialisées")
        return len(DEFAULT_POLICIES)

    def evaluate(self, db: Session, user: str, source_ip: str,
                 resource: str, device_id: str = None,
                 account: dict = None) -> dict:
        """Évalue une demande d'accès et crée la session + log."""
        score, factors, decision = _evaluate_trust(user, source_ip, resource, account, db)

        # Créer session
        session = ZeroTrustSession(
            user=user, source_ip=source_ip, resource=resource,
            device_id=device_id, trust_score=score, decision=decision,
            risk_factors=json.dumps(factors), status="ACTIVE",
            expires_at=datetime.utcnow() + timedelta(hours=8),
        )
        db.add(session)

        # Journal
        log_entry = ZeroTrustAccessLog(
            user=user, source_ip=source_ip, resource=resource,
            decision=decision,
            reason=", ".join(factors[:3]) if factors else "Evaluation nominale",
            trust_score=score,
        )
        db.add(log_entry)
        db.commit()
        db.refresh(session)
        log.info(f"[ZT] {user}@{source_ip}→{resource} score={score} {decision}")

        return {"session_id": session.id, "user": user,
                "trust_score": score, "decision": decision,
                "risk_factors": factors, "resource": resource}

    def revoke_session(self, db: Session, session_id: int) -> bool:
        sess = db.query(ZeroTrustSession).filter(ZeroTrustSession.id == session_id).first()
        if not sess: return False
        sess.status = "REVOKED"
        db.commit()
        return True

    def list_sessions(self, db: Session, status: str = None,
                      page: int = 1, per_page: int = 50) -> dict:
        q = db.query(ZeroTrustSession).order_by(desc(ZeroTrustSession.created_at))
        if status: q = q.filter(ZeroTrustSession.status == status)
        total = q.count()
        rows  = q.offset((page-1)*per_page).limit(per_page).all()
        return {"total": total, "sessions": [self._sess_dict(s) for s in rows]}

    def list_policies(self, db: Session) -> list:
        self.init_policies(db)
        policies = db.query(ZeroTrustPolicy).order_by(ZeroTrustPolicy.priority).all()
        return [self._pol_dict(p) for p in policies]

    def access_logs(self, db: Session, hours: int = 24, page: int = 1, per_page: int = 50) -> dict:
        since = datetime.utcnow() - timedelta(hours=hours)
        q = db.query(ZeroTrustAccessLog).filter(ZeroTrustAccessLog.logged_at >= since).order_by(desc(ZeroTrustAccessLog.logged_at))
        total = q.count()
        rows  = q.offset((page-1)*per_page).limit(per_page).all()
        return {"total": total, "logs": [self._log_dict(l) for l in rows]}

    def stats(self, db: Session) -> dict:
        total_sessions = db.query(ZeroTrustSession).count()
        active         = db.query(ZeroTrustSession).filter(ZeroTrustSession.status == "ACTIVE").count()
        denied         = db.query(ZeroTrustSession).filter(ZeroTrustSession.decision == "DENY").count()
        total_policies = db.query(ZeroTrustPolicy).filter(ZeroTrustPolicy.enabled == True).count()
        since24        = datetime.utcnow() - timedelta(hours=24)
        logs_24h       = db.query(ZeroTrustAccessLog).filter(ZeroTrustAccessLog.logged_at >= since24).count()
        return {"total_sessions": total_sessions, "active_sessions": active,
                "denied_sessions": denied, "active_policies": total_policies, "access_logs_24h": logs_24h}

    def _pol_dict(self, p: ZeroTrustPolicy) -> dict:
        return {"id": p.id, "name": p.name, "description": p.description,
                "action": p.action, "priority": p.priority, "enabled": p.enabled,
                "conditions": json.loads(p.conditions) if p.conditions else {},
                "hit_count": p.hit_count}

    def _sess_dict(self, s: ZeroTrustSession) -> dict:
        return {"id": s.id, "user": s.user, "source_ip": s.source_ip,
                "resource": s.resource, "trust_score": s.trust_score,
                "decision": s.decision, "status": s.status,
                "risk_factors": json.loads(s.risk_factors) if s.risk_factors else [],
                "created_at": s.created_at.isoformat() if s.created_at else None}

    def _log_dict(self, l: ZeroTrustAccessLog) -> dict:
        return {"id": l.id, "user": l.user, "source_ip": l.source_ip,
                "resource": l.resource, "decision": l.decision,
                "reason": l.reason, "trust_score": l.trust_score,
                "logged_at": l.logged_at.isoformat() if l.logged_at else None}


zero_trust_engine = ZeroTrustEngine()
