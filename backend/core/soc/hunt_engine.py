"""L'Œil de Dieu — Threat Hunting Engine
Pipeline : IOC match alertes → IOC intel → comportement réseau → events EDR → rapport IA
"""
import asyncio
import re
from datetime import datetime, timedelta
from typing import Optional

import anthropic
from sqlalchemy.orm import Session
from sqlalchemy import desc, func, or_

from database.db import SessionLocal
from app.config import settings

_SEV_WEIGHT = {"CRITICAL": 30, "HIGH": 15, "MEDIUM": 5, "LOW": 2, "INFO": 0}

_TACTIC_MAP = {
    "IOC":      ("Command and Control", "TA0011"),
    "BEHAVIOR": ("Execution",           "TA0002"),
    "NETWORK":  ("Discovery",           "TA0007"),
    "USER":     ("Credential Access",   "TA0006"),
    "CUSTOM":   ("Initial Access",      "TA0001"),
}

_HUNT_PROMPT = """Tu es L'Œil de Dieu, expert en Threat Hunting et analyse de menaces avancées (APT).
Analyse les résultats de cette campagne de chasse et génère un rapport structuré.

Données :
{data}

Réponds UNIQUEMENT avec ce JSON (rien d'autre) :
{{
  "verdict": "CONFIRMED|LIKELY|UNLIKELY|BENIGN",
  "confidence": 0-100,
  "executive_summary": "2-3 phrases résumant la situation",
  "threat_description": "Description détaillée de la menace détectée",
  "mitre_tactics": ["TA0001 — Initial Access"],
  "mitre_techniques": ["T1059 — Command and Scripting Interpreter"],
  "ioc_assessment": "Évaluation des IOCs trouvés",
  "recommended_actions": ["Action 1", "Action 2", "Action 3"],
  "hunt_queries": ["Requête de suivi 1", "Requête de suivi 2"],
  "false_positive_assessment": "Évaluation faux positif"
}}"""


class HuntEngine:

    async def run_hunt(self, hunt_id: int):
        db = SessionLocal()
        try:
            from database.models import ThreatHunt
            hunt = db.query(ThreatHunt).filter(ThreatHunt.id == hunt_id).first()
            if not hunt:
                return

            hunt.status     = "RUNNING"
            hunt.started_at = datetime.utcnow()
            db.commit()

            findings  = []
            findings += self._hunt_ioc_in_alerts(db, hunt)
            await asyncio.sleep(0.05)
            findings += self._hunt_ioc_in_intel(db, hunt)
            await asyncio.sleep(0.05)
            findings += self._hunt_network_behavior(db, hunt)
            await asyncio.sleep(0.05)
            findings += self._hunt_edr_events(db, hunt)

            ai_report  = await self._ai_report(hunt, findings)
            confidence = min(100.0, sum(_SEV_WEIGHT.get(f["severity"], 0) for f in findings))
            verdict    = ai_report.get("verdict", "UNKNOWN") if ai_report else "UNKNOWN"
            if verdict not in ("CONFIRMED", "LIKELY", "UNLIKELY", "BENIGN"):
                verdict = "UNKNOWN"

            from database.models import HuntFinding
            for f in findings:
                db.add(HuntFinding(
                    hunt_id     = hunt_id,
                    severity    = f.get("severity", "INFO"),
                    source      = f.get("source", "unknown"),
                    category    = f.get("category"),
                    title       = f.get("title", "Finding"),
                    description = f.get("description"),
                    evidence    = f.get("evidence"),
                    ioc_type    = f.get("ioc_type"),
                    ioc_value   = f.get("ioc_value"),
                    host        = f.get("host"),
                ))

            hunt.findings_count = len(findings)
            hunt.confidence     = confidence
            hunt.verdict        = verdict
            hunt.ai_analysis    = ai_report
            hunt.status         = "COMPLETED"
            hunt.finished_at    = datetime.utcnow()
            hunt.duration_sec   = int((hunt.finished_at - hunt.started_at).total_seconds())
            db.commit()

        except Exception:
            try:
                from database.models import ThreatHunt
                h = db.query(ThreatHunt).filter(ThreatHunt.id == hunt_id).first()
                if h:
                    h.status      = "FAILED"
                    h.finished_at = datetime.utcnow()
                    db.commit()
            except Exception:
                pass
        finally:
            db.close()

    # ── Phase 1 : IOC dans alertes ────────────────────────────────────────────

    def _hunt_ioc_in_alerts(self, db: Session, hunt) -> list:
        findings = []
        qv = (hunt.query_value or "").strip()
        if not qv:
            return findings
        from database.models import Alert
        since = datetime.utcnow() - timedelta(days=90)

        if hunt.query_type == "IOC":
            alerts = db.query(Alert).filter(
                Alert.timestamp >= since,
                or_(Alert.source_ip == qv, Alert.destination_ip == qv)
            ).order_by(desc(Alert.timestamp)).limit(50).all()
        else:
            alerts = db.query(Alert).filter(
                Alert.timestamp >= since,
                or_(Alert.title.ilike(f"%{qv}%"),
                    Alert.description.ilike(f"%{qv}%"),
                    Alert.source_ip == qv)
            ).order_by(desc(Alert.timestamp)).limit(50).all()

        for a in alerts:
            sev = a.severity if a.severity in ("CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO") else "MEDIUM"
            findings.append({
                "severity":    sev,
                "source":      "alerts",
                "category":    a.category,
                "title":       f"Alerte liée : {a.title}",
                "description": a.description or "",
                "evidence":    f"Alerte #{a.id} | {a.source_ip} → {a.destination_ip} | {a.timestamp.isoformat()}",
                "ioc_type":    "IP" if _is_ip(qv) else "PATTERN",
                "ioc_value":   qv,
                "host":        a.source_ip,
            })
        return findings

    # ── Phase 2 : IOC dans Threat Intel ──────────────────────────────────────

    def _hunt_ioc_in_intel(self, db: Session, hunt) -> list:
        findings = []
        qv = (hunt.query_value or "").strip()
        if not qv:
            return findings
        try:
            from database.models import ThreatIOC
            iocs = db.query(ThreatIOC).filter(
                ThreatIOC.active == True,
                ThreatIOC.value.ilike(f"%{qv}%"),
            ).limit(20).all()
            for ioc in iocs:
                findings.append({
                    "severity":    ioc.severity,
                    "source":      "intel",
                    "category":    "THREAT_INTEL_MATCH",
                    "title":       f"IOC connu en base : {ioc.value}",
                    "description": ioc.description or f"Type:{ioc.threat_type} — Confiance:{ioc.confidence}%",
                    "evidence":    f"IOC #{ioc.id} | type:{ioc.ioc_type} | source:{ioc.source} | hits:{ioc.hit_count}",
                    "ioc_type":    ioc.ioc_type,
                    "ioc_value":   ioc.value,
                    "host":        ioc.value if ioc.ioc_type == "IP" else None,
                })
        except Exception:
            pass
        return findings

    # ── Phase 3 : Comportement réseau ─────────────────────────────────────────

    def _hunt_network_behavior(self, db: Session, hunt) -> list:
        findings = []
        since = datetime.utcnow() - timedelta(days=30)
        try:
            from database.models import Alert
            bf = (
                db.query(Alert.source_ip, func.count(Alert.id).label("cnt"))
                .filter(Alert.timestamp >= since, Alert.category == "BRUTE_FORCE")
                .group_by(Alert.source_ip)
                .having(func.count(Alert.id) > 10).limit(10).all()
            )
            for ip, cnt in bf:
                if ip:
                    findings.append({
                        "severity": "HIGH", "source": "network", "category": "BRUTE_FORCE",
                        "title": f"Brute force persistant depuis {ip}",
                        "description": f"{cnt} alertes brute force en 30 jours",
                        "evidence": f"IP:{ip} | tentatives:{cnt}",
                        "ioc_type": "IP", "ioc_value": ip, "host": ip,
                    })

            ps = (
                db.query(Alert.source_ip, func.count(Alert.id).label("cnt"))
                .filter(Alert.timestamp >= since, Alert.category == "PORT_SCAN")
                .group_by(Alert.source_ip)
                .having(func.count(Alert.id) > 5).limit(10).all()
            )
            for ip, cnt in ps:
                if ip:
                    findings.append({
                        "severity": "MEDIUM", "source": "network", "category": "PORT_SCAN",
                        "title": f"Scan de ports répété depuis {ip}",
                        "description": f"{cnt} scans en 30 jours",
                        "evidence": f"IP:{ip} | scans:{cnt}",
                        "ioc_type": "IP", "ioc_value": ip, "host": ip,
                    })

            exfil = (
                db.query(Alert)
                .filter(Alert.timestamp >= since, Alert.category == "DATA_EXFILTRATION")
                .order_by(desc(Alert.timestamp)).limit(5).all()
            )
            for a in exfil:
                findings.append({
                    "severity": "CRITICAL", "source": "network", "category": "DATA_EXFILTRATION",
                    "title": f"Exfiltration : {a.title}",
                    "description": a.description or "",
                    "evidence": f"Alerte #{a.id} | {a.source_ip} → {a.destination_ip}",
                    "ioc_type": "IP", "ioc_value": a.source_ip, "host": a.source_ip,
                })
        except Exception:
            pass
        return findings

    # ── Phase 4 : Events EDR + flux NTA suspects ──────────────────────────────

    def _hunt_edr_events(self, db: Session, hunt) -> list:
        findings = []
        since = datetime.utcnow() - timedelta(days=7)
        try:
            from database.models import EdrEvent
            critical = (
                db.query(EdrEvent)
                .filter(EdrEvent.timestamp >= since, EdrEvent.severity == "CRITICAL")
                .order_by(desc(EdrEvent.timestamp)).limit(10).all()
            )
            for e in critical:
                findings.append({
                    "severity": "CRITICAL", "source": "edr", "category": e.event_type,
                    "title": f"EDR critique : {e.event_type} sur {e.hostname or 'inconnu'}",
                    "description": e.description or e.command_line or "",
                    "evidence": f"EDR #{e.id} | host:{e.hostname} | process:{e.process_name}",
                    "ioc_type": "HOST", "ioc_value": e.hostname, "host": e.hostname,
                })
        except Exception:
            pass
        try:
            from database.models import NetworkFlow
            c2_flows = (
                db.query(NetworkFlow)
                .filter(
                    NetworkFlow.detected_at >= since,
                    NetworkFlow.threat_type.in_(["C2", "BEACONING", "DNS_TUNNEL", "EXFIL"])
                )
                .order_by(desc(NetworkFlow.detected_at)).limit(10).all()
            )
            for f in c2_flows:
                findings.append({
                    "severity": "HIGH", "source": "nta", "category": f.threat_type,
                    "title": f"Trafic suspect {f.threat_type} : {f.src_ip} → {f.dst_ip}",
                    "description": f"Proto:{f.protocol} | Port:{f.dst_port} | Bytes:{f.bytes_out}",
                    "evidence": f"Flow #{f.id} | risk:{f.risk_score}",
                    "ioc_type": "IP", "ioc_value": f.dst_ip, "host": f.src_ip,
                })
        except Exception:
            pass
        return findings

    # ── Rapport Claude AI ─────────────────────────────────────────────────────

    async def _ai_report(self, hunt, findings: list) -> Optional[dict]:
        try:
            client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
            findings_text = "\n".join(
                f"[{f['severity']}] {f['title']} — {f.get('evidence', '')}"
                for f in findings[:30]
            )
            data = (
                f"Hypothèse : {hunt.hypothesis}\n"
                f"Type : {hunt.query_type}\n"
                f"Valeur cherchée : {hunt.query_value or 'N/A'}\n"
                f"Findings ({len(findings)}) :\n{findings_text or 'Aucun.'}"
            )
            msg = await client.messages.create(
                model=settings.CLAUDE_MODEL,
                max_tokens=1024,
                messages=[{"role": "user", "content": _HUNT_PROMPT.format(data=data)}],
            )
            import json as _json
            text = msg.content[0].text.strip()
            m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
            if m:
                text = m.group(1)
            return _json.loads(text)
        except Exception:
            return _fallback_report(hunt, findings)

    # ── API helpers ───────────────────────────────────────────────────────────

    def get_hunt(self, db: Session, hunt_id: int) -> Optional[dict]:
        from database.models import ThreatHunt, HuntFinding
        hunt = db.query(ThreatHunt).filter(ThreatHunt.id == hunt_id).first()
        if not hunt:
            return None
        findings = db.query(HuntFinding).filter(HuntFinding.hunt_id == hunt_id).all()
        return {**_hunt_to_dict(hunt), "findings": [_finding_to_dict(f) for f in findings]}

    def list_hunts(self, db: Session, page: int = 1, per_page: int = 20) -> dict:
        from database.models import ThreatHunt
        total = db.query(func.count(ThreatHunt.id)).scalar() or 0
        hunts = (db.query(ThreatHunt)
                 .order_by(desc(ThreatHunt.created_at))
                 .offset((page - 1) * per_page).limit(per_page).all())
        return {"total": total, "page": page, "per_page": per_page,
                "hunts": [_hunt_to_dict(h) for h in hunts]}

    def delete_hunt(self, db: Session, hunt_id: int) -> bool:
        from database.models import ThreatHunt, HuntFinding
        db.query(HuntFinding).filter(HuntFinding.hunt_id == hunt_id).delete()
        n = db.query(ThreatHunt).filter(ThreatHunt.id == hunt_id).delete()
        db.commit()
        return n > 0

    def stats(self, db: Session) -> dict:
        from database.models import ThreatHunt
        total     = db.query(func.count(ThreatHunt.id)).scalar() or 0
        completed = db.query(func.count(ThreatHunt.id)).filter(ThreatHunt.status == "COMPLETED").scalar() or 0
        confirmed = db.query(func.count(ThreatHunt.id)).filter(ThreatHunt.verdict == "CONFIRMED").scalar() or 0
        likely    = db.query(func.count(ThreatHunt.id)).filter(ThreatHunt.verdict == "LIKELY").scalar() or 0
        return {"total": total, "completed": completed,
                "confirmed": confirmed, "likely": likely,
                "detection_rate": round((confirmed + likely) / max(completed, 1) * 100, 1)}


def _hunt_to_dict(h) -> dict:
    return {
        "id": h.id, "hypothesis": h.hypothesis, "query_type": h.query_type,
        "query_value": h.query_value, "status": h.status, "verdict": h.verdict,
        "confidence": h.confidence, "findings_count": h.findings_count,
        "ai_analysis": h.ai_analysis, "duration_sec": h.duration_sec,
        "started_at": h.started_at.isoformat() if h.started_at else None,
        "finished_at": h.finished_at.isoformat() if h.finished_at else None,
        "created_at": h.created_at.isoformat() if h.created_at else None,
    }


def _finding_to_dict(f) -> dict:
    return {
        "id": f.id, "hunt_id": f.hunt_id, "severity": f.severity,
        "source": f.source, "category": f.category, "title": f.title,
        "description": f.description, "evidence": f.evidence,
        "ioc_type": f.ioc_type, "ioc_value": f.ioc_value, "host": f.host,
        "found_at": f.found_at.isoformat() if f.found_at else None,
    }


def _fallback_report(hunt, findings: list) -> dict:
    critical = sum(1 for f in findings if f["severity"] == "CRITICAL")
    high     = sum(1 for f in findings if f["severity"] == "HIGH")
    verdict  = "CONFIRMED" if critical > 0 else "LIKELY" if high > 0 else "UNLIKELY" if findings else "BENIGN"
    tactic, tactic_id = _TACTIC_MAP.get(hunt.query_type, ("Unknown", "N/A"))
    return {
        "verdict": verdict,
        "confidence": min(100, critical * 30 + high * 15),
        "executive_summary": f"Chasse terminée : {len(findings)} indicateurs. Hypothèse : {hunt.hypothesis[:100]}",
        "threat_description": f"Analyse basée sur {len(findings)} findings. IA indisponible.",
        "mitre_tactics": [f"{tactic_id} — {tactic}"],
        "mitre_techniques": [],
        "ioc_assessment": f"{sum(1 for f in findings if f.get('source') == 'intel')} IOCs connus.",
        "recommended_actions": ["Investiguer les findings CRITICAL/HIGH", "Escalader si confirmé"],
        "hunt_queries": [f"Rechercher {hunt.query_value} dans les 7 prochains jours"],
        "false_positive_assessment": "Évaluation manuelle requise.",
    }


def _is_ip(value: str) -> bool:
    return bool(re.match(r"^\d{1,3}(\.\d{1,3}){3}$", value or ""))


hunt_engine = HuntEngine()
