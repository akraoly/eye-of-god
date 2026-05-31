"""
VectorStore — ChromaDB avec fallback keyword.
Interface stable : add() / search() / delete() / count()
"""
from __future__ import annotations

import re
import uuid
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def _try_chromadb(chroma_dir: str):
    """Retourne un client ChromaDB persistant ou None si indispo."""
    try:
        import chromadb
        client = chromadb.PersistentClient(path=chroma_dir)
        return client
    except Exception as e:
        logger.warning("ChromaDB indisponible, fallback keyword: %s", e)
        return None


class _ChromaBackend:
    """Backend ChromaDB avec embeddings sentence-transformers."""

    def __init__(self, chroma_dir: str):
        import chromadb
        self._client = chromadb.PersistentClient(path=chroma_dir)
        self._col = self._client.get_or_create_collection(
            name="memories",
            metadata={"hnsw:space": "cosine"},
        )
        self.backend = "chromadb"
        self.enabled = True

    def add(self, text: str, metadata: Optional[dict] = None, doc_id: Optional[str] = None) -> str:
        did = doc_id or str(uuid.uuid4())[:16]
        self._col.upsert(
            documents=[text],
            metadatas=[metadata or {}],
            ids=[did],
        )
        return did

    def search(self, query: str, k: int = 5) -> list[dict]:
        n = min(k, self._col.count())
        if n == 0:
            return []
        results = self._col.query(query_texts=[query], n_results=n)
        out = []
        docs = results["documents"][0]
        metas = results["metadatas"][0]
        distances = results["distances"][0]
        ids = results["ids"][0]
        for doc, meta, dist, did in zip(docs, metas, distances, ids):
            # cosine distance [0,2] → score [1,0]  (0 = identique)
            score = round(max(0.0, 1.0 - dist / 2.0), 4)
            out.append({"id": did, "text": doc, "score": score, "metadata": meta})
        return out

    def delete(self, doc_id: str) -> bool:
        try:
            self._col.delete(ids=[doc_id])
            return True
        except Exception:
            return False

    def count(self) -> int:
        return self._col.count()

    def clear(self):
        self._client.delete_collection("memories")
        self._col = self._client.get_or_create_collection(
            name="memories",
            metadata={"hnsw:space": "cosine"},
        )


class _KeywordBackend:
    """Fallback TF-Jaccard — aucune dépendance externe."""

    def __init__(self):
        self._docs: dict[str, dict] = {}
        self.backend = "keyword"
        self.enabled = True

    def add(self, text: str, metadata: Optional[dict] = None, doc_id: Optional[str] = None) -> str:
        did = doc_id or str(uuid.uuid4())[:8]
        self._docs[did] = {
            "text": text,
            "metadata": metadata or {},
            "tokens": self._tokenize(text),
        }
        return did

    def search(self, query: str, k: int = 5) -> list[dict]:
        if not self._docs:
            return []
        qt = self._tokenize(query)
        if not qt:
            return []
        scores = []
        for did, doc in self._docs.items():
            s = self._score(qt, doc["tokens"], doc["text"])
            if s > 0:
                scores.append((s, did))
        scores.sort(reverse=True)
        return [
            {
                "id": did,
                "text": self._docs[did]["text"],
                "score": round(s, 4),
                "metadata": self._docs[did]["metadata"],
            }
            for s, did in scores[:k]
        ]

    def delete(self, doc_id: str) -> bool:
        if doc_id in self._docs:
            del self._docs[doc_id]
            return True
        return False

    def count(self) -> int:
        return len(self._docs)

    def clear(self):
        self._docs.clear()

    _STOPWORDS = {
        "les", "des", "une", "est", "que", "qui", "pour", "dans",
        "avec", "sur", "par", "the", "and", "for", "are", "was",
    }

    def _tokenize(self, text: str) -> set[str]:
        words = re.findall(r"\b\w{3,}\b", text.lower())
        return {w for w in words if w not in self._STOPWORDS}

    def _score(self, qt: set, dt: set, text: str) -> float:
        inter = qt & dt
        if not inter:
            return 0.0
        jaccard = len(inter) / len(qt | dt)
        bonus = sum(
            0.1 for t in inter
            if re.search(rf"\b{re.escape(t)}\b", text, re.IGNORECASE)
        )
        return jaccard + min(bonus, 0.5)


class VectorStore:
    """Point d'entrée unique. Délègue à ChromaDB ou Keyword selon dispo."""

    def __init__(self):
        self._backend: _ChromaBackend | _KeywordBackend | None = None

    def _get(self) -> _ChromaBackend | _KeywordBackend:
        if self._backend is None:
            self._init()
        return self._backend  # type: ignore[return-value]

    def _init(self):
        from app.config import settings
        import os
        os.makedirs(settings.CHROMA_DIR, exist_ok=True)
        try:
            self._backend = _ChromaBackend(settings.CHROMA_DIR)
            logger.info("VectorStore: ChromaDB initialisé (%s)", settings.CHROMA_DIR)
        except Exception as e:
            logger.warning("VectorStore: ChromaDB KO (%s), mode keyword activé", e)
            self._backend = _KeywordBackend()

    @property
    def backend(self) -> str:
        return self._get().backend

    @property
    def enabled(self) -> bool:
        return True

    def add(self, text: str, metadata: Optional[dict] = None, doc_id: Optional[str] = None) -> str:
        return self._get().add(text, metadata, doc_id)

    def search(self, query: str, k: int = 5) -> list[dict]:
        return self._get().search(query, k)

    def delete(self, doc_id: str) -> bool:
        return self._get().delete(doc_id)

    def count(self) -> int:
        return self._get().count()

    def clear(self):
        self._get().clear()


vector_store = VectorStore()
