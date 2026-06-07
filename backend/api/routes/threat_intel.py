"""
Routes /api/threat-intel — Threat intelligence feeds and IOC lookup.
NVD, CISA KEV, Exploit-DB, VirusTotal, AbuseIPDB.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database.db import get_db
from core.engines.threat_intel_feeds import ThreatIntelFeedsEngine
from core.autonomy.threat_intel_scheduler import run_threat_intel_refresh

router  = APIRouter()
_engine = ThreatIntelFeedsEngine()


# ── Pydantic models ───────────────────────────────────────────────────────────

class IOCCheckRequest(BaseModel):
    ioc:      str
    ioc_type: str = "auto"   # ip|hash|url|domain|auto
    api_key:  str | None = None


class CorrelateRequest(BaseModel):
    technologies: list[str]
    days:         int = 7
    severity:     str | None = None


class RefreshRequest(BaseModel):
    source:   str = "all"   # all|nvd|cisa|exploitdb


# ── CVEs ──────────────────────────────────────────────────────────────────────

@router.get("/cves")
async def get_recent_cves(
    severity: str | None = Query(None, description="CRITICAL|HIGH|MEDIUM|LOW"),
    days:     int        = Query(7, ge=1, le=90),
    source:   str        = Query("db", description="db|live"),
    db:       Session    = Depends(get_db),
):
    """Recent CVEs with optional severity and time filters."""
    if source == "live":
        try:
            cves = await _engine.fetch_nvd_recent(days=days, severity=severity)
            return {"source": "nvd_live", "count": len(cves), "cves": cves}
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"NVD API error: {e}")

    # From DB
    try:
        from database.models import ThreatFeedEntry
        since = datetime.utcnow() - timedelta(days=days)
        query = (
            db.query(ThreatFeedEntry)
            .filter(ThreatFeedEntry.entry_type == "cve")
            .filter(ThreatFeedEntry.fetched_at >= since)
        )
        if severity:
            query = query.filter(ThreatFeedEntry.severity == severity.upper())

        entries = query.order_by(ThreatFeedEntry.cvss_score.desc()).limit(200).all()

        return {
            "source": "database",
            "count":  len(entries),
            "cves": [
                {
                    "identifier":   e.identifier,
                    "title":        e.title,
                    "description":  e.description,
                    "severity":     e.severity,
                    "cvss_score":   e.cvss_score,
                    "source":       e.source,
                    "published_at": e.published_at.isoformat() if e.published_at else None,
                    "fetched_at":   e.fetched_at.isoformat() if e.fetched_at else None,
                    "affects_known_target": e.affects_known_target,
                }
                for e in entries
            ],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cisa-kev")
async def get_cisa_kev(
    source: str   = Query("db", description="db|live"),
    db:     Session = Depends(get_db),
):
    """CISA Known Exploited Vulnerabilities catalog."""
    if source == "live":
        try:
            kevs = await _engine.fetch_cisa_kev()
            return {"source": "cisa_live", "count": len(kevs), "vulnerabilities": kevs}
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"CISA API error: {e}")

    try:
        from database.models import ThreatFeedEntry
        entries = (
            db.query(ThreatFeedEntry)
            .filter(ThreatFeedEntry.source == "cisa")
            .order_by(ThreatFeedEntry.fetched_at.desc())
            .limit(500)
            .all()
        )
        return {
            "source": "database",
            "count":  len(entries),
            "vulnerabilities": [
                {
                    "cve_id":      e.identifier,
                    "title":       e.title,
                    "description": e.description,
                    "severity":    e.severity,
                    "published_at": e.published_at.isoformat() if e.published_at else None,
                    "raw":         json.loads(e.raw_data) if e.raw_data else {},
                }
                for e in entries
            ],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/exploits")
async def get_recent_exploits(
    days:   int     = Query(7, ge=1, le=90),
    source: str     = Query("db", description="db|live"),
    db:     Session = Depends(get_db),
):
    """Recent public exploits from Exploit-DB."""
    if source == "live":
        try:
            exploits = await _engine.fetch_exploitdb_recent(days=days)
            return {"source": "exploitdb_live", "count": len(exploits), "exploits": exploits}
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Exploit-DB API error: {e}")

    try:
        from database.models import ThreatFeedEntry
        since = datetime.utcnow() - timedelta(days=days)
        entries = (
            db.query(ThreatFeedEntry)
            .filter(ThreatFeedEntry.entry_type == "exploit")
            .filter(ThreatFeedEntry.fetched_at >= since)
            .order_by(ThreatFeedEntry.fetched_at.desc())
            .limit(100)
            .all()
        )
        return {
            "source": "database",
            "count":  len(entries),
            "exploits": [
                {
                    "identifier":  e.identifier,
                    "title":       e.title,
                    "description": e.description,
                    "source":      e.source,
                    "published_at": e.published_at.isoformat() if e.published_at else None,
                }
                for e in entries
            ],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── IOC Lookup ────────────────────────────────────────────────────────────────

@router.post("/ioc/check")
async def check_ioc(req: IOCCheckRequest):
    """IOC lookup across available sources (VirusTotal, AbuseIPDB, etc.)."""
    if not req.ioc or not req.ioc.strip():
        raise HTTPException(status_code=400, detail="IOC value required")

    result: dict = {
        "ioc":      req.ioc,
        "ioc_type": req.ioc_type,
        "results":  {},
    }

    # Auto-detect type
    if req.ioc_type == "auto":
        import re
        if re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", req.ioc):
            req.ioc_type = "ip"
        elif re.match(r"^[a-fA-F0-9]{32}$|^[a-fA-F0-9]{40}$|^[a-fA-F0-9]{64}$", req.ioc):
            req.ioc_type = "hash"
        elif req.ioc.startswith("http"):
            req.ioc_type = "url"
        else:
            req.ioc_type = "domain"
        result["ioc_type"] = req.ioc_type

    if req.api_key:
        # VT check
        vt_result = await _engine.check_virustotal(req.ioc, req.ioc_type, api_key=req.api_key)
        result["results"]["virustotal"] = vt_result

        # AbuseIPDB for IPs
        if req.ioc_type in ("ip", "ip_address"):
            abuse_result = await _engine.check_abuseipdb(req.ioc, api_key=req.api_key)
            result["results"]["abuseipdb"] = abuse_result
    else:
        result["results"]["note"] = "Provide api_key for VirusTotal and AbuseIPDB lookups"
        basic = await _engine.search_ioc(req.ioc)
        result.update(basic)

    return result


# ── Correlation ───────────────────────────────────────────────────────────────

@router.post("/correlate")
async def correlate_cves(req: CorrelateRequest, db: Session = Depends(get_db)):
    """Correlate recent CVEs with known target technologies."""
    if not req.technologies:
        raise HTTPException(status_code=400, detail="technologies list required")

    # Get CVEs from DB
    try:
        from database.models import ThreatFeedEntry
        since = datetime.utcnow() - timedelta(days=req.days)
        entries = (
            db.query(ThreatFeedEntry)
            .filter(ThreatFeedEntry.entry_type == "cve")
            .filter(ThreatFeedEntry.fetched_at >= since)
            .all()
        )
        cves = [
            {
                "identifier":       e.identifier,
                "description":      e.description,
                "severity":         e.severity,
                "cvss_score":       e.cvss_score,
                "affected_product": "",
                "title":            e.title,
            }
            for e in entries
        ]
    except Exception:
        cves = []

    # Also fetch live if DB is empty
    if not cves:
        cves = await _engine.fetch_nvd_recent(days=req.days, severity=req.severity)

    matched = await _engine.correlate_with_targets(cves, req.technologies)

    return {
        "technologies": req.technologies,
        "total_cves":   len(cves),
        "matched":      len(matched),
        "affected_cves": matched,
    }


# ── Manual refresh ────────────────────────────────────────────────────────────

@router.post("/refresh")
async def refresh_feeds(db: Session = Depends(get_db)):
    """Manually trigger a threat intel feed refresh."""
    try:
        result = await run_threat_intel_refresh(db=db)
        return {
            "status":    "completed",
            "total":     result.get("total_entries", 0) if result else 0,
            "critical":  result.get("critical_count", 0) if result else 0,
            "fetched_at": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Feed refresh failed: {e}")


# ── Status ────────────────────────────────────────────────────────────────────

@router.get("/status")
def get_status(db: Session = Depends(get_db)):
    """Last fetch time and entry counts."""
    try:
        from database.models import ThreatFeedEntry, ThreatIntelJob
        total_entries = db.query(ThreatFeedEntry).count()
        cve_count     = db.query(ThreatFeedEntry).filter(ThreatFeedEntry.entry_type == "cve").count()
        exploit_count = db.query(ThreatFeedEntry).filter(ThreatFeedEntry.entry_type == "exploit").count()
        critical_count = db.query(ThreatFeedEntry).filter(ThreatFeedEntry.severity == "CRITICAL").count()

        last_job = db.query(ThreatIntelJob).order_by(ThreatIntelJob.last_run.desc()).first()

        return {
            "total_entries":  total_entries,
            "cve_count":      cve_count,
            "exploit_count":  exploit_count,
            "critical_count": critical_count,
            "last_run":       last_job.last_run.isoformat() if last_job and last_job.last_run else None,
            "last_status":    last_job.status if last_job else "never",
            "entries_fetched": last_job.entries_fetched if last_job else 0,
            "alerts_created": last_job.alerts_created if last_job else 0,
        }
    except Exception as e:
        return {"error": str(e), "total_entries": 0}
