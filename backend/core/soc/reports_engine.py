"""
Reports Engine — génération de rapports de sécurité.
Portage depuis AEGIS AI v3.1 — format JSON/Markdown (pas PDF, pas de dépendances lourdes).
"""
from __future__ import annotations
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
import logging

log = logging.getLogger("SOC.Reports")

REPORT_TYPES = {
    "security_overview": {
        "label": "Vue Globale de Sécurité",
        "desc":  "Alertes, incidents, top IPs, recommandations",
        "icon":  "🛡️",
    },
    "threat_intelligence": {
        "label": "Rapport Threat Intelligence",
        "desc":  "IOCs actifs, hits, acteurs APT, groupes détectés",
        "icon":  "🔎",
    },
    "compliance": {
        "label": "Rapport de Conformité",
        "desc":  "Score CIS, contrôles passés/échoués, plans de remédiation",
        "icon":  "📋",
    },
    "iam_audit": {
        "label": "Audit IAM",
        "desc":  "Comptes à risque, MFA, comptes dormants, privilèges excessifs",
        "icon":  "👤",
    },
    "incident_summary": {
        "label": "Résumé des Incidents",
        "desc":  "Incidents ouverts, résolus, timeline, MTTR",
        "icon":  "🚨",
    },
}


class ReportsEngine:

    def generate(self, db: Session, report_type: str, hours: int = 168) -> dict:
        """Génère un rapport selon le type demandé."""
        if report_type not in REPORT_TYPES:
            return {"error": f"Type inconnu. Disponibles: {list(REPORT_TYPES.keys())}"}

        fn = getattr(self, f"_gen_{report_type}", None)
        if not fn:
            return {"error": "Générateur non implémenté"}

        report = fn(db, hours)
        report.update({
            "report_type": report_type,
            "label": REPORT_TYPES[report_type]["label"],
            "generated_at": datetime.utcnow().isoformat(),
            "period_hours": hours,
        })
        log.info(f"[Reports] Rapport généré: {report_type}")
        return report

    def _gen_security_overview(self, db: Session, hours: int) -> dict:
        from database.models import Alert, Incident
        from core.soc.alert_engine import alert_engine
        from core.soc.incident_engine import incident_engine
        since = datetime.utcnow() - timedelta(hours=hours)
        a_stats = alert_engine.stats(db, hours=hours)
        i_stats = incident_engine.stats(db)
        recent_alerts = db.query(Alert).filter(Alert.created_at >= since).order_by(
            Alert.created_at.desc()).limit(5).all()
        return {
            "summary": {
                "total_alerts": a_stats["total"],
                "critical_open": a_stats["critical_open"],
                "by_severity": a_stats["by_severity"],
                "open_incidents": i_stats["open"],
                "total_incidents": i_stats["total"],
            },
            "top_source_ips": a_stats.get("top_source_ips", [])[:5],
            "recent_alerts": [{"title": a.title, "severity": a.severity,
                                "category": a.category, "source_ip": a.source_ip,
                                "ts": a.timestamp.isoformat() if a.timestamp else None}
                               for a in recent_alerts],
            "recommendations": self._security_recs(a_stats),
        }

    def _gen_threat_intelligence(self, db: Session, hours: int) -> dict:
        from database.models import ThreatIOC, ThreatHit, OsintActor
        total_iocs  = db.query(ThreatIOC).filter(ThreatIOC.active == True).count()
        critical    = db.query(ThreatIOC).filter(ThreatIOC.severity == "CRITICAL", ThreatIOC.active == True).count()
        since       = datetime.utcnow() - timedelta(hours=hours)
        hits        = db.query(ThreatHit).filter(ThreatHit.matched_at >= since).count()
        active_apt  = db.query(OsintActor).filter(OsintActor.is_active == True).count()
        top_iocs    = db.query(ThreatIOC).filter(ThreatIOC.hit_count > 0).order_by(
            ThreatIOC.hit_count.desc()).limit(5).all()
        return {
            "summary": {"total_iocs": total_iocs, "critical_iocs": critical,
                        "hits_period": hits, "active_apt_groups": active_apt},
            "top_hit_iocs": [{"type": i.ioc_type, "value": i.value,
                               "threat": i.threat_type, "hits": i.hit_count}
                              for i in top_iocs],
        }

    def _gen_compliance(self, db: Session, hours: int) -> dict:
        from core.soc.compliance_engine import compliance_engine
        stats = compliance_engine.stats(db)
        failed = db.query(__import__("database.models", fromlist=["ComplianceControl"]).ComplianceControl).filter_by(status="FAIL").all()
        return {
            "summary": stats,
            "critical_failures": [{"id": c.control_id, "title": c.title,
                                    "category": c.category, "severity": c.severity}
                                   for c in failed if c.severity == "CRITICAL"][:10],
            "recommendations": [f"Remédier au contrôle {c.control_id}: {c.title}"
                                 for c in failed[:5]],
        }

    def _gen_iam_audit(self, db: Session, hours: int) -> dict:
        from core.soc.iam_engine import iam_engine
        stats = iam_engine.stats(db)
        high_risk = db.query(__import__("database.models", fromlist=["IamAccount"]).IamAccount).filter(
            __import__("database.models", fromlist=["IamAccount"]).IamAccount.risk_score >= 70
        ).order_by(__import__("database.models", fromlist=["IamAccount"]).IamAccount.risk_score.desc()).limit(5).all()
        mfa_audit = iam_engine.mfa_audit(db)
        return {
            "summary": stats,
            "high_risk_accounts": [{"username": a.username, "risk_score": a.risk_score,
                                     "reasons": __import__("json").loads(a.risk_reasons) if a.risk_reasons else []}
                                    for a in high_risk],
            "mfa_coverage_pct": stats["mfa_coverage_pct"],
            "privileged_without_mfa": len(mfa_audit["privileged_without_mfa"]),
            "recommendations": self._iam_recs(stats),
        }

    def _gen_incident_summary(self, db: Session, hours: int) -> dict:
        from database.models import Incident
        from core.soc.incident_engine import incident_engine
        stats = incident_engine.stats(db)
        recent = db.query(Incident).order_by(Incident.opened_at.desc()).limit(10).all()
        return {
            "summary": stats,
            "recent_incidents": [{"title": i.title, "severity": i.severity,
                                   "status": i.status, "opened_at": i.opened_at.isoformat() if i.opened_at else None}
                                  for i in recent],
        }

    def _security_recs(self, stats: dict) -> list:
        recs = []
        if stats.get("critical_open", 0) > 0:
            recs.append(f"⚠️ {stats['critical_open']} alerte(s) CRITICAL non résolue(s) — traiter en priorité")
        if stats.get("by_severity", {}).get("HIGH", 0) > 5:
            recs.append("🔴 Forte activité HIGH — vérifier les règles SIEM et playbooks SOAR")
        return recs or ["✅ Aucune action urgente identifiée"]

    def _iam_recs(self, stats: dict) -> list:
        recs = []
        if stats.get("no_mfa", 0) > 0:
            recs.append(f"🔐 {stats['no_mfa']} compte(s) sans MFA — activer l'authentification forte")
        if stats.get("dormant", 0) > 0:
            recs.append(f"💤 {stats['dormant']} compte(s) dormant(s) — désactiver ou supprimer")
        if stats.get("high_risk", 0) > 0:
            recs.append(f"⚠️ {stats['high_risk']} compte(s) à haut risque — audit immédiat requis")
        return recs or ["✅ Posture IAM correcte"]

    def list_types(self) -> list:
        return [{"type": k, **v} for k, v in REPORT_TYPES.items()]


reports_engine = ReportsEngine()
