"""
Middleware RAG — indexe automatiquement dans ChromaDB après chaque
- POST /api/chat (nouveau message)
- POST /api/knowledge (nouvel article)
"""
from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger(__name__)


async def _index_chat_session(session_id: str):
    """Indexe la session de chat dans ChromaDB (non bloquant)."""
    try:
        from database.db import SessionLocal
        from services.rag.indexer_service import rag_indexer
        db = SessionLocal()
        try:
            n = await rag_indexer.index_single_conversation(db, session_id)
            if n:
                logger.debug("RAG hook: %d chunks indexés pour session %s", n, session_id)
        finally:
            db.close()
    except Exception as e:
        logger.debug("RAG hook chat: %s", e)


async def _index_knowledge_article(article_id: int):
    """Indexe un article knowledge dans ChromaDB (non bloquant)."""
    try:
        from database.db import SessionLocal
        from services.rag.indexer_service import rag_indexer
        db = SessionLocal()
        try:
            n = await rag_indexer.index_single_knowledge(db, article_id)
            if n:
                logger.debug("RAG hook: %d chunks indexés pour article %d", n, article_id)
        finally:
            db.close()
    except Exception as e:
        logger.debug("RAG hook knowledge: %s", e)


def register_rag_hooks(app):
    """
    Enregistre les handlers post-requête pour l'indexation RAG.
    Appelé depuis lifecycle.startup().
    """
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.requests import Request

    class RAGMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):
            if request.scope.get("type") == "websocket":
                return await call_next(request)
            response = await call_next(request)

            # Index après POST /api/chat (non stream)
            if (
                request.method == "POST"
                and "/api/chat" in request.url.path
                and "/stream" not in request.url.path
                and response.status_code == 200
            ):
                try:
                    session_id = None
                    # Récupérer session_id depuis le body (déjà consommé)
                    # On passe par le path ou query param comme fallback
                    # Pour éviter de relire le body, on utilise un état partagé
                    session_id = getattr(request.state, "rag_session_id", None)
                    if session_id:
                        asyncio.create_task(_index_chat_session(session_id))
                except Exception:
                    pass

            # Index après POST /api/knowledge
            if (
                request.method == "POST"
                and "/api/knowledge" in request.url.path
                and response.status_code in (200, 201)
            ):
                try:
                    article_id = getattr(request.state, "rag_article_id", None)
                    if article_id:
                        asyncio.create_task(_index_knowledge_article(article_id))
                except Exception:
                    pass

            return response

    app.add_middleware(RAGMiddleware)
    logger.info("RAG middleware enregistré")
