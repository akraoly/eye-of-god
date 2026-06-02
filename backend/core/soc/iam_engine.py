"""
IAM Engine — Identity & Access Management.
Inventaire comptes, MFA audit, anomalies, risk scoring.
Portage depuis AEGIS AI v3.1.
"""
from __future__ import annotations
import json
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from database.models import IamAccount, Alert
from core.soc.alert_engine import alert_engine
import logging

log = logging.getLogger("SOC.IAM")

# ── Comptes seed par défaut ────────────────────────────────────────────────────
SEED_ACCOUNTS = [
    {"username":"admin.system","display_name":"Admin Système","email":"admin@company.local",
     "department":"IT","job_title":"Administrateur Système","account_type":"ADMIN",
     "is_privileged":True,"is_admin":True,"privilege_level":"SUPER_ADMIN",
     "groups":["Domain Admins","IT Ops"],"mfa_enabled":True,"mfa_type":"TOTP",
     "password_age_days":30,"failed_logins":0,"is_locked":False,"is_dormant":False,
     "risk_score":25,"risk_reasons":["Compte super-admin"],"status":"ACTIVE"},
    {"username":"svc.backup","display_name":"Service Backup","email":None,
     "department":"IT","job_title":"Compte de service","account_type":"SERVICE",
     "is_privileged":True,"is_admin":False,"privilege_level":"PRIVILEGED",
     "groups":["Backup Operators"],"mfa_enabled":False,"mfa_type":None,
     "password_age_days":290,"failed_logins":0,"is_locked":False,"is_dormant":False,
     "risk_score":82,"risk_reasons":["Pas de MFA","Mot de passe non roté (290j)","Compte service à privilèges"],"status":"ACTIVE"},
    {"username":"user.dormant","display_name":"Ex-Employé Dupont","email":"ex@company.local",
     "department":"Finance","job_title":"Ancien comptable","account_type":"USER",
     "is_privileged":False,"is_admin":False,"privilege_level":"STANDARD",
     "groups":["Finance","VPN-Users"],"mfa_enabled":False,"mfa_type":None,
     "password_age_days":450,"failed_logins":2,"is_locked":False,"is_dormant":True,
     "risk_score":91,"risk_reasons":["Compte dormant (>90j)","Pas de MFA","Mot de passe expiré","Ex-employé potentiel"],"status":"ACTIVE"},
    {"username":"dev.martin","display_name":"Alice Martin","email":"a.martin@company.local",
     "department":"R&D","job_title":"Lead Developer","account_type":"USER",
     "is_privileged":False,"is_admin":False,"privilege_level":"STANDARD",
     "groups":["Developers","GitHub-Enterprise"],"mfa_enabled":True,"mfa_type":"FIDO2",
     "password_age_days":45,"failed_logins":0,"is_locked":False,"is_dormant":False,
     "risk_score":15,"risk_reasons":[],"status":"ACTIVE"},
    {"username":"shared.printer","display_name":"Imprimante RH partagée","email":None,
     "department":"HR","job_title":"Compte partagé","account_type":"SHARED",
     "is_privileged":False,"is_admin":False,"privilege_level":"STANDARD",
     "groups":["Print-Queue"],"mfa_enabled":False,"mfa_type":None,
     "password_age_days":730,"failed_logins":0,"is_locked":False,"is_dormant":False,
     "risk_score":60,"risk_reasons":["Compte partagé","Pas de MFA","Mot de passe non roté"],"status":"ACTIVE"},
]

# Seuils de risque
_RISK_WEIGHTS = {
    "no_mfa":         30, "dormant_90d":   25, "password_old":  15,
    "privileged":     20, "shared":        20, "locked":         5,
    "failed_logins":  15, "service_account": 15,
}


def _calc_risk(account: dict) -> tuple[float, list]:
    reasons, score = [], 0
    if not account.get("mfa_enabled"):
        reasons.append("Pas de MFA"); score += _RISK_WEIGHTS["no_mfa"]
    if account.get("is_dormant"):
        reasons.append("Compte dormant (>90j)"); score += _RISK_WEIGHTS["dormant_90d"]
    age = account.get("password_age_days", 0)
    if age > 180:
        reasons.append(f"Mot de passe non roté ({age}j)"); score += _RISK_WEIGHTS["password_old"]
    if account.get("is_privileged") and not account.get("mfa_enabled"):
        reasons.append("Compte privilégié sans MFA"); score += _RISK_WEIGHTS["privileged"]
    if account.get("account_type") == "SHARED":
        reasons.append("Compte partagé"); score += _RISK_WEIGHTS["shared"]
    if account.get("account_type") == "SERVICE" and not account.get("mfa_enabled"):
        reasons.append("Compte service sans MFA"); score += _RISK_WEIGHTS["service_account"]
    fails = account.get("failed_logins", 0)
    if fails >= 5:
        reasons.append(f"{fails} tentatives échouées récentes"); score += _RISK_WEIGHTS["failed_logins"]
    return min(100.0, float(score)), reasons


class IamEngine:

    def init_accounts(self, db: Session) -> int:
        existing = db.query(IamAccount).count()
        if existing > 0: return existing
        for a in SEED_ACCOUNTS:
            risk, reasons = _calc_risk(a)
            acc = IamAccount(
                **{k: v for k, v in a.items()
                   if k not in ("groups", "risk_reasons", "risk_score", "last_login_at", "last_login_ip")},
                groups=json.dumps(a.get("groups", [])),
                risk_reasons=json.dumps(reasons),
                risk_score=risk,
                last_login_at=datetime.utcnow() - timedelta(days=30 if not a.get("is_dormant") else 120),
            )
            db.add(acc)
        db.commit()
        log.info(f"[IAM] {len(SEED_ACCOUNTS)} comptes initialisés")
        return len(SEED_ACCOUNTS)

    def create_account(self, db: Session, username: str, display_name: str = None,
                       email: str = None, department: str = None, job_title: str = None,
                       account_type: str = "USER", is_privileged: bool = False,
                       mfa_enabled: bool = False, mfa_type: str = None,
                       groups: list = None) -> dict:
        acc = IamAccount(
            username=username, display_name=display_name, email=email,
            department=department, job_title=job_title,
            account_type=account_type, is_privileged=is_privileged,
            mfa_enabled=mfa_enabled, mfa_type=mfa_type,
            groups=json.dumps(groups or []),
            privilege_level="PRIVILEGED" if is_privileged else "STANDARD",
        )
        acc.risk_score, reasons = _calc_risk({
            "mfa_enabled": mfa_enabled, "is_privileged": is_privileged,
            "account_type": account_type, "password_age_days": 0,
        })
        acc.risk_reasons = json.dumps(reasons)
        db.add(acc); db.commit(); db.refresh(acc)
        if acc.risk_score >= 70:
            alert_engine.create(db, severity="HIGH", category="UNAUTHORIZED_ACCESS",
                title=f"[IAM] Compte à risque créé : {username}",
                description=f"Risk score: {acc.risk_score} — {', '.join(reasons[:2])}",
                mitre_tactic="TA0006", mitre_technique="T1078", source_engine="iam")
        return self._acc_dict(acc)

    def list_accounts(self, db: Session, account_type: str = None,
                      risk_min: float = 0, page: int = 1, per_page: int = 50) -> dict:
        q = db.query(IamAccount).order_by(desc(IamAccount.risk_score))
        if account_type: q = q.filter(IamAccount.account_type == account_type)
        if risk_min > 0:  q = q.filter(IamAccount.risk_score >= risk_min)
        total = q.count()
        rows  = q.offset((page-1)*per_page).limit(per_page).all()
        return {"total": total, "accounts": [self._acc_dict(a) for a in rows]}

    def stats(self, db: Session) -> dict:
        total      = db.query(IamAccount).count()
        no_mfa     = db.query(IamAccount).filter(IamAccount.mfa_enabled == False).count()
        dormant    = db.query(IamAccount).filter(IamAccount.is_dormant == True).count()
        high_risk  = db.query(IamAccount).filter(IamAccount.risk_score >= 70).count()
        privileged = db.query(IamAccount).filter(IamAccount.is_privileged == True).count()
        locked     = db.query(IamAccount).filter(IamAccount.is_locked == True).count()
        by_type = {}
        for row in db.query(IamAccount.account_type, func.count(IamAccount.id)).group_by(IamAccount.account_type).all():
            by_type[row[0]] = row[1]
        return {"total": total, "no_mfa": no_mfa, "dormant": dormant,
                "high_risk": high_risk, "privileged": privileged, "locked": locked,
                "by_type": by_type,
                "mfa_coverage_pct": round((total - no_mfa) / total * 100 if total else 0)}

    def mfa_audit(self, db: Session) -> dict:
        accounts = db.query(IamAccount).all()
        by_type  = {}
        for a in accounts:
            mt = a.mfa_type or "NONE"
            by_type[mt] = by_type.get(mt, 0) + 1
        no_mfa_privs = [a for a in accounts if a.is_privileged and not a.mfa_enabled]
        return {"total_accounts": len(accounts),
                "mfa_enabled": sum(1 for a in accounts if a.mfa_enabled),
                "mfa_disabled": sum(1 for a in accounts if not a.mfa_enabled),
                "by_mfa_type": by_type,
                "privileged_without_mfa": [self._acc_dict(a) for a in no_mfa_privs]}

    def _acc_dict(self, a: IamAccount) -> dict:
        return {"id": a.id, "username": a.username, "display_name": a.display_name,
                "email": a.email, "department": a.department, "job_title": a.job_title,
                "account_type": a.account_type, "is_privileged": a.is_privileged,
                "is_admin": a.is_admin, "privilege_level": a.privilege_level,
                "groups": json.loads(a.groups) if a.groups else [],
                "mfa_enabled": a.mfa_enabled, "mfa_type": a.mfa_type,
                "password_age_days": a.password_age_days,
                "failed_logins": a.failed_logins, "is_locked": a.is_locked,
                "is_dormant": a.is_dormant, "risk_score": a.risk_score,
                "risk_reasons": json.loads(a.risk_reasons) if a.risk_reasons else [],
                "status": a.status,
                "last_login_at": a.last_login_at.isoformat() if a.last_login_at else None}


iam_engine = IamEngine()
