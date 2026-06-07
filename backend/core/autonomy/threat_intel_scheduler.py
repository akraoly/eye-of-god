"""
ThreatIntelScheduler — APScheduler job that runs aggregate_all() every 4 hours.
Saves results to DB, creates Alerts for critical CVEs, notifies WebSocket subscribers.
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Optional

from core.engines.threat_intel_feeds import ThreatIntelFeedsEngine
from core.tools.logger import get_logger

logger = get_logger("threat_intel_scheduler")

_engine = ThreatIntelFeedsEngine()

# ── WebSocket broadcast hook (injected by main app if available) ──────────────
_ws_broadcast_fn = None


def set_ws_broadcast(fn):
    """Register a broadcast function for WebSocket notifications."""
    global _ws_broadcast_fn
    _ws_broadcast_fn = fn


async def _broadcast(event: dict):
    """Broadcast to WebSocket subscribers if handler registered."""
    if _ws_broadcast_fn:
        try:
            await _ws_broadcast_fn(event)
        except Exception as e:
            logger.warning(f"WS broadcast failed: {e}")


# ── Core scheduler job ────────────────────────────────────────────────────────

async def run_threat_intel_refresh(db=None):
    """
    Fetch all threat intel feeds, persist to DB, raise alerts for critical findings.
    Called by APScheduler every 4 hours.
    """
    logger.info("[ThreatIntel] Starting scheduled feed refresh...")
    started_at = datetime.utcnow()

    try:
        result = await _engine.aggregate_all()
    except Exception as e:
        logger.error(f"[ThreatIntel] aggregate_all failed: {e}")
        if db:
            _save_job_status(db, status="error", entries=0, alerts=0,
                             started_at=started_at, error=str(e))
        return

    entries     = result.get("all_entries", [])
    critical    = result.get("critical_cves", [])
    alerts_created = 0

    if db:
        try:
            alerts_created = _persist_results(db, entries, critical)
        except Exception as e:
            logger.error(f"[ThreatIntel] DB persist error: {e}")

        try:
            _save_job_status(db, status="success", entries=len(entries),
                             alerts=alerts_created, started_at=started_at)
        except Exception:
            pass

    # Broadcast summary
    summary_event = {
        "type":     "threat_intel_refresh",
        "total":    len(entries),
        "critical": len(critical),
        "alerts":   alerts_created,
        "ts":       datetime.utcnow().isoformat(),
    }
    await _broadcast(summary_event)

    logger.info(
        f"[ThreatIntel] Refresh done — {len(entries)} entries, "
        f"{len(critical)} critical, {alerts_created} alerts."
    )
    return result


def _persist_results(db, entries: list, critical: list) -> int:
    """Save entries to DB, create Alerts for critical CVEs affecting known targets."""
    from database.models import ThreatFeedEntry, Alert

    alerts_created = 0
    for entry in entries[:500]:  # cap at 500 per run
        try:
            existing = db.query(ThreatFeedEntry).filter_by(
                identifier=entry.get("identifier", ""),
                source=entry.get("source", ""),
            ).first()
            if existing:
                continue

            feed_entry = ThreatFeedEntry(
                source=entry.get("source", ""),
                entry_type=entry.get("entry_type", "cve"),
                identifier=entry.get("identifier", entry.get("cve_id", "")),
                title=entry.get("title", "")[:255],
                description=entry.get("description", "")[:1000],
                severity=entry.get("severity", "UNKNOWN"),
                cvss_score=float(entry.get("cvss_score", 0)),
                published_at=_parse_date(entry.get("published_at")),
                fetched_at=datetime.utcnow(),
                affects_known_target=entry.get("affects_known_target", False),
                raw_data=json.dumps(entry.get("raw_data", {}), default=str)[:4000],
            )
            db.add(feed_entry)
        except Exception as e:
            logger.debug(f"Entry persist error: {e}")
            continue

    db.commit()

    # Create alerts for critical CVEs affecting known targets
    for cve in critical:
        if not cve.get("affects_known_target"):
            continue
        try:
            alert = Alert(
                severity="CRITICAL",
                category="THREAT_INTEL",
                title=f"Critical CVE affecting target: {cve.get('identifier', cve.get('cve_id', ''))}",
                description=(
                    f"CVE {cve.get('identifier','')} (CVSS {cve.get('cvss_score',0):.1f}) "
                    f"affects known technology. Matched: {', '.join(cve.get('matched_technologies', []))}. "
                    f"{cve.get('description','')[:300]}"
                ),
                source_engine="threat_intel",
                raw_data=json.dumps(cve, default=str)[:2000],
                mitre_tactic="TA0001",
            )
            db.add(alert)
            alerts_created += 1
        except Exception:
            pass

    if alerts_created:
        db.commit()

    return alerts_created


def _save_job_status(db, status: str, entries: int, alerts: int,
                     started_at: datetime, error: str = ""):
    from database.models import ThreatIntelJob
    try:
        job = ThreatIntelJob(
            last_run=started_at,
            entries_fetched=entries,
            alerts_created=alerts,
            status=status,
            error_message=error[:500] if error else None,
        )
        db.add(job)
        db.commit()
    except Exception as e:
        logger.debug(f"Job status save error: {e}")


def _parse_date(date_str) -> Optional[datetime]:
    if not date_str:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(date_str)[:19], fmt[:len(fmt)])
        except ValueError:
            continue
    return None


# ── APScheduler registration ──────────────────────────────────────────────────

def register_threat_intel_job(scheduler, db_factory):
    """Register the 4-hour threat intel job with APScheduler."""
    from apscheduler.triggers.interval import IntervalTrigger

    async def _job():
        from database.db import SessionLocal
        db = SessionLocal()
        try:
            await run_threat_intel_refresh(db=db)
        finally:
            db.close()

    scheduler.add_job(
        lambda: asyncio.ensure_future(_job()),
        trigger=IntervalTrigger(hours=4),
        id="threat_intel_refresh",
        replace_existing=True,
        max_instances=1,
    )
    logger.info("[ThreatIntel] Scheduled refresh job registered (every 4 hours)")
