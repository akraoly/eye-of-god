"""
Routes /api/observe — Auto-observation et introspection du système.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.dependencies import get_db
from core.self.self_observer import self_observer

router = APIRouter()


@router.get("/report")
async def get_report(
    days: int = Query(7, ge=1, le=90, description="Période d'analyse en jours"),
    db: Session = Depends(get_db),
):
    """Rapport d'auto-observation formaté."""
    report_text = self_observer.generate_report(db=db)
    analysis = self_observer.analyze(db=db, days=days)
    return {
        "report": report_text,
        "healthy": analysis.get("healthy", []),
        "issues": analysis.get("issues", []),
        "suggestions": analysis.get("suggestions", []),
        "stats": analysis.get("stats", {}),
    }


@router.get("/stats")
async def get_stats(db: Session = Depends(get_db)):
    """Statistiques globales toutes périodes confondues."""
    return self_observer.get_global_stats(db=db)


@router.get("/actions")
async def get_recent_actions(
    limit: int = Query(50, ge=1, le=500, description="Nombre d'actions à retourner"),
    db: Session = Depends(get_db),
):
    """Dernières actions journalisées."""
    actions = self_observer.get_recent_actions(db=db, limit=limit)
    return {"actions": actions, "count": len(actions)}


@router.get("/analysis")
async def get_analysis(
    days: int = Query(7, ge=1, le=90),
    db: Session = Depends(get_db),
):
    """Analyse brute des logs (healthy/issues/suggestions + stats)."""
    return self_observer.analyze(db=db, days=days)
