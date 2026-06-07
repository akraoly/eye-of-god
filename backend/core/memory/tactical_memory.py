"""
TacticalMemoryEngine — mémoire persistante des opérations offensives.
Collection ChromaDB dédiée "operations" pour recherche sémantique.
À chaque nouvelle opération sur une cible connue → injecte le contexte historique.
"""
from __future__ import annotations

import json
import hashlib
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session


class TacticalMemoryEngine:
    """
    Indexe chaque opération de pentest dans ChromaDB (collection "operations").
    Permet de récupérer automatiquement le contexte historique pour une cible.
    """

    _collection = None
    _backend    = "keyword"

    def _get_collection(self):
        if self._collection is not None:
            return self._collection
        try:
            import chromadb
            from chromadb.config import Settings
            client = chromadb.PersistentClient(
                path="./data/chroma",
                settings=Settings(anonymized_telemetry=False),
            )
            self._collection = client.get_or_create_collection(
                name="operations",
                metadata={"hnsw:space": "cosine"},
            )
            self._backend = "chromadb"
        except Exception:
            self._collection = _FallbackKeywordStore()
            self._backend    = "keyword"
        return self._collection

    # ── Indexation ─────────────────────────────────────────────────────────────

    def index_operation(self, db: Session, summary: dict) -> str:
        """Indexe une opération dans ChromaDB et dans la table tactique."""
        target      = summary.get("target", "unknown")
        job_id      = summary.get("job_id", "")
        open_ports  = summary.get("open_ports", [])
        services    = summary.get("services", {})
        top_cves    = summary.get("top_cves", [])

        # ── Texte pour embedding ───────────────────────────────────────────────
        services_text = "; ".join(
            f"port {p}: {s.get('name', '')} {s.get('product', '')} {s.get('version', '')}"
            for p, s in services.items()
        )
        cves_text = "; ".join(f"{c['id']} CVSS {c.get('cvss', 0)}" for c in top_cves[:5])
        doc = (
            f"Opération pentest sur {target}. "
            f"Ports ouverts : {open_ports}. "
            f"Services : {services_text}. "
            f"Vulnérabilités : {cves_text}."
        )

        doc_id = f"op_{job_id}" if job_id else f"op_{hashlib.md5(doc.encode()).hexdigest()[:8]}"
        meta   = {
            "target":      target,
            "job_id":      job_id,
            "open_ports":  json.dumps(open_ports),
            "cves_count":  len(top_cves),
            "timestamp":   datetime.utcnow().isoformat(),
        }

        try:
            col = self._get_collection()
            col.upsert(documents=[doc], metadatas=[meta], ids=[doc_id])
        except Exception:
            pass

        # ── Persistance SQL ────────────────────────────────────────────────────
        try:
            from database.models import TacticalOperation
            op = TacticalOperation(
                job_id   = job_id,
                target   = target,
                ports    = json.dumps(open_ports),
                services = json.dumps(services, default=str),
                cves     = json.dumps(top_cves),
                summary  = json.dumps(summary, default=str),
            )
            db.add(op)
            db.commit()
        except Exception:
            pass

        return doc_id

    # ── Récupération contexte ──────────────────────────────────────────────────

    def get_target_history(self, target: str, k: int = 3) -> list[dict]:
        """Retourne les opérations passées sur la même cible (ou cibles similaires)."""
        try:
            col = self._get_collection()
            results = col.query(
                query_texts=[f"pentest {target}"],
                n_results=k,
            )
            docs   = results.get("documents", [[]])[0]
            metas  = results.get("metadatas", [[]])[0]
            scores = results.get("distances", [[]])[0]
            out = []
            for doc, meta, dist in zip(docs, metas, scores):
                out.append({
                    "target":    meta.get("target", ""),
                    "job_id":    meta.get("job_id", ""),
                    "timestamp": meta.get("timestamp", ""),
                    "summary":   doc,
                    "score":     round(1 - dist / 2, 3),
                })
            return out
        except Exception:
            return []

    def get_context_for_prompt(self, target: str) -> str:
        """
        Construit une section de prompt avec le contexte historique.
        Injecté dans system_context par l'orchestrateur pour chaque nouveau pentest.
        """
        history = self.get_target_history(target, k=3)
        if not history:
            return ""

        parts = [f"\n\n## MÉMOIRE TACTIQUE — {target}"]
        for i, op in enumerate(history, 1):
            parts.append(
                f"\n### Opération {i} ({op.get('timestamp', '')[:10]})\n"
                f"Cible : {op['target']} | Score similarité : {op['score']}\n"
                f"{op['summary'][:600]}\n"
            )
        parts.append("\nUtilise ce contexte pour améliorer l'analyse de la cible courante.")
        return "\n".join(parts)

    def search_operations(self, query: str, k: int = 5) -> list[dict]:
        """Recherche sémantique sur toutes les opérations."""
        return self.get_target_history(query, k=k)


# ── Fallback keyword store ─────────────────────────────────────────────────────

class _FallbackKeywordStore:
    def __init__(self):
        self._docs:  list[str]  = []
        self._metas: list[dict] = []
        self._ids:   list[str]  = []

    def upsert(self, documents, metadatas, ids):
        for doc, meta, doc_id in zip(documents, metadatas, ids):
            if doc_id in self._ids:
                idx = self._ids.index(doc_id)
                self._docs[idx]  = doc
                self._metas[idx] = meta
            else:
                self._docs.append(doc)
                self._metas.append(meta)
                self._ids.append(doc_id)

    def query(self, query_texts, n_results=5):
        q = query_texts[0].lower() if query_texts else ""
        scored = []
        for i, doc in enumerate(self._docs):
            score = sum(1 for w in q.split() if w in doc.lower())
            scored.append((score, i))
        scored.sort(reverse=True)
        top = scored[:n_results]
        return {
            "documents": [[self._docs[i] for _, i in top]],
            "metadatas": [[self._metas[i] for _, i in top]],
            "distances": [[1.0 - s * 0.1 for s, _ in top]],
        }


tactical_memory = TacticalMemoryEngine()
