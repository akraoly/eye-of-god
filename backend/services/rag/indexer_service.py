"""
RAGIndexerService — Peuple ChromaDB avec les données existantes.

Collections :
  - conversations  : échanges episodic_sessions
  - knowledge      : articles de la knowledge base
  - memories       : souvenirs persistants
"""
from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Taille des chunks (caractères)
CONV_CHUNK = 2000
CONV_OVERLAP = 200
KNOW_CHUNK = 3000
KNOW_OVERLAP = 300


def _chunk_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    """Découpe un texte en chunks avec overlap."""
    if not text or len(text) <= chunk_size:
        return [text] if text else []
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append(text[start:end])
        if end == len(text):
            break
        start += chunk_size - overlap
    return chunks


def _stable_id(prefix: str, source_id: str | int, idx: int = 0) -> str:
    raw = f"{prefix}:{source_id}:{idx}"
    return hashlib.md5(raw.encode()).hexdigest()[:16]


class RAGIndexerService:
    """Indexation sémantique dans ChromaDB via VectorStore."""

    def __init__(self):
        self._chroma_dir = "./data/chroma"

    def _get_chroma(self):
        import chromadb
        Path(self._chroma_dir).mkdir(parents=True, exist_ok=True)
        return chromadb.PersistentClient(path=self._chroma_dir)

    def _get_collection(self, name: str):
        client = self._get_chroma()
        return client.get_or_create_collection(
            name=name,
            metadata={"hnsw:space": "cosine"},
        )

    # ── Indexation complète ───────────────────────────────────────────────────

    async def index_all(self, db: Session) -> dict:
        errors = []
        conv_count = 0
        know_count = 0
        mem_count = 0

        try:
            conv_count = await self.index_conversations(db)
        except Exception as e:
            errors.append(f"conversations: {e}")
            logger.error("RAG index_all conversations: %s", e)

        try:
            know_count = await self.index_knowledge(db)
        except Exception as e:
            errors.append(f"knowledge: {e}")
            logger.error("RAG index_all knowledge: %s", e)

        try:
            mem_count = await self.index_memories(db)
        except Exception as e:
            errors.append(f"memories: {e}")
            logger.error("RAG index_all memories: %s", e)

        total = conv_count + know_count + mem_count
        return {
            "total_chunks": total,
            "conversations": conv_count,
            "knowledge": know_count,
            "memories": mem_count,
            "errors": errors,
            "status": "completed" if not errors else "partial",
        }

    # ── Conversations ─────────────────────────────────────────────────────────

    async def index_conversations(self, db: Session, limit: int = 1000) -> int:
        from database.models import EpisodicSession, Conversation

        col = self._get_collection("conversations")
        indexed = 0
        batch_size = 50

        sessions = db.query(EpisodicSession).order_by(
            EpisodicSession.started_at.desc()
        ).limit(limit).all()

        docs_batch, metas_batch, ids_batch = [], [], []

        for session in sessions:
            convs = db.query(Conversation).filter(
                Conversation.session_id == session.session_id
            ).order_by(Conversation.timestamp).all()

            full_text = ""
            for conv in convs:
                full_text += f"User: {conv.user_message}\nAssistant: {conv.assistant_response}\n\n"

            if not full_text.strip():
                continue

            chunks = _chunk_text(full_text, CONV_CHUNK, CONV_OVERLAP)
            for i, chunk in enumerate(chunks):
                doc_id = _stable_id("conv", session.session_id, i)
                meta = {
                    "session_id": session.session_id,
                    "date": session.started_at.isoformat() if session.started_at else "",
                    "exchange_count": session.exchange_count or 0,
                    "summary": (session.summary or "")[:200],
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                    "source": "conversation",
                }
                docs_batch.append(chunk)
                metas_batch.append(meta)
                ids_batch.append(doc_id)

                if len(docs_batch) >= batch_size:
                    col.upsert(documents=docs_batch, metadatas=metas_batch, ids=ids_batch)
                    indexed += len(docs_batch)
                    docs_batch, metas_batch, ids_batch = [], [], []

        if docs_batch:
            col.upsert(documents=docs_batch, metadatas=metas_batch, ids=ids_batch)
            indexed += len(docs_batch)

        logger.info("RAG: %d chunks conversations indexés", indexed)
        return indexed

    # ── Knowledge ─────────────────────────────────────────────────────────────

    async def index_knowledge(self, db: Session) -> int:
        from database.models import KnowledgeEntry

        col = self._get_collection("knowledge")
        indexed = 0
        docs_batch, metas_batch, ids_batch = [], [], []

        articles = db.query(KnowledgeEntry).all()
        for article in articles:
            text = f"{article.title or ''}\n\n{article.content or ''}"
            if not text.strip():
                continue

            chunks = _chunk_text(text, KNOW_CHUNK, KNOW_OVERLAP)
            for i, chunk in enumerate(chunks):
                doc_id = _stable_id("know", article.id, i)
                meta = {
                    "article_id": str(article.id),
                    "title": article.title or "",
                    "category": article.category or "",
                    "tags": article.tags or "",
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                    "source": "knowledge",
                }
                docs_batch.append(chunk)
                metas_batch.append(meta)
                ids_batch.append(doc_id)

        if docs_batch:
            col.upsert(documents=docs_batch, metadatas=metas_batch, ids=ids_batch)
            indexed = len(docs_batch)

        logger.info("RAG: %d chunks knowledge indexés", indexed)
        return indexed

    # ── Memories ──────────────────────────────────────────────────────────────

    async def index_memories(self, db: Session) -> int:
        from database.models import Memory

        col = self._get_collection("memories")
        docs_batch, metas_batch, ids_batch = [], [], []

        memories = db.query(Memory).all()
        for mem in memories:
            text = f"{mem.key}: {mem.value}"
            if not text.strip():
                continue
            doc_id = _stable_id("mem", mem.id)
            meta = {
                "memory_id": str(mem.id),
                "memory_type": mem.memory_type or "",
                "key": mem.key or "",
                "importance": float(mem.importance or 0.5),
                "priority": mem.priority or "normal",
                "source": "memory",
            }
            docs_batch.append(text)
            metas_batch.append(meta)
            ids_batch.append(doc_id)

        if docs_batch:
            col.upsert(documents=docs_batch, metadatas=metas_batch, ids=ids_batch)

        logger.info("RAG: %d souvenirs indexés", len(docs_batch))
        return len(docs_batch)

    # ── Index single items (hook temps réel) ─────────────────────────────────

    async def index_single_conversation(self, db: Session, session_id: str) -> int:
        from database.models import Conversation, EpisodicSession

        col = self._get_collection("conversations")
        convs = db.query(Conversation).filter(
            Conversation.session_id == session_id
        ).order_by(Conversation.timestamp).all()

        if not convs:
            return 0

        full_text = ""
        for conv in convs:
            full_text += f"User: {conv.user_message}\nAssistant: {conv.assistant_response}\n\n"

        session = db.query(EpisodicSession).filter(
            EpisodicSession.session_id == session_id
        ).first()

        chunks = _chunk_text(full_text, CONV_CHUNK, CONV_OVERLAP)
        docs, metas, ids = [], [], []
        for i, chunk in enumerate(chunks):
            doc_id = _stable_id("conv", session_id, i)
            meta = {
                "session_id": session_id,
                "date": datetime.utcnow().isoformat(),
                "exchange_count": len(convs),
                "summary": (session.summary if session and session.summary else "")[:200],
                "chunk_index": i,
                "total_chunks": len(chunks),
                "source": "conversation",
            }
            docs.append(chunk)
            metas.append(meta)
            ids.append(doc_id)

        if docs:
            col.upsert(documents=docs, metadatas=metas, ids=ids)

        return len(docs)

    async def index_single_knowledge(self, db: Session, article_id: int) -> int:
        from database.models import KnowledgeEntry

        article = db.query(KnowledgeEntry).filter(KnowledgeEntry.id == article_id).first()
        if not article:
            return 0

        col = self._get_collection("knowledge")
        text = f"{article.title or ''}\n\n{article.content or ''}"
        chunks = _chunk_text(text, KNOW_CHUNK, KNOW_OVERLAP)
        docs, metas, ids = [], [], []
        for i, chunk in enumerate(chunks):
            doc_id = _stable_id("know", article.id, i)
            meta = {
                "article_id": str(article.id),
                "title": article.title or "",
                "category": article.category or "",
                "tags": article.tags or "",
                "chunk_index": i,
                "total_chunks": len(chunks),
                "source": "knowledge",
            }
            docs.append(chunk)
            metas.append(meta)
            ids.append(doc_id)

        if docs:
            col.upsert(documents=docs, metadatas=metas, ids=ids)

        return len(docs)

    # ── Rebuild ───────────────────────────────────────────────────────────────

    async def rebuild_collection(self, collection_name: str, db: Optional[Session] = None) -> bool:
        try:
            client = self._get_chroma()
            try:
                client.delete_collection(collection_name)
            except Exception:
                pass

            if db is None:
                return True

            if collection_name == "conversations":
                await self.index_conversations(db)
            elif collection_name == "knowledge":
                await self.index_knowledge(db)
            elif collection_name == "memories":
                await self.index_memories(db)
            return True
        except Exception as e:
            logger.error("RAG rebuild_collection %s: %s", collection_name, e)
            return False

    # ── Stats ─────────────────────────────────────────────────────────────────

    async def get_collection_stats(self) -> dict:
        try:
            client = self._get_chroma()
            stats = {}
            total = 0
            for name in ("conversations", "knowledge", "memories"):
                try:
                    col = client.get_collection(name)
                    count = col.count()
                    stats[name] = count
                    total += count
                except Exception:
                    stats[name] = 0

            chroma_path = Path(self._chroma_dir)
            disk_mb = 0.0
            if chroma_path.exists():
                disk_mb = round(
                    sum(f.stat().st_size for f in chroma_path.rglob("*") if f.is_file()) / 1e6,
                    2,
                )

            return {
                "conversations": stats.get("conversations", 0),
                "knowledge": stats.get("knowledge", 0),
                "memories": stats.get("memories", 0),
                "total_vectors": total,
                "disk_mb": disk_mb,
                "backend": "chromadb",
            }
        except Exception as e:
            logger.error("RAG get_collection_stats: %s", e)
            return {
                "conversations": 0, "knowledge": 0, "memories": 0,
                "total_vectors": 0, "disk_mb": 0.0,
                "backend": "unavailable", "error": str(e),
            }

    # ── Semantic Query ────────────────────────────────────────────────────────

    async def query_context(
        self,
        query: str,
        collection: str = "conversations",
        n_results: int = 5,
    ) -> list[dict]:
        try:
            col = self._get_collection(collection)
            n = min(n_results, col.count())
            if n == 0:
                return []
            results = col.query(query_texts=[query], n_results=n)
            out = []
            for doc, meta, dist, doc_id in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0],
                results["ids"][0],
            ):
                score = round(max(0.0, 1.0 - dist / 2.0), 4)
                out.append({
                    "id": doc_id,
                    "text": doc,
                    "metadata": meta,
                    "score": score,
                    "distance": round(dist, 4),
                })
            return out
        except Exception as e:
            logger.error("RAG query_context: %s", e)
            return []


rag_indexer = RAGIndexerService()
