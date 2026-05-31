"""
VectorStore — stub fonctionnel par recherche lexicale.
Interface stable : add() / search() / delete() identiques à ce que sera l'implémentation embeddings.
Remplacer uniquement l'intérieur de la classe (ChromaDB, FAISS…) sans toucher les appelants.
"""
from __future__ import annotations

import re
import uuid
from collections import defaultdict
from typing import Optional


class VectorStore:
    """
    Implémentation stub : score TF-IDF simplifié par mots-clés.
    Utilisable immédiatement, remplaçable par embeddings sans changer l'interface.
    """

    def __init__(self):
        # {doc_id: {"text": str, "metadata": dict, "tokens": set}}
        self._docs: dict[str, dict] = {}
        self.enabled = True
        self.backend = "keyword"   # "keyword" | "chromadb" | "faiss"

    # ── Interface publique stable ─────────────────────────────────────────

    def add(self, text: str, metadata: Optional[dict] = None) -> str:
        """Indexe un texte. Retourne son id."""
        doc_id = str(uuid.uuid4())[:8]
        self._docs[doc_id] = {
            "text": text,
            "metadata": metadata or {},
            "tokens": self._tokenize(text),
        }
        return doc_id

    def search(self, query: str, k: int = 5) -> list[dict]:
        """
        Retourne les k documents les plus pertinents.
        Format : [{"id", "text", "score", "metadata"}]
        """
        if not self._docs:
            return []

        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []

        scores: list[tuple[float, str]] = []
        for doc_id, doc in self._docs.items():
            score = self._score(query_tokens, doc["tokens"], doc["text"])
            if score > 0:
                scores.append((score, doc_id))

        scores.sort(reverse=True)
        results = []
        for score, doc_id in scores[:k]:
            doc = self._docs[doc_id]
            results.append({
                "id": doc_id,
                "text": doc["text"],
                "score": round(score, 4),
                "metadata": doc["metadata"],
            })
        return results

    def delete(self, doc_id: str) -> bool:
        if doc_id in self._docs:
            del self._docs[doc_id]
            return True
        return False

    def count(self) -> int:
        return len(self._docs)

    def clear(self):
        self._docs.clear()

    # ── Scoring lexical interne ───────────────────────────────────────────

    def _tokenize(self, text: str) -> set[str]:
        words = re.findall(r"\b\w{3,}\b", text.lower())
        stopwords = {"les", "des", "une", "est", "que", "qui", "pour", "dans",
                     "avec", "sur", "par", "the", "and", "for", "are", "was"}
        return {w for w in words if w not in stopwords}

    def _score(self, query_tokens: set, doc_tokens: set, doc_text: str) -> float:
        if not doc_tokens:
            return 0.0
        # Jaccard similarity pondérée par la longueur du document
        intersection = query_tokens & doc_tokens
        if not intersection:
            return 0.0
        jaccard = len(intersection) / len(query_tokens | doc_tokens)
        # Bonus si les mots apparaissent proches dans le texte (fenêtre de 50 chars)
        proximity_bonus = sum(
            0.1 for t in intersection
            if re.search(rf"\b{re.escape(t)}\b", doc_text, re.IGNORECASE)
        )
        return jaccard + min(proximity_bonus, 0.5)


vector_store = VectorStore()
