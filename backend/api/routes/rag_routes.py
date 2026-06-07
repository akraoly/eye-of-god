"""
Routes /api/rag — RAG Semantic Engine (ChromaDB).
"""
from __future__ import annotations

import asyncio
import uuid
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.auth.dependencies import get_current_user
from database.db import get_db
from services.rag.indexer_service import rag_indexer

router = APIRouter()

# In-memory task status store
_tasks: dict[str, dict] = {}


# ── Models ────────────────────────────────────────────────────────────────────

class QueryRequest(BaseModel):
    query: str
    collection: str = "conversations"
    n_results: int = 5


class ChatWithContextRequest(BaseModel):
    query: str
    collection: str = "all"
    n_results: int = 5
    session_id: str = "default"


# ── Background indexing jobs ──────────────────────────────────────────────────

async def _run_index_all(task_id: str, db: Session):
    _tasks[task_id]["status"] = "running"
    try:
        result = await rag_indexer.index_all(db)
        _tasks[task_id].update({
            "status": "completed",
            "result": result,
        })
    except Exception as e:
        _tasks[task_id].update({
            "status": "failed",
            "error": str(e),
        })
    finally:
        db.close()


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/index-all")
async def index_all(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Lance l'indexation complète en arrière-plan. Retourne un task_id."""
    task_id = str(uuid.uuid4())[:8]
    _tasks[task_id] = {
        "task_id": task_id,
        "status": "queued",
        "started_at": __import__("datetime").datetime.utcnow().isoformat(),
    }

    # Ouvrir une nouvelle session DB pour le background task
    from database.db import SessionLocal
    bg_db = SessionLocal()
    background_tasks.add_task(_run_index_all, task_id, bg_db)

    return {"task_id": task_id, "status": "queued"}


@router.get("/index-status/{task_id}")
def get_index_status(
    task_id: str,
    current_user=Depends(get_current_user),
):
    """Statut d'une tâche d'indexation."""
    task = _tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Tâche introuvable")
    return task


@router.get("/stats")
async def get_stats(current_user=Depends(get_current_user)):
    """Statistiques des collections ChromaDB."""
    return await rag_indexer.get_collection_stats()


@router.post("/query")
async def semantic_query(
    body: QueryRequest,
    current_user=Depends(get_current_user),
):
    """Recherche sémantique dans une collection ChromaDB."""
    if not body.query.strip():
        raise HTTPException(status_code=400, detail="Query vide")

    if body.collection == "all":
        results = []
        for col in ("conversations", "knowledge", "memories"):
            r = await rag_indexer.query_context(body.query, col, body.n_results)
            for item in r:
                item["collection"] = col
            results.extend(r)
        results.sort(key=lambda x: x["score"], reverse=True)
        return {"results": results[:body.n_results * 2], "query": body.query}

    results = await rag_indexer.query_context(body.query, body.collection, body.n_results)
    for item in results:
        item["collection"] = body.collection
    return {"results": results, "query": body.query, "collection": body.collection}


@router.post("/rebuild/{collection_name}")
async def rebuild_collection(
    collection_name: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Supprime et reconstruit une collection ChromaDB."""
    if collection_name not in ("conversations", "knowledge", "memories", "all"):
        raise HTTPException(status_code=400, detail="Collection invalide")

    if collection_name == "all":
        result = await rag_indexer.index_all(db)
        return {"message": "Toutes les collections reconstruites", "result": result}

    ok = await rag_indexer.rebuild_collection(collection_name, db)
    if not ok:
        raise HTTPException(status_code=500, detail="Rebuild échoué")
    return {"message": f"Collection '{collection_name}' reconstruite"}


@router.post("/chat-with-context")
async def chat_with_rag_context(
    body: ChatWithContextRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Chat enrichi par le contexte RAG : query → ChromaDB → contexte → LLM → réponse."""
    from core.llm.client import llm_client

    collection = body.collection if body.collection != "all" else "conversations"
    context_docs = await rag_indexer.query_context(body.query, collection, body.n_results)

    context_str = ""
    if context_docs:
        context_str = "\n\n## Contexte retrouvé par recherche sémantique (RAG)\n"
        for i, doc in enumerate(context_docs, 1):
            meta = doc.get("metadata", {})
            source_info = meta.get("title", meta.get("session_id", ""))
            context_str += f"\n### Source {i} (score: {doc['score']:.2f}) — {source_info}\n"
            context_str += doc["text"][:600] + "\n"

    system = (
        "Tu es L'Œil de Dieu, un assistant IA ultra-avancé. "
        "Réponds à la question de l'utilisateur en t'appuyant sur le contexte fourni ci-dessous. "
        "Si le contexte est pertinent, cite les informations importantes."
        + context_str
    )

    messages = [{"role": "user", "content": body.query}]
    response = await llm_client.complete(messages=messages, system=system, max_tokens=1024)

    return {
        "response": response,
        "query": body.query,
        "context_used": len(context_docs),
        "sources": [
            {
                "score": d["score"],
                "source": d.get("metadata", {}).get("source", ""),
                "preview": d["text"][:150],
            }
            for d in context_docs
        ],
    }
