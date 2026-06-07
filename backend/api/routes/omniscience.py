"""
Routes /api/omniscience — Omniscience Dashboard (Module 24).

Aggregates data from all platform modules for unified intelligence view.
All endpoints are JWT-protected via the main router.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database.db import get_db
from core.engines.omniscience import OmniscienceEngine

router = APIRouter()
_engine = OmniscienceEngine()


@router.get("/stats")
async def global_stats(db: Session = Depends(get_db)):
    """
    Global platform statistics.
    Counts: active beacons, OSINT jobs, pentest jobs, SOC alerts,
    credentials, fuzzing, lab instances, honeypot captures, and more.
    """
    return await _engine.get_global_stats(db)


@router.get("/activity")
async def recent_activity(
    limit: int = Query(50, ge=1, le=500, description="Max events to return"),
    db: Session = Depends(get_db),
):
    """
    Unified activity timeline across all modules.
    Returns [{timestamp, type, title, severity, data}] sorted newest-first.
    """
    return await _engine.get_recent_activity(db, limit=limit)


@router.get("/targets")
async def top_targets(db: Session = Depends(get_db)):
    """
    Most active targets ranked by combined activity.
    Merges data from TacticalOperation, OsintJob, PentestJob, and ImplantBeacon.
    """
    return await _engine.get_top_targets(db)


@router.get("/network-map")
async def network_map(db: Session = Depends(get_db)):
    """
    Network topology for visualization (D3.js / Cytoscape compatible).
    Returns {nodes, edges} with node types: c2, beacon, lab, pentest_target,
    honeypot, attacker.
    """
    return await _engine.get_network_map(db)


@router.get("/heatmap")
async def activity_heatmap(db: Session = Depends(get_db)):
    """
    Activity heatmap data for the last 30 days.
    Returns [{date, hour, count}] suitable for a calendar heatmap visualization.
    """
    return await _engine.get_heatmap_data(db)


@router.get("/alerts")
async def alerts_by_severity(db: Session = Depends(get_db)):
    """
    All open alerts grouped by severity.
    Returns {CRITICAL: [...], HIGH: [...], MEDIUM: [...], LOW: [...], INFO: [...]}.
    """
    return await _engine.get_alerts_by_severity(db)


@router.get("/report")
async def comprehensive_report(
    format: str = Query("json", description="Report format: json"),
    db: Session = Depends(get_db),
):
    """
    Comprehensive intelligence report combining all module data.
    Includes: global stats, alerts by severity, top targets, recent activity,
    network map, active beacons detail, and exfil summary.
    """
    return await _engine.generate_report(db, fmt=format)
