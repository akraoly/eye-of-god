"""
OmniscienceEngine — Module 24
Aggregates data from all platform modules for a unified intelligence view.
Provides global stats, activity timeline, network map, heatmap, and reports.
"""
from __future__ import annotations

import json
import logging
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class OmniscienceEngine:
    """
    Aggregates data from all platform modules for unified view.
    All methods accept a SQLAlchemy Session and return serializable dicts/lists.
    """

    # ── Global Stats ──────────────────────────────────────────────────────────

    async def get_global_stats(self, db: Session) -> dict:
        """
        Count all entities across every module.
        Returns: unified stats dict.
        """
        stats: dict = {}

        def _count(model_name: str) -> int:
            try:
                from database import models as m
                model = getattr(m, model_name, None)
                if model is None:
                    return 0
                return db.query(model).count()
            except Exception as exc:
                logger.debug("[omniscience] stats %s: %s", model_name, exc)
                return 0

        def _count_filtered(model_name: str, **kwargs) -> int:
            try:
                from database import models as m
                model = getattr(m, model_name, None)
                if model is None:
                    return 0
                q = db.query(model)
                for k, v in kwargs.items():
                    col = getattr(model, k, None)
                    if col is not None:
                        q = q.filter(col == v)
                return q.count()
            except Exception as exc:
                logger.debug("[omniscience] stats_filtered %s: %s", model_name, exc)
                return 0

        # Beacons
        stats["active_beacons"] = _count_filtered("ImplantBeacon", status="active")
        stats["total_beacons"] = _count("ImplantBeacon")

        # OSINT
        stats["osint_jobs_completed"] = _count_filtered("OsintJob", status="completed")
        stats["osint_jobs_total"] = _count("OsintJob")

        # Pentest
        stats["pentest_jobs_total"] = _count("PentestJob")
        stats["pentest_jobs_completed"] = _count_filtered("PentestJob", status="completed")

        # SOC alerts
        stats["soc_alerts_open"] = _count_filtered("Alert", status="NEW")
        stats["soc_alerts_total"] = _count("Alert")
        stats["soc_incidents_open"] = _count_filtered("Incident", status="OPEN")

        # Cameras (not a dedicated table — check vision/network if available)
        stats["cameras_discovered"] = 0  # placeholder — no CameraDiscovery model yet

        # Audio recordings
        stats["audio_recordings"] = 0  # placeholder

        # CVEs
        stats["cves_tracked"] = _count("ThreatFeedEntry")

        # Lab
        stats["lab_instances"] = _count("LabInstance")
        stats["lab_running"] = _count_filtered("LabInstance", status="running")

        # Fuzzing
        stats["fuzzing_jobs"] = _count("FuzzingJob")

        # Honeypots
        stats["honeypot_captures"] = _count("HoneypotCapture")

        # Credentials
        stats["cracked_credentials"] = _count("CrackedCredential")

        # Reports
        stats["generated_reports"] = _count("GeneratedReport")

        # Post-exploit (new modules)
        stats["keystroke_logs"] = _count("KeystrokeLog")
        stats["clipboard_captures"] = _count("ClipboardCapture")
        stats["captured_forms"] = _count("CapturedForm")

        # Triggers
        stats["active_triggers"] = _count_filtered("AutoTrigger", enabled=True)
        stats["total_triggers"] = _count("AutoTrigger")

        # Exfil
        stats["exfil_jobs"] = _count("ExfilJob")
        stats["exfil_completed"] = _count_filtered("ExfilJob", status="completed")

        # Lateral movement
        stats["lateral_movements"] = _count("LateralMovement")

        # Threat Intel
        stats["threat_iocs"] = _count("ThreatIOC")

        # Forensics
        stats["forensics_cases"] = _count("ForensicsCase")

        # EDR
        stats["edr_agents_online"] = _count_filtered("EdrAgent", status="online")

        stats["generated_at"] = datetime.utcnow().isoformat()
        return stats

    # ── Recent Activity ───────────────────────────────────────────────────────

    async def get_recent_activity(self, db: Session, limit: int = 50) -> list:
        """
        Timeline of recent actions across all modules.
        Merges: alerts, pentest jobs, OSINT jobs, beacons, recordings, exfil.
        Returns: [{timestamp, type, title, severity, data}] sorted desc.
        """
        activities = []

        def _safe_iso(dt) -> str:
            if dt is None:
                return datetime.utcnow().isoformat()
            if isinstance(dt, str):
                return dt
            return dt.isoformat()

        # SOC Alerts
        try:
            from database.models import Alert
            alerts = db.query(Alert).order_by(Alert.created_at.desc()).limit(limit).all()
            for a in alerts:
                activities.append({
                    "timestamp": _safe_iso(a.created_at),
                    "type": "soc_alert",
                    "title": a.title,
                    "severity": a.severity,
                    "data": {
                        "alert_id": a.id,
                        "category": a.category,
                        "source_ip": a.source_ip,
                        "status": a.status,
                    },
                })
        except Exception as exc:
            logger.debug("[omniscience] activity alerts: %s", exc)

        # Pentest Jobs
        try:
            from database.models import PentestJob
            jobs = db.query(PentestJob).order_by(PentestJob.created_at.desc()).limit(limit).all()
            for j in jobs:
                activities.append({
                    "timestamp": _safe_iso(j.created_at),
                    "type": "pentest_job",
                    "title": f"Pentest: {j.target}",
                    "severity": "INFO",
                    "data": {
                        "job_id": j.job_id,
                        "target": j.target,
                        "status": j.status,
                    },
                })
        except Exception as exc:
            logger.debug("[omniscience] activity pentest: %s", exc)

        # OSINT Jobs
        try:
            from database.models import OsintJob
            jobs = db.query(OsintJob).order_by(OsintJob.created_at.desc()).limit(limit).all()
            for j in jobs:
                activities.append({
                    "timestamp": _safe_iso(j.created_at),
                    "type": "osint_job",
                    "title": f"OSINT: {j.target}",
                    "severity": "INFO",
                    "data": {
                        "job_id": j.job_id,
                        "target": j.target,
                        "status": j.status,
                    },
                })
        except Exception as exc:
            logger.debug("[omniscience] activity osint: %s", exc)

        # Beacons
        try:
            from database.models import ImplantBeacon
            beacons = db.query(ImplantBeacon).order_by(ImplantBeacon.first_seen.desc()).limit(limit).all()
            for b in beacons:
                activities.append({
                    "timestamp": _safe_iso(b.first_seen),
                    "type": "beacon_connected",
                    "title": f"Beacon: {b.hostname} ({b.ip})",
                    "severity": "HIGH",
                    "data": {
                        "beacon_id": b.beacon_id,
                        "hostname": b.hostname,
                        "ip": b.ip,
                        "os": b.os_type,
                        "status": b.status,
                    },
                })
        except Exception as exc:
            logger.debug("[omniscience] activity beacons: %s", exc)

        # Exfil Jobs
        try:
            from database.models import ExfilJob
            exfils = db.query(ExfilJob).order_by(ExfilJob.created_at.desc()).limit(limit).all()
            for e in exfils:
                activities.append({
                    "timestamp": _safe_iso(e.created_at),
                    "type": "exfil_job",
                    "title": f"Exfil via {e.channel}: {e.data_size} bytes",
                    "severity": "CRITICAL",
                    "data": {
                        "exfil_id": e.exfil_id,
                        "channel": e.channel,
                        "status": e.status,
                        "chunks_sent": e.chunks_sent,
                    },
                })
        except Exception as exc:
            logger.debug("[omniscience] activity exfil: %s", exc)

        # Keystrokes
        try:
            from database.models import KeystrokeLog
            ks_logs = db.query(KeystrokeLog).order_by(KeystrokeLog.captured_at.desc()).limit(limit // 5).all()
            for k in ks_logs:
                activities.append({
                    "timestamp": _safe_iso(k.captured_at),
                    "type": "keystrokes_captured",
                    "title": f"Keystrokes: session {k.session_id}",
                    "severity": "HIGH",
                    "data": {
                        "log_id": k.log_id,
                        "session_id": k.session_id,
                        "window": k.window_title,
                        "app": k.app_name,
                    },
                })
        except Exception as exc:
            logger.debug("[omniscience] activity keystrokes: %s", exc)

        # Trigger firings
        try:
            from database.models import TriggerLog
            tl = db.query(TriggerLog).order_by(TriggerLog.triggered_at.desc()).limit(limit // 5).all()
            for t in tl:
                activities.append({
                    "timestamp": _safe_iso(t.triggered_at),
                    "type": "trigger_fired",
                    "title": f"Trigger fired: {t.trigger_id[:8]}",
                    "severity": "MEDIUM" if t.success else "LOW",
                    "data": {
                        "log_id": t.log_id,
                        "trigger_id": t.trigger_id,
                        "success": t.success,
                    },
                })
        except Exception as exc:
            logger.debug("[omniscience] activity triggers: %s", exc)

        # Sort by timestamp descending
        def _ts_key(item):
            try:
                ts = item["timestamp"]
                if isinstance(ts, str):
                    return ts
                return str(ts)
            except Exception:
                return ""

        activities.sort(key=_ts_key, reverse=True)
        return activities[:limit]

    # ── Top Targets ───────────────────────────────────────────────────────────

    async def get_top_targets(self, db: Session) -> list:
        """
        Most active targets: merge TacticalOperation + OsintJob + PentestJob.
        Returns list of {target, job_count, last_seen, types}.
        """
        from collections import Counter
        target_counts: Counter = Counter()
        target_times: dict = {}
        target_types: dict = defaultdict(set)

        def _safe_iso(dt) -> str:
            if dt is None:
                return ""
            return dt.isoformat() if hasattr(dt, "isoformat") else str(dt)

        # PentestJob
        try:
            from database.models import PentestJob
            for j in db.query(PentestJob).all():
                target_counts[j.target] += 1
                t = _safe_iso(j.created_at)
                if t > target_times.get(j.target, ""):
                    target_times[j.target] = t
                target_types[j.target].add("pentest")
        except Exception as exc:
            logger.debug("[omniscience] top_targets pentest: %s", exc)

        # OsintJob
        try:
            from database.models import OsintJob
            for j in db.query(OsintJob).all():
                target_counts[j.target] += 1
                t = _safe_iso(j.created_at)
                if t > target_times.get(j.target, ""):
                    target_times[j.target] = t
                target_types[j.target].add("osint")
        except Exception as exc:
            logger.debug("[omniscience] top_targets osint: %s", exc)

        # TacticalOperation
        try:
            from database.models import TacticalOperation
            for op in db.query(TacticalOperation).all():
                target_counts[op.target] += 1
                t = _safe_iso(op.created_at)
                if t > target_times.get(op.target, ""):
                    target_times[op.target] = t
                target_types[op.target].add("tactical")
        except Exception as exc:
            logger.debug("[omniscience] top_targets tactical: %s", exc)

        # ImplantBeacon
        try:
            from database.models import ImplantBeacon
            for b in db.query(ImplantBeacon).all():
                key = b.ip or b.hostname
                target_counts[key] += 2  # beacons count double (active compromise)
                t = _safe_iso(b.last_seen)
                if t > target_times.get(key, ""):
                    target_times[key] = t
                target_types[key].add("beacon")
        except Exception as exc:
            logger.debug("[omniscience] top_targets beacons: %s", exc)

        results = [
            {
                "target": target,
                "job_count": count,
                "last_seen": target_times.get(target, ""),
                "types": list(target_types.get(target, set())),
            }
            for target, count in target_counts.most_common(20)
        ]
        return results

    # ── Network Map ───────────────────────────────────────────────────────────

    async def get_network_map(self, db: Session) -> dict:
        """
        Build network topology from discovered data.
        nodes: cameras, lab instances, pentest targets, beacons
        edges: connections, relationships
        Returns: {nodes: [...], edges: [...]} for D3/Cytoscape.
        """
        nodes = []
        edges = []
        node_ids: set = set()

        def _add_node(node_id: str, label: str, node_type: str, **props):
            if node_id not in node_ids:
                node_ids.add(node_id)
                nodes.append({"id": node_id, "label": label, "type": node_type, **props})

        # C2/Attacker node
        _add_node("c2_server", "C2 Server", "c2", color="#ff4444")

        # Beacons
        try:
            from database.models import ImplantBeacon
            for b in db.query(ImplantBeacon).filter(ImplantBeacon.status == "active").all():
                nid = f"beacon_{b.beacon_id[:8]}"
                _add_node(
                    nid,
                    f"{b.hostname} ({b.ip})",
                    "beacon",
                    ip=b.ip,
                    os=b.os_type,
                    color="#ff8800",
                )
                edges.append({
                    "source": "c2_server",
                    "target": nid,
                    "label": b.protocol or "c2",
                    "type": "c2_channel",
                })
        except Exception as exc:
            logger.debug("[omniscience] network_map beacons: %s", exc)

        # Lab instances
        try:
            from database.models import LabInstance
            for lab in db.query(LabInstance).filter(LabInstance.status == "running").all():
                nid = f"lab_{lab.lab_id[:8]}"
                _add_node(
                    nid,
                    f"Lab: {lab.template_name}",
                    "lab",
                    ip=lab.target_ip,
                    color="#44aaff",
                )
                edges.append({
                    "source": "c2_server",
                    "target": nid,
                    "label": "lab_network",
                    "type": "lab",
                })
        except Exception as exc:
            logger.debug("[omniscience] network_map labs: %s", exc)

        # Pentest targets
        try:
            from database.models import PentestJob
            seen_targets = set()
            for j in db.query(PentestJob).filter(PentestJob.status == "completed").all():
                if j.target not in seen_targets:
                    seen_targets.add(j.target)
                    nid = f"pentest_{j.target.replace('.', '_').replace('/', '_')}"
                    _add_node(nid, j.target, "pentest_target", color="#aa44ff")
                    edges.append({
                        "source": "c2_server",
                        "target": nid,
                        "label": "pentest",
                        "type": "recon",
                    })
        except Exception as exc:
            logger.debug("[omniscience] network_map pentest: %s", exc)

        # Honeypots
        try:
            from database.models import HoneypotConfig, HoneypotCapture
            for hp in db.query(HoneypotConfig).filter(HoneypotConfig.is_active == True).all():
                nid = f"honeypot_{hp.honeypot_id[:8]}"
                _add_node(
                    nid,
                    f"Honeypot:{hp.service_type}:{hp.port}",
                    "honeypot",
                    port=hp.port,
                    color="#44ff88",
                )
                # Attacker nodes from captures
                captures = (
                    db.query(HoneypotCapture)
                    .filter(HoneypotCapture.honeypot_id == hp.honeypot_id)
                    .limit(10)
                    .all()
                )
                for cap in captures:
                    aid = f"attacker_{cap.attacker_ip.replace('.', '_')}"
                    _add_node(aid, f"Attacker: {cap.attacker_ip}", "attacker", ip=cap.attacker_ip, color="#ff4444")
                    edges.append({
                        "source": aid,
                        "target": nid,
                        "label": "attack",
                        "type": "honeypot_hit",
                    })
        except Exception as exc:
            logger.debug("[omniscience] network_map honeypots: %s", exc)

        return {
            "nodes": nodes,
            "edges": edges,
            "node_count": len(nodes),
            "edge_count": len(edges),
            "generated_at": datetime.utcnow().isoformat(),
        }

    # ── Heatmap ───────────────────────────────────────────────────────────────

    async def get_heatmap_data(self, db: Session) -> list:
        """
        Activity heatmap: count events per day/hour for the last 30 days.
        Returns list of {date, hour, count} suitable for D3/Chart.js.
        """
        from collections import defaultdict
        heatmap: dict = defaultdict(int)  # (date_str, hour) -> count

        cutoff = datetime.utcnow() - timedelta(days=30)

        def _add_events(model_name: str, ts_field: str) -> None:
            try:
                from database import models as m
                model = getattr(m, model_name, None)
                if model is None:
                    return
                ts_col = getattr(model, ts_field, None)
                if ts_col is None:
                    return
                rows = db.query(ts_col).filter(ts_col >= cutoff).all()
                for (ts,) in rows:
                    if ts:
                        dt = ts if isinstance(ts, datetime) else datetime.fromisoformat(str(ts))
                        key = (dt.strftime("%Y-%m-%d"), dt.hour)
                        heatmap[key] += 1
            except Exception as exc:
                logger.debug("[omniscience] heatmap %s: %s", model_name, exc)

        _add_events("Alert", "created_at")
        _add_events("PentestJob", "created_at")
        _add_events("OsintJob", "created_at")
        _add_events("KeystrokeLog", "captured_at")
        _add_events("ClipboardCapture", "captured_at")
        _add_events("TriggerLog", "triggered_at")
        _add_events("ExfilJob", "created_at")
        _add_events("HoneypotCapture", "timestamp")
        _add_events("ImplantBeacon", "first_seen")

        return [
            {"date": k[0], "hour": k[1], "count": v}
            for k, v in sorted(heatmap.items())
        ]

    # ── Alerts by Severity ────────────────────────────────────────────────────

    async def get_alerts_by_severity(self, db: Session) -> dict:
        """
        Group all alerts by severity.
        Returns: {CRITICAL: [...], HIGH: [...], MEDIUM: [...], LOW: [...]}
        """
        result: dict = {"CRITICAL": [], "HIGH": [], "MEDIUM": [], "LOW": [], "INFO": []}

        try:
            from database.models import Alert
            alerts = (
                db.query(Alert)
                .filter(Alert.status.in_(["NEW", "ACK", "IN_PROGRESS"]))
                .order_by(Alert.created_at.desc())
                .limit(500)
                .all()
            )
            for a in alerts:
                sev = a.severity.upper() if a.severity else "INFO"
                if sev not in result:
                    result[sev] = []
                result[sev].append({
                    "id": a.id,
                    "uuid": a.alert_uuid,
                    "title": a.title,
                    "category": a.category,
                    "source_ip": a.source_ip,
                    "status": a.status,
                    "timestamp": a.timestamp.isoformat() if a.timestamp else None,
                })
        except Exception as exc:
            logger.debug("[omniscience] alerts_by_severity: %s", exc)

        return result

    # ── Report ────────────────────────────────────────────────────────────────

    async def generate_report(self, db: Session, fmt: str = "json") -> dict:
        """
        Comprehensive report combining all module data.
        fmt: json (always) — PDF generation requires reportlab (future).
        """
        report = {
            "report_id": __import__("uuid").uuid4().hex[:12],
            "generated_at": datetime.utcnow().isoformat(),
            "format": fmt,
            "platform": "L'Oeil de Dieu",
        }

        report["global_stats"] = await self.get_global_stats(db)
        report["alerts_by_severity"] = await self.get_alerts_by_severity(db)
        report["top_targets"] = await self.get_top_targets(db)
        report["recent_activity"] = await self.get_recent_activity(db, limit=20)
        report["network_map"] = await self.get_network_map(db)
        report["heatmap_sample"] = (await self.get_heatmap_data(db))[:50]

        # Module-specific summaries
        try:
            from database.models import ImplantBeacon
            beacons = db.query(ImplantBeacon).filter(ImplantBeacon.status == "active").all()
            report["active_beacons_detail"] = [
                {
                    "beacon_id": b.beacon_id,
                    "hostname": b.hostname,
                    "ip": b.ip,
                    "os": b.os_type,
                    "privilege": b.privilege,
                    "last_seen": b.last_seen.isoformat() if b.last_seen else None,
                }
                for b in beacons[:20]
            ]
        except Exception:
            report["active_beacons_detail"] = []

        try:
            from database.models import ExfilJob
            exfil_jobs = db.query(ExfilJob).order_by(ExfilJob.created_at.desc()).limit(10).all()
            report["exfil_summary"] = [
                {
                    "exfil_id": e.exfil_id,
                    "channel": e.channel,
                    "status": e.status,
                    "data_size": e.data_size,
                    "completed_at": e.completed_at.isoformat() if e.completed_at else None,
                }
                for e in exfil_jobs
            ]
        except Exception:
            report["exfil_summary"] = []

        return report
