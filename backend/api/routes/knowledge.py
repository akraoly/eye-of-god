"""
Routes /api/knowledge — Gestion de la base de connaissances.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional, List

from app.dependencies import get_db
from core.learning.learning_engine import learning_engine, VALID_CATEGORIES

router = APIRouter()


# ── Schémas ───────────────────────────────────────────────────────────────────

class IngestTextRequest(BaseModel):
    text: str = Field(..., min_length=1, description="Texte à ingérer")
    title: str = Field("", description="Titre optionnel")
    category: str = Field("general", description="Catégorie de connaissance")
    source: str = Field("manual", description="Source du texte")
    tags: List[str] = Field(default_factory=list)
    importance: float = Field(0.5, ge=0.0, le=1.0)


class IngestUrlRequest(BaseModel):
    url: str = Field(..., description="URL à ingérer")
    category: str = Field("general")
    importance: float = Field(0.5, ge=0.0, le=1.0)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/ingest")
async def ingest_text(body: IngestTextRequest, db: Session = Depends(get_db)):
    """Ingère un texte dans la base de connaissances."""
    if body.category not in VALID_CATEGORIES:
        body.category = "general"

    result = learning_engine.ingest_text(
        db=db,
        text=body.text,
        source=body.source,
        category=body.category,
        title=body.title,
        tags=body.tags,
        importance=body.importance,
    )
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "Erreur inconnue"))
    return result


@router.post("/ingest-url")
async def ingest_url(body: IngestUrlRequest, db: Session = Depends(get_db)):
    """Récupère une URL et ingère son contenu dans la base de connaissances."""
    if body.category not in VALID_CATEGORIES:
        body.category = "general"

    result = learning_engine.ingest_url(
        db=db,
        url=body.url,
        category=body.category,
        importance=body.importance,
    )
    if not result.get("success"):
        raise HTTPException(status_code=422, detail=result.get("error", "Impossible de récupérer l'URL"))
    return result


@router.get("/search")
async def search_knowledge(
    q: str = Query(..., description="Requête de recherche"),
    category: Optional[str] = Query(None, description="Filtrer par catégorie"),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """Recherche dans la base de connaissances."""
    if not q.strip():
        raise HTTPException(status_code=400, detail="La requête ne peut pas être vide.")
    results = learning_engine.search_knowledge(db=db, query=q, category=category, limit=limit)
    return {"query": q, "category": category, "results": results, "count": len(results)}


@router.get("/list")
async def list_knowledge(
    category: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Liste les entrées de connaissances."""
    entries = learning_engine.list_knowledge(db=db, category=category, limit=limit, offset=offset)
    return {"entries": entries, "count": len(entries), "offset": offset}


@router.get("/stats")
async def knowledge_stats(db: Session = Depends(get_db)):
    """Statistiques de la base de connaissances."""
    return learning_engine.get_learning_summary(db=db)


@router.get("/{entry_id}")
async def get_entry(entry_id: int, db: Session = Depends(get_db)):
    """Récupère une entrée par son ID."""
    entry = learning_engine.get_entry(db=db, entry_id=entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Entrée {entry_id} introuvable.")
    return entry


@router.delete("/{entry_id}")
async def delete_entry(entry_id: int, db: Session = Depends(get_db)):
    """Supprime une entrée de la base de connaissances."""
    result = learning_engine.delete_entry(db=db, entry_id=entry_id)
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("error", "Entrée introuvable"))
    return result


@router.get("/categories/list")
async def list_categories():
    """Liste les catégories disponibles."""
    return {"categories": VALID_CATEGORIES}
