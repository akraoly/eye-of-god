"""
Routes /api/mitre — Module MITRE ATT&CK automatique.
Expose les stats, graphes, heatmaps, recommandations et log manuel.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.auth.dependencies import get_current_user
from database.db import get_db
from database.models import AppUser
from database.models_mitre import MitreEvent
from services.mitre.mitre_mapper_service import (
    MitreMapperService,
    ACTIONS_MAP,
    TACTICS_MAP,
)

router = APIRouter()

# Singleton du service
mitre_service = MitreMapperService()


# ── Schémas Pydantic ──────────────────────────────────────────────────────────

class LogActionBody(BaseModel):
    campaign_id: str
    action_type: str
    details: dict = {}


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/campaign/{campaign_id}/stats")
async def get_campaign_stats(
    campaign_id: str,
    db: Session = Depends(get_db),
    _user: AppUser = Depends(get_current_user),
):
    """Stats MITRE agrégées d'une campagne."""
    return await mitre_service.get_campaign_mitre_stats(campaign_id, db)


@router.get("/campaign/{campaign_id}/graph")
async def get_attack_graph(
    campaign_id: str,
    db: Session = Depends(get_db),
    _user: AppUser = Depends(get_current_user),
):
    """Graphe d'attaque (noeuds + arêtes + kill chain progress)."""
    return await mitre_service.get_attack_graph(campaign_id, db)


@router.get("/campaign/{campaign_id}/heatmap")
async def get_heatmap(
    campaign_id: str,
    db: Session = Depends(get_db),
    _user: AppUser = Depends(get_current_user),
):
    """Heatmap tactic × technique pour la campagne."""
    return await mitre_service.get_heatmap(campaign_id, db)


@router.get("/campaign/{campaign_id}/recommendations")
async def get_recommendations(
    campaign_id: str,
    db: Session = Depends(get_db),
    _user: AppUser = Depends(get_current_user),
):
    """Techniques recommandées non encore couvertes, triées par priorité."""
    recs = await mitre_service.recommend_next_techniques(campaign_id, db)
    return {"campaign_id": campaign_id, "recommendations": recs}


@router.get("/campaign/{campaign_id}/report")
async def get_report(
    campaign_id: str,
    format: str = Query("json", description="Format du rapport: json"),
    db: Session = Depends(get_db),
    _user: AppUser = Depends(get_current_user),
):
    """Rapport MITRE complet (stats + graph + heatmap + recommandations)."""
    return await mitre_service.generate_mitre_report(campaign_id, format=format, db=db)


@router.get("/campaign/{campaign_id}/events")
async def get_events(
    campaign_id: str,
    technique: Optional[str] = Query(None),
    tactic: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    _user: AppUser = Depends(get_current_user),
):
    """Liste les événements MITRE d'une campagne avec filtres optionnels."""
    q = db.query(MitreEvent).filter(MitreEvent.campaign_id == campaign_id)

    if technique:
        q = q.filter(MitreEvent.technique_id == technique)
    if tactic:
        q = q.filter(MitreEvent.tactic_id == tactic)

    events = q.order_by(MitreEvent.timestamp.desc()).limit(limit).all()

    return {
        "campaign_id": campaign_id,
        "total": len(events),
        "events": [
            {
                "event_id": e.event_id,
                "action_type": e.action_type,
                "technique_id": e.technique_id,
                "tactic_id": e.tactic_id,
                "score": e.score,
                "success": e.success,
                "details": e.details,
                "timestamp": e.timestamp.isoformat() if e.timestamp else None,
            }
            for e in events
        ],
    }


@router.get("/techniques")
async def list_techniques(
    _user: AppUser = Depends(get_current_user),
):
    """Liste toutes les techniques référencées dans ACTIONS_MAP."""
    techniques: dict[str, dict] = {}
    for action_type, mapping in ACTIONS_MAP.items():
        tid = mapping["technique"]
        if tid not in techniques:
            techniques[tid] = {
                "technique_id": tid,
                "tactic_id": mapping["tactic"],
                "score": mapping["score"],
                "actions": [],
            }
        techniques[tid]["actions"].append(action_type)

    return {
        "total": len(techniques),
        "techniques": sorted(techniques.values(), key=lambda t: t["technique_id"]),
    }


@router.get("/tactics")
async def list_tactics(
    _user: AppUser = Depends(get_current_user),
):
    """Liste toutes les tactiques MITRE ATT&CK."""
    tactics = [
        {
            "tactic_id": tac_id,
            "name": meta["name"],
            "phase": meta["phase"],
        }
        for tac_id, meta in TACTICS_MAP.items()
    ]
    return {"total": len(tactics), "tactics": tactics}


@router.post("/log")
async def manual_log(
    body: LogActionBody,
    db: Session = Depends(get_db),
    _user: AppUser = Depends(get_current_user),
):
    """Log manuel d'une action MITRE (sans passer par le middleware)."""
    if body.action_type not in ACTIONS_MAP:
        raise HTTPException(
            status_code=400,
            detail=f"Action inconnue: {body.action_type}. "
                   f"Actions disponibles: {list(ACTIONS_MAP.keys())}",
        )
    result = await mitre_service.log_action(
        body.campaign_id,
        body.action_type,
        details=body.details,
        db=db,
    )
    return result
