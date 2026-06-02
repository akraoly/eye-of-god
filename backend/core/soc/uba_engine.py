"""L'Œil de Dieu — User Behavior Analytics (UBA) Engine
7 anomalies comportementales détectées :
  ODD_HOUR_LOGIN       — connexion entre 22h–6h
  HIGH_VELOCITY        — >50 actions en 5 min (même IP)
  NEW_IP               — IP jamais vue pour cet utilisateur
  REPEATED_FAILURES    — >5 échecs consécutifs
  BULK_DATA_ACCESS     — >30 reads en 10 min
  AFTER_HOURS_ADMIN    — action sensible entre 20h–7h
  LATERAL_MOVEMENT     — même IP sur >3 catégories d'alertes distinctes

Sources : UBAEventLog (events injectés via API) + Alert (patterns réseau comme proxy).
"""
import asyncio
import uuid as _uuid
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import func, desc

# ── Seuils ────────────────────────────────────────────────────────────────────

VELOCITY_WINDOW_MIN = 5
VELOCITY_THRESHOLD  = 50
BULK_WINDOW_MIN     = 10
BULK_THRESHOLD      = 30
FAILURE_THRESHOLD   = 5
ODD_HOUR_START      = 22
ODD_HOUR_END        = 6
MAX_KNOWN_IPS       = 20
LATERAL_CATEGORIES  = 3   # nombre de catégories distinctes pour LATERAL_MOVEMENT

SENSITIVE_ACTIONS = {"DELETE", "ADMIN", "EXPORT", "DOWNLOAD", "BULK", "CONFIG", "USERS", "ROLES"}


class UBAEngine:

    def __init__(self):
        self._running   = False
        self._task: Optional[asyncio.Task] = None
        self._last_run: Optional[datetime] = None

    # ── Analyse principale ────────────────────────────────────────────────────

    async def analyze(self) -> dict:
        from database.db import SessionLocal
        db    = SessionLocal()
        since = datetime.utcnow() - timedelta(hours=24)
        created = 0

        try:
            # Source 1 : UBAEventLog (events manuels ou injectés)
            from database.models import UBAEventLog
            logs = (db.query(UBAEventLog)
                    .filter(UBAEventLog.timestamp >= since)
                    .order_by(UBAEventLog.timestamp).all())

            by_user: dict[str, list] = defaultdict(list)
            for log in logs:
                uid = log.user_id or log.username or "anonymous"
                by_user[uid].append(log)

            for uid, user_logs in by_user.items():
                username = user_logs[-1].username or uid
                created += await self._analyze_user(db, uid, username, user_logs)

            # Source 2 : Alertes réseau — inférer comportement depuis source_ip
            created += await self._analyze_alert_patterns(db, since)

        except Exception as e:
            db.close()
            return {"anomalies": 0, "error": str(e)}

        db.close()
        self._last_run = datetime.utcnow()
        return {"anomalies": created, "users_analyzed": len(by_user)}

    # ── Analyse par utilisateur (UBAEventLog) ─────────────────────────────────

    async def _analyze_user(self, db: Session, user_id: str, username: str, logs: list) -> int:
        created = 0
        now     = datetime.utcnow()

        # 1. ODD_HOUR_LOGIN
        for log in logs:
            if log.action and "LOGIN" in log.action.upper() and log.success:
                h = log.timestamp.hour
                if h >= ODD_HOUR_START or h < ODD_HOUR_END:
                    if not self._anomaly_exists(db, user_id, "ODD_HOUR_LOGIN", now - timedelta(hours=12)):
                        await self._create_anomaly(db,
                            user_id=user_id, username=username, atype="ODD_HOUR_LOGIN",
                            severity="MEDIUM", score=45.0,
                            desc=f"{username} connecté à {log.timestamp.strftime('%H:%M')} (heure inhabituelle).",
                            details={"hour": h, "ip": log.ip_address},
                            source_ip=log.ip_address,
                        )
                        created += 1
                        break

        # 2. HIGH_VELOCITY
        window_start = now - timedelta(minutes=VELOCITY_WINDOW_MIN)
        recent = [l for l in logs if l.timestamp >= window_start]
        if len(recent) >= VELOCITY_THRESHOLD:
            if not self._anomaly_exists(db, user_id, "HIGH_VELOCITY", now - timedelta(minutes=30)):
                await self._create_anomaly(db,
                    user_id=user_id, username=username, atype="HIGH_VELOCITY",
                    severity="HIGH", score=70.0,
                    desc=f"{username} : {len(recent)} actions en {VELOCITY_WINDOW_MIN} min.",
                    details={"count": len(recent), "window_min": VELOCITY_WINDOW_MIN},
                    source_ip=recent[-1].ip_address if recent else None,
                )
                created += 1

        # 3. NEW_IP
        profile   = self._get_profile(db, user_id)
        known_ips = set(profile.get("known_ips") or [])
        for log in logs:
            if log.ip_address and log.success and log.ip_address not in known_ips:
                if not self._anomaly_exists(db, user_id, "NEW_IP", now - timedelta(hours=6)):
                    await self._create_anomaly(db,
                        user_id=user_id, username=username, atype="NEW_IP",
                        severity="MEDIUM", score=40.0,
                        desc=f"{username} connecté depuis nouvelle IP : {log.ip_address}.",
                        details={"new_ip": log.ip_address, "known_ips": list(known_ips)[:5]},
                        source_ip=log.ip_address,
                    )
                    created += 1
                break

        # 4. REPEATED_FAILURES
        failures = [l for l in logs if not l.success]
        if len(failures) >= FAILURE_THRESHOLD:
            if not self._anomaly_exists(db, user_id, "REPEATED_FAILURES", now - timedelta(hours=2)):
                await self._create_anomaly(db,
                    user_id=user_id, username=username, atype="REPEATED_FAILURES",
                    severity="HIGH", score=75.0,
                    desc=f"{username} : {len(failures)} échecs d'authentification en 24h.",
                    details={"failure_count": len(failures),
                             "last_ip": failures[-1].ip_address if failures else None},
                    source_ip=failures[-1].ip_address if failures else None,
                )
                created += 1

        # 5. BULK_DATA_ACCESS
        bulk_window = now - timedelta(minutes=BULK_WINDOW_MIN)
        bulk_reads  = [l for l in logs if l.timestamp >= bulk_window and (l.method or "") == "GET"]
        if len(bulk_reads) >= BULK_THRESHOLD:
            if not self._anomaly_exists(db, user_id, "BULK_DATA_ACCESS", now - timedelta(minutes=30)):
                await self._create_anomaly(db,
                    user_id=user_id, username=username, atype="BULK_DATA_ACCESS",
                    severity="HIGH", score=65.0,
                    desc=f"{username} : {len(bulk_reads)} lectures en {BULK_WINDOW_MIN} min.",
                    details={"count": len(bulk_reads), "window_min": BULK_WINDOW_MIN},
                    source_ip=bulk_reads[-1].ip_address if bulk_reads else None,
                )
                created += 1

        # 6. AFTER_HOURS_ADMIN
        for log in logs:
            if log.action and any(s in log.action.upper() for s in SENSITIVE_ACTIONS):
                h = log.timestamp.hour
                if h >= 20 or h < 7:
                    if not self._anomaly_exists(db, user_id, "AFTER_HOURS_ADMIN", log.timestamp - timedelta(hours=1)):
                        await self._create_anomaly(db,
                            user_id=user_id, username=username, atype="AFTER_HOURS_ADMIN",
                            severity="HIGH", score=60.0,
                            desc=f"{username} : action '{log.action}' à {log.timestamp.strftime('%H:%M')} (hors heures).",
                            details={"action": log.action, "hour": h, "resource": log.resource},
                            source_ip=log.ip_address,
                        )
                        created += 1
                        break

        self._update_profile(db, user_id, username, logs)
        return created

    # ── Analyse patterns alertes (source_ip comme proxy utilisateur) ──────────

    async def _analyze_alert_patterns(self, db: Session, since: datetime) -> int:
        created = 0
        try:
            from database.models import Alert

            # LATERAL_MOVEMENT : même IP source sur ≥ LATERAL_CATEGORIES catégories
            rows = (
                db.query(Alert.source_ip,
                         func.count(func.distinct(Alert.category)).label("cat_cnt"),
                         func.count(Alert.id).label("total"))
                .filter(Alert.timestamp >= since, Alert.source_ip.isnot(None))
                .group_by(Alert.source_ip)
                .having(func.count(func.distinct(Alert.category)) >= LATERAL_CATEGORIES)
                .limit(20).all()
            )
            for ip, cat_cnt, total in rows:
                uid = f"ip:{ip}"
                if not self._anomaly_exists(db, uid, "LATERAL_MOVEMENT", since):
                    cats = [r.category for r in
                            db.query(Alert.category).filter(
                                Alert.source_ip == ip, Alert.timestamp >= since
                            ).distinct().all()]
                    await self._create_anomaly(db,
                        user_id=uid, username=ip, atype="LATERAL_MOVEMENT",
                        severity="HIGH", score=min(100.0, cat_cnt * 15 + total * 2),
                        desc=f"IP {ip} détectée sur {cat_cnt} catégories d'alertes distinctes.",
                        details={"categories": cats, "total_alerts": total},
                        source_ip=ip,
                    )
                    created += 1

            # HIGH_VELOCITY réseau : >30 alertes depuis même IP en 5 min
            recent = datetime.utcnow() - timedelta(minutes=VELOCITY_WINDOW_MIN)
            vel_rows = (
                db.query(Alert.source_ip, func.count(Alert.id).label("cnt"))
                .filter(Alert.timestamp >= recent, Alert.source_ip.isnot(None))
                .group_by(Alert.source_ip)
                .having(func.count(Alert.id) >= VELOCITY_THRESHOLD)
                .limit(10).all()
            )
            for ip, cnt in vel_rows:
                uid = f"ip:{ip}"
                if not self._anomaly_exists(db, uid, "HIGH_VELOCITY", recent):
                    await self._create_anomaly(db,
                        user_id=uid, username=ip, atype="HIGH_VELOCITY",
                        severity="HIGH", score=min(100.0, cnt * 1.5),
                        desc=f"IP {ip} : {cnt} alertes en {VELOCITY_WINDOW_MIN} min.",
                        details={"alert_count": cnt},
                        source_ip=ip,
                    )
                    created += 1

        except Exception:
            pass
        return created

    # ── Helpers DB ────────────────────────────────────────────────────────────

    def _anomaly_exists(self, db: Session, user_id: str, atype: str, since: datetime) -> bool:
        try:
            from database.models import UBAAnomaly
            return db.query(UBAAnomaly).filter(
                UBAAnomaly.user_id      == user_id,
                UBAAnomaly.anomaly_type == atype,
                UBAAnomaly.detected_at  >= since,
                UBAAnomaly.status       != "FALSE_POSITIVE",
            ).first() is not None
        except Exception:
            return False

    async def _create_anomaly(self, db: Session, user_id: str, username: str,
                               atype: str, severity: str, score: float,
                               desc: str, details: dict, source_ip: str = None):
        try:
            from database.models import UBAAnomaly
            a = UBAAnomaly(
                anomaly_uuid = str(_uuid.uuid4()),
                user_id      = user_id,
                username     = username,
                anomaly_type = atype,
                severity     = severity,
                score        = score,
                description  = desc,
                details      = details,
                source_ip    = source_ip,
            )
            db.add(a)
            db.commit()

            if severity in ("HIGH", "CRITICAL"):
                self._create_alert(db, a)
        except Exception:
            pass

    def _create_alert(self, db: Session, anomaly):
        try:
            from database.models import Alert
            db.add(Alert(
                alert_uuid  = str(_uuid.uuid4()),
                severity    = anomaly.severity,
                category    = "UNAUTHORIZED_ACCESS",
                title       = f"[UBA] {anomaly.anomaly_type.replace('_', ' ')} — {anomaly.username}",
                description = anomaly.description,
                source_ip   = anomaly.source_ip,
                status      = "NEW",
                source_engine = "uba",
            ))
            db.commit()
        except Exception:
            pass

    def _get_profile(self, db: Session, user_id: str) -> dict:
        try:
            from database.models import UBAProfile
            p = db.query(UBAProfile).filter(UBAProfile.user_id == user_id).first()
            if p:
                return {"known_ips": p.known_ips or [], "usual_hours": p.usual_hours or {},
                        "risk_score": p.risk_score}
        except Exception:
            pass
        return {"known_ips": [], "usual_hours": {}, "risk_score": 0.0}

    def _update_profile(self, db: Session, user_id: str, username: str, logs: list):
        try:
            from database.models import UBAProfile, UBAAnomaly
            p    = db.query(UBAProfile).filter(UBAProfile.user_id == user_id).first()
            ips  = {l.ip_address for l in logs if l.ip_address}
            if p:
                merged = list(set(p.known_ips or []) | ips)[-MAX_KNOWN_IPS:]
            else:
                merged = list(ips)[:MAX_KNOWN_IPS]

            hours: dict[str, int] = {}
            for l in logs:
                h = str(l.timestamp.hour)
                hours[h] = hours.get(h, 0) + 1

            anom_count = db.query(func.count(UBAAnomaly.id)).filter(
                UBAAnomaly.user_id == user_id,
                UBAAnomaly.status  != "FALSE_POSITIVE",
            ).scalar() or 0

            failures   = sum(1 for l in logs if not l.success)
            risk_score = min(100.0, anom_count * 15 + failures * 2)
            last_log   = logs[-1] if logs else None

            if p:
                p.username      = username
                p.known_ips     = merged
                p.usual_hours   = hours
                p.total_events  = (p.total_events or 0) + len(logs)
                p.failed_logins = (p.failed_logins or 0) + failures
                p.last_seen     = last_log.timestamp if last_log else p.last_seen
                p.last_ip       = last_log.ip_address if last_log else p.last_ip
                p.anomaly_count = anom_count
                p.risk_score    = risk_score
                p.is_high_risk  = risk_score >= 50
            else:
                db.add(UBAProfile(
                    user_id       = user_id,
                    username      = username,
                    risk_score    = risk_score,
                    total_events  = len(logs),
                    failed_logins = failures,
                    known_ips     = merged,
                    usual_hours   = hours,
                    last_seen     = last_log.timestamp if last_log else None,
                    last_ip       = last_log.ip_address if last_log else None,
                    anomaly_count = anom_count,
                    is_high_risk  = risk_score >= 50,
                ))
            db.commit()
        except Exception:
            pass

    # ── Scan automatique ──────────────────────────────────────────────────────

    async def _scan_loop(self):
        while self._running:
            await self.analyze()
            await asyncio.sleep(600)

    async def start(self):
        self._running = True
        self._task    = asyncio.create_task(self._scan_loop())

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    # ── API helpers ───────────────────────────────────────────────────────────

    def list_anomalies(self, db: Session, status: str = None, severity: str = None,
                        atype: str = None, page: int = 1, per_page: int = 50) -> dict:
        from database.models import UBAAnomaly
        q = db.query(UBAAnomaly)
        if status:
            q = q.filter(UBAAnomaly.status == status)
        if severity:
            q = q.filter(UBAAnomaly.severity == severity)
        if atype:
            q = q.filter(UBAAnomaly.anomaly_type == atype)
        total = q.count()
        items = q.order_by(desc(UBAAnomaly.detected_at)).offset((page-1)*per_page).limit(per_page).all()
        return {"total": total, "page": page, "per_page": per_page,
                "anomalies": [_anomaly_to_dict(a) for a in items]}

    def update_anomaly(self, db: Session, anomaly_id: int, status: str) -> Optional[dict]:
        from database.models import UBAAnomaly
        a = db.query(UBAAnomaly).filter(UBAAnomaly.id == anomaly_id).first()
        if not a:
            return None
        a.status = status
        db.commit()
        return _anomaly_to_dict(a)

    def list_profiles(self, db: Session, risk_min: float = 0,
                       page: int = 1, per_page: int = 50) -> dict:
        from database.models import UBAProfile
        q     = db.query(UBAProfile).filter(UBAProfile.risk_score >= risk_min)
        total = q.count()
        items = q.order_by(desc(UBAProfile.risk_score)).offset((page-1)*per_page).limit(per_page).all()
        return {"total": total, "page": page, "per_page": per_page,
                "profiles": [_profile_to_dict(p) for p in items]}

    def stats(self, db: Session) -> dict:
        from database.models import UBAAnomaly, UBAProfile
        open_anomalies  = db.query(func.count(UBAAnomaly.id)).filter(UBAAnomaly.status == "OPEN").scalar() or 0
        high_risk_users = db.query(func.count(UBAProfile.id)).filter(UBAProfile.is_high_risk == True).scalar() or 0
        confirmed       = db.query(func.count(UBAAnomaly.id)).filter(UBAAnomaly.status == "CONFIRMED").scalar() or 0
        by_type = (db.query(UBAAnomaly.anomaly_type, func.count(UBAAnomaly.id).label("cnt"))
                   .group_by(UBAAnomaly.anomaly_type)
                   .order_by(func.count(UBAAnomaly.id).desc()).all())
        return {
            "open_anomalies":  open_anomalies,
            "high_risk_users": high_risk_users,
            "confirmed":       confirmed,
            "by_type":         {t: c for t, c in by_type},
            "running":         self._running,
            "last_run":        self._last_run.isoformat() if self._last_run else None,
        }

    def log_event(self, db: Session, username: str, action: str, success: bool = True,
                   ip_address: str = None, resource: str = None,
                   method: str = None, user_id: str = None, details: dict = None) -> dict:
        from database.models import UBAEventLog
        ev = UBAEventLog(
            username   = username,
            user_id    = user_id or username,
            action     = action.upper(),
            resource   = resource,
            method     = method,
            ip_address = ip_address,
            success    = success,
            details    = details,
        )
        db.add(ev)
        db.commit()
        return {"id": ev.id, "username": username, "action": ev.action,
                "success": success, "timestamp": ev.timestamp.isoformat()}


def _anomaly_to_dict(a) -> dict:
    return {
        "id": a.id, "anomaly_uuid": a.anomaly_uuid,
        "user_id": a.user_id, "username": a.username,
        "anomaly_type": a.anomaly_type, "severity": a.severity,
        "score": a.score, "description": a.description,
        "details": a.details, "source_ip": a.source_ip,
        "status": a.status, "alert_created": a.alert_created,
        "detected_at": a.detected_at.isoformat() if a.detected_at else None,
    }


def _profile_to_dict(p) -> dict:
    return {
        "id": p.id, "user_id": p.user_id, "username": p.username,
        "risk_score": p.risk_score, "total_events": p.total_events,
        "failed_logins": p.failed_logins, "anomaly_count": p.anomaly_count,
        "is_high_risk": p.is_high_risk, "known_ips": p.known_ips,
        "usual_hours": p.usual_hours, "last_ip": p.last_ip,
        "last_seen": p.last_seen.isoformat() if p.last_seen else None,
    }


uba_engine = UBAEngine()
