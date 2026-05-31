from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from services.memory_service import memory_service
from database.db import get_db
from core.memory.memory_engine import memory_engine
from core.memory.vector_store import vector_store

router = APIRouter()


class MemorySaveRequest(BaseModel):
    memory_type: str = "user"
    key: str
    value: str
    importance: float = 0.5


class ProfileUpdateRequest(BaseModel):
    field: str
    value: str


@router.post("/save")
async def save_memory(request: MemorySaveRequest, db: Session = Depends(get_db)):
    return memory_service.save(
        db=db,
        memory_type=request.memory_type,
        key=request.key,
        value=request.value,
        importance=request.importance,
    )


@router.get("/get")
async def get_memories(
    memory_type: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    return memory_service.list(db=db, memory_type=memory_type, limit=limit)


@router.delete("/{memory_id}")
async def delete_memory(memory_id: int, db: Session = Depends(get_db)):
    if not memory_service.delete(db=db, memory_id=memory_id):
        raise HTTPException(status_code=404, detail="Mémoire introuvable")
    return {"message": "Mémoire supprimée"}


@router.get("/profile")
async def get_profile(db: Session = Depends(get_db)):
    return memory_service.get_profile(db=db)


@router.post("/profile")
async def update_profile(request: ProfileUpdateRequest, db: Session = Depends(get_db)):
    return memory_service.update_profile(db=db, field=request.field, value=request.value)


@router.get("/search")
async def semantic_search(
    q: str = Query(..., min_length=2, description="Requête de recherche sémantique"),
    k: int = Query(5, ge=1, le=20),
):
    results = memory_engine.semantic_search(query=q, k=k)
    return {
        "query": q,
        "results": results,
        "count": len(results),
        "backend": vector_store.backend,
    }


@router.post("/reindex")
async def reindex_memories(db: Session = Depends(get_db)):
    """Ré-indexe toutes les mémoires existantes dans le vector store."""
    count = memory_engine.index_existing_memories(db=db)
    return {"indexed": count, "backend": vector_store.backend}


@router.get("/vector/stats")
async def vector_stats():
    return {
        "backend": vector_store.backend,
        "total_documents": vector_store.count(),
        "enabled": vector_store.enabled,
    }
