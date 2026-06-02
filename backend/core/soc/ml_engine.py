"""
ML Anomaly Detection Engine — K-Means + Isolation Forest.
Portage depuis AEGIS AI v3.4, adapté à L'Œil de Dieu.
"""
from __future__ import annotations
import json, time, traceback
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import numpy as np
import joblib

from database.models import Alert, MLAnomaly, MLTrainingRun
import logging
log = logging.getLogger("SOC.ML")

# ── Config ────────────────────────────────────────────────────────────────
ML_DIR           = Path(__file__).parent.parent.parent / "data" / "ml_models"
ML_DIR.mkdir(parents=True, exist_ok=True)

KMEANS_PATH      = ML_DIR / "kmeans.joblib"
IFOREST_PATH     = ML_DIR / "iforest.joblib"
SCALER_PATH      = ML_DIR / "scaler.joblib"
META_PATH        = ML_DIR / "metadata.json"

N_CLUSTERS         = 5
CONTAMINATION      = 0.05
MIN_SAMPLES        = 20
ANOMALY_THRESHOLD  = 70.0

SEVERITY_MAP = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
CATEGORY_MAP = {
    "PORT_SCAN": 1, "BRUTE_FORCE": 2, "DOS_ATTACK": 3,
    "ANOMALY": 4,   "MALWARE": 5,    "INTRUSION": 6,
    "UNAUTHORIZED_ACCESS": 7, "DATA_EXFILTRATION": 8,
    "LATERAL_MOVEMENT": 6,  "PHISHING": 5, "RANSOMWARE": 5,
    "PRIVILEGE_ESCALATION": 6, "C2": 6, "OTHER": 9,
}
CLUSTER_NAMES = {
    0: "Scan réseau / Reconnaissance",
    1: "Brute force / Authentification",
    2: "Intrusion / Malware critique",
    3: "Activité nocturne suspecte",
    4: "Anomalie comportementale rare",
}


def _ip_class(ip: Optional[str]) -> int:
    if not ip: return 0
    try:
        p = ip.split(".")
        f, s = int(p[0]), int(p[1]) if len(p) > 1 else 0
        if f == 10:  return 1
        if f == 172 and 16 <= s <= 31: return 2
        if f == 192 and s == 168: return 3
        if f == 127: return 4
        return 5
    except Exception: return 0


def _extract_features(alerts: list) -> np.ndarray:
    rows, now = [], datetime.utcnow()
    for a in alerts:
        ts    = a.timestamp or a.created_at or now
        age_h = max(0, (now - ts).total_seconds() / 3600) if ts else 0
        rows.append([
            SEVERITY_MAP.get(a.severity, 2),
            CATEGORY_MAP.get(a.category, 9),
            (ts.hour if ts else 12) / 23.0,
            (ts.weekday() if ts else 0) / 6.0,
            _ip_class(a.source_ip) / 5.0,
            min(a.affected_port or 0, 65535) / 65535.0,
            min(age_h, 168) / 168.0,
        ])
    return np.array(rows, dtype=np.float64) if rows else np.empty((0, 7))


def _synthetic(n: int = 50) -> np.ndarray:
    """Données synthétiques pour bootstrap (< MIN_SAMPLES alertes en DB)."""
    rng = np.random.default_rng(42)
    X   = rng.uniform(0, 1, (n, 7))
    X[:, 0] = rng.integers(1, 5, n) / 4.0
    return X


def _iso_to_score(raw: float) -> float:
    clamped = max(min(raw, 0.0), -0.6)
    return round((-clamped / 0.6) * 100, 1)


def _score_sev(s: float) -> str:
    if s >= 85: return "CRITICAL"
    if s >= 70: return "HIGH"
    if s >= 50: return "MEDIUM"
    return "LOW"


class MLAnomalyEngine:

    def __init__(self):
        self._km = self._if = self._sc = None
        self._trained = False
        self._meta: dict = {}
        self._load()

    def _load(self):
        try:
            if KMEANS_PATH.exists() and IFOREST_PATH.exists() and SCALER_PATH.exists():
                self._km = joblib.load(KMEANS_PATH)
                self._if = joblib.load(IFOREST_PATH)
                self._sc = joblib.load(SCALER_PATH)
                if META_PATH.exists():
                    self._meta = json.loads(META_PATH.read_text())
                self._trained = True
                log.info("Modèles ML chargés")
        except Exception as e:
            log.warning(f"ML load error: {e}")

    def _save(self, meta: dict):
        try:
            joblib.dump(self._km, KMEANS_PATH)
            joblib.dump(self._if, IFOREST_PATH)
            joblib.dump(self._sc, SCALER_PATH)
            META_PATH.write_text(json.dumps(meta, default=str))
        except Exception as e:
            log.warning(f"ML save error: {e}")

    # ── Entraînement ──────────────────────────────────────────────────────
    def train(self, db) -> dict:
        from sklearn.cluster import KMeans
        from sklearn.ensemble import IsolationForest
        from sklearn.preprocessing import StandardScaler

        t0    = time.time()
        since = datetime.utcnow() - timedelta(days=30)
        run   = MLTrainingRun(triggered_by="manual", status="running")
        db.add(run); db.commit(); db.refresh(run)

        try:
            alerts = db.query(Alert).filter(Alert.created_at >= since).limit(5000).all()
            log.info(f"ML train: {len(alerts)} alertes")

            synthetic = len(alerts) < MIN_SAMPLES
            X_raw = _synthetic(max(MIN_SAMPLES, len(alerts))) if synthetic else _extract_features(alerts)

            sc = StandardScaler()
            X  = sc.fit_transform(X_raw)

            k  = min(N_CLUSTERS, max(2, len(X_raw) // 10))
            km = KMeans(n_clusters=k, n_init=10, random_state=42)
            km.fit(X)

            ifo = IsolationForest(contamination=CONTAMINATION, n_estimators=100, random_state=42)
            ifo.fit(X)

            self._km, self._if, self._sc = km, ifo, sc
            self._trained = True

            # Scorer les vraies alertes
            n_anomalies = 0
            if not synthetic and alerts:
                n_anomalies = self._score_and_save(db, alerts)

            dur  = time.time() - t0
            meta = {"trained_at": datetime.utcnow().isoformat(), "n_samples": len(X_raw),
                    "n_clusters": k, "contamination": CONTAMINATION}
            self._save(meta)
            self._meta = meta

            run.status = "success"; run.n_samples = len(X_raw)
            run.n_anomalies = n_anomalies; run.duration_s = dur
            db.commit()

            return {"status": "success", "n_samples": len(X_raw), "n_clusters": k,
                    "n_anomalies": n_anomalies, "duration_s": round(dur, 2),
                    "synthetic_data": synthetic}
        except Exception as e:
            run.status = "failed"; run.error_msg = str(e); db.commit()
            log.error(f"ML train error: {e}")
            return {"status": "error", "message": str(e)}

    def _score_and_save(self, db, alerts: list) -> int:
        """Score les alertes et sauvegarde les anomalies détectées."""
        X_raw = _extract_features(alerts)
        if len(X_raw) == 0: return 0
        X      = self._sc.transform(X_raw)
        raw_sc = self._if.score_samples(X)
        labels = self._km.predict(X)
        count  = 0
        for i, (alert, raw, label) in enumerate(zip(alerts, raw_sc, labels)):
            score = _iso_to_score(raw)
            if score >= ANOMALY_THRESHOLD:
                feats = X_raw[i].tolist()
                anom  = MLAnomaly(
                    entity_type="alert", entity_id=alert.id,
                    score=score, severity=_score_sev(score),
                    cluster_id=int(label),
                    cluster_name=CLUSTER_NAMES.get(int(label), f"Cluster {label}"),
                    explanation=self._explain(alert, int(label), score),
                    features=json.dumps(feats),
                )
                db.add(anom)
                count += 1
        db.commit()
        return count

    def _explain(self, alert, cluster_id: int, score: float) -> str:
        parts = []
        if alert.severity in ("HIGH", "CRITICAL"): parts.append(f"sévérité {alert.severity}")
        ts = alert.timestamp or alert.created_at
        if ts and (ts.hour >= 22 or ts.hour <= 5): parts.append("heure nocturne")
        if cluster_id in (2, 4): parts.append(f"cluster rare ({CLUSTER_NAMES.get(cluster_id, '?')})")
        if score >= 85: parts.append("très éloigné du comportement habituel")
        return ", ".join(parts) or "comportement statistiquement inhabituel"

    # ── Score en temps réel ───────────────────────────────────────────────
    def score_alert(self, alert) -> Optional[dict]:
        """Score une seule alerte — retourne None si modèle non entraîné."""
        if not self._trained: return None
        try:
            X_raw = _extract_features([alert])
            X     = self._sc.transform(X_raw)
            raw   = self._if.score_samples(X)[0]
            label = int(self._km.predict(X)[0])
            score = _iso_to_score(raw)
            return {"score": score, "severity": _score_sev(score),
                    "cluster": label, "cluster_name": CLUSTER_NAMES.get(label, f"Cluster {label}"),
                    "is_anomaly": score >= ANOMALY_THRESHOLD}
        except Exception as e:
            log.warning(f"Score error: {e}")
            return None

    # ── Requêtes ─────────────────────────────────────────────────────────
    def get_anomalies(self, db, hours: int = 24, min_score: float = 0,
                      page: int = 1, per_page: int = 50) -> dict:
        from sqlalchemy import desc
        since = datetime.utcnow() - timedelta(hours=hours)
        q = db.query(MLAnomaly).filter(
            MLAnomaly.detected_at >= since,
            MLAnomaly.score >= min_score,
        ).order_by(desc(MLAnomaly.score))
        total = q.count()
        rows  = q.offset((page-1)*per_page).limit(per_page).all()
        return {"total": total, "page": page, "per_page": per_page,
                "anomalies": [self._anom_dict(a) for a in rows]}

    def stats(self, db) -> dict:
        total     = db.query(MLAnomaly).count()
        critical  = db.query(MLAnomaly).filter(MLAnomaly.severity == "CRITICAL").count()
        high      = db.query(MLAnomaly).filter(MLAnomaly.severity == "HIGH").count()
        last_run  = db.query(MLTrainingRun).order_by(MLTrainingRun.trained_at.desc()).first()
        return {"total_anomalies": total, "critical": critical, "high": high,
                "trained": self._trained, "meta": self._meta,
                "last_run": {"status": last_run.status,
                             "trained_at": last_run.trained_at.isoformat(),
                             "n_samples": last_run.n_samples,
                             "n_anomalies": last_run.n_anomalies} if last_run else None}

    def _anom_dict(self, a: MLAnomaly) -> dict:
        return {"id": a.id, "entity_type": a.entity_type, "entity_id": a.entity_id,
                "score": a.score, "severity": a.severity,
                "cluster": a.cluster_name, "explanation": a.explanation,
                "detected_at": a.detected_at.isoformat()}


ml_engine = MLAnomalyEngine()
