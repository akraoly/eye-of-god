"""
LearningEngine — Pilier 2 : ingestion et recherche de connaissances.
Gère le stockage, la résumification et la recherche dans la base de connaissances.
"""
from __future__ import annotations

import json
import asyncio
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_, func

from database.models import KnowledgeEntry, LearningEvent


# Catégories valides pour la base de connaissances
VALID_CATEGORIES = [
    "ai", "cyber", "programmation", "sciences", "business",
    "utilisateur", "projets", "resumes", "general"
]


class LearningEngine:
    """Moteur d'apprentissage — ingestion de texte/URL, recherche sémantique."""

    # ── Ingestion de texte ────────────────────────────────────────────────────

    def ingest_text(
        self,
        db: Session,
        text: str,
        source: str = "manual",
        category: str = "general",
        title: str = "",
        tags: list = None,
        importance: float = 0.5,
    ) -> dict:
        """Ingère un texte, résume si nécessaire, et stocke dans KnowledgeEntry + LearningEvent."""
        try:
            if category not in VALID_CATEGORIES:
                category = "general"

            summary = self._summarize_sync(text) if len(text) > 500 else text
            title = title or self._extract_title(text)
            tags_str = json.dumps(tags or [], ensure_ascii=False)

            # Stocker dans KnowledgeEntry
            entry = KnowledgeEntry(
                title=title,
                content=text,
                summary=summary,
                category=category,
                source=source,
                tags=tags_str,
                importance=importance,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db.add(entry)
            db.flush()

            # Stocker dans LearningEvent
            event = LearningEvent(
                topic=title,
                source_url=source if source.startswith("http") else None,
                source_type="url" if source.startswith("http") else "text",
                summary=summary,
                content=text[:5000],
                tags=tags_str,
                importance=importance,
                learned_at=datetime.utcnow(),
            )
            db.add(event)
            db.commit()

            return {
                "success": True,
                "entry_id": entry.id,
                "title": title,
                "summary": summary[:300] if summary else "",
                "category": category,
                "chars": len(text),
            }
        except Exception as e:
            db.rollback()
            return {"success": False, "error": str(e)}

    def ingest_url(
        self,
        db: Session,
        url: str,
        category: str = "general",
        importance: float = 0.5,
    ) -> dict:
        """Récupère le contenu d'une URL, résume et stocke."""
        try:
            content = self._fetch_url(url)
            if not content:
                return {"success": False, "error": f"Impossible de récupérer l'URL: {url}"}

            return self.ingest_text(
                db=db,
                text=content,
                source=url,
                category=category,
                importance=importance,
            )
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ── Recherche ─────────────────────────────────────────────────────────────

    def search_knowledge(
        self,
        db: Session,
        query: str,
        category: Optional[str] = None,
        limit: int = 10,
    ) -> list:
        """Recherche full-text dans KnowledgeEntry par titre, contenu et résumé."""
        try:
            q = db.query(KnowledgeEntry)
            if category and category in VALID_CATEGORIES:
                q = q.filter(KnowledgeEntry.category == category)

            # Recherche par mots-clés dans titre et résumé et contenu
            keywords = query.lower().split()
            for kw in keywords[:5]:  # limiter à 5 mots-clés
                q = q.filter(
                    or_(
                        func.lower(KnowledgeEntry.title).contains(kw),
                        func.lower(KnowledgeEntry.summary).contains(kw),
                        func.lower(KnowledgeEntry.content).contains(kw),
                        func.lower(KnowledgeEntry.tags).contains(kw),
                    )
                )

            entries = q.order_by(
                KnowledgeEntry.importance.desc(),
                KnowledgeEntry.updated_at.desc(),
            ).limit(limit).all()

            return [self._entry_to_dict(e) for e in entries]
        except Exception as e:
            return []

    def list_knowledge(
        self,
        db: Session,
        category: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list:
        """Liste les entrées de connaissances."""
        try:
            q = db.query(KnowledgeEntry)
            if category and category in VALID_CATEGORIES:
                q = q.filter(KnowledgeEntry.category == category)
            entries = q.order_by(
                KnowledgeEntry.importance.desc(),
                KnowledgeEntry.created_at.desc(),
            ).offset(offset).limit(limit).all()
            return [self._entry_to_dict(e) for e in entries]
        except Exception:
            return []

    def get_entry(self, db: Session, entry_id: int) -> Optional[dict]:
        """Récupère une entrée par son ID."""
        try:
            entry = db.query(KnowledgeEntry).filter(KnowledgeEntry.id == entry_id).first()
            return self._entry_to_dict(entry) if entry else None
        except Exception:
            return None

    def delete_entry(self, db: Session, entry_id: int) -> dict:
        """Supprime une entrée."""
        try:
            entry = db.query(KnowledgeEntry).filter(KnowledgeEntry.id == entry_id).first()
            if not entry:
                return {"success": False, "error": "Entrée introuvable"}
            db.delete(entry)
            db.commit()
            return {"success": True, "deleted_id": entry_id}
        except Exception as e:
            db.rollback()
            return {"success": False, "error": str(e)}

    # ── Statistiques ──────────────────────────────────────────────────────────

    def get_learning_summary(self, db: Session) -> dict:
        """Statistiques : nombre d'entrées par catégorie, derniers apprentissages."""
        try:
            total = db.query(KnowledgeEntry).count()
            events_total = db.query(LearningEvent).count()

            # Par catégorie
            by_category = {}
            for cat in VALID_CATEGORIES:
                count = db.query(KnowledgeEntry).filter(
                    KnowledgeEntry.category == cat
                ).count()
                if count > 0:
                    by_category[cat] = count

            # Derniers apprentissages
            recent = db.query(LearningEvent).order_by(
                LearningEvent.learned_at.desc()
            ).limit(5).all()

            recent_list = [
                {
                    "topic": e.topic,
                    "source_type": e.source_type,
                    "learned_at": e.learned_at.isoformat() if e.learned_at else None,
                }
                for e in recent
            ]

            return {
                "total_entries": total,
                "total_events": events_total,
                "by_category": by_category,
                "recent_learning": recent_list,
                "categories_available": VALID_CATEGORIES,
            }
        except Exception as e:
            return {"error": str(e), "total_entries": 0}

    # ── Helpers privés ─────────────────────────────────────────────────────────

    def _summarize_sync(self, text: str) -> str:
        """Résumé via Claude — appelé en synchrone depuis le moteur."""
        try:
            # Import ici pour éviter les imports circulaires
            from core.llm.client import llm_client
            import asyncio

            async def _do_summarize():
                messages = [{"role": "user", "content": f"Résume ce texte en 3-5 phrases claires et factuelles :\n\n{text[:3000]}"}]
                return await llm_client.complete(
                    messages=messages,
                    system="Tu es un assistant de synthèse. Résume de façon concise et factuelle.",
                    max_tokens=500,
                )

            try:
                loop = asyncio.get_running_loop()
                # On est dans un contexte async, créer une tâche
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(asyncio.run, _do_summarize())
                    return future.result(timeout=30)
            except RuntimeError:
                # Pas de loop en cours
                return asyncio.run(_do_summarize())
        except Exception:
            # En cas d'échec, résumé simple par troncation
            lines = text.strip().split("\n")
            return " ".join(lines[:5])[:500]

    def _fetch_url(self, url: str) -> Optional[str]:
        """Récupère le contenu textuel d'une URL."""
        try:
            import urllib.request
            from html.parser import HTMLParser

            class TextExtractor(HTMLParser):
                def __init__(self):
                    super().__init__()
                    self.texts = []
                    self._skip = False

                def handle_starttag(self, tag, attrs):
                    if tag in ("script", "style", "nav", "footer"):
                        self._skip = True

                def handle_endtag(self, tag):
                    if tag in ("script", "style", "nav", "footer"):
                        self._skip = False

                def handle_data(self, data):
                    if not self._skip and data.strip():
                        self.texts.append(data.strip())

            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                html = resp.read().decode("utf-8", errors="replace")

            parser = TextExtractor()
            parser.feed(html)
            content = " ".join(parser.texts)
            return content[:10000] if content else None
        except Exception as e:
            return None

    def _extract_title(self, text: str) -> str:
        """Extrait un titre depuis les premières lignes du texte."""
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        if lines:
            return lines[0][:200]
        return text[:100]

    def _entry_to_dict(self, entry: KnowledgeEntry) -> dict:
        """Convertit une entrée SQLAlchemy en dict."""
        if not entry:
            return {}
        try:
            tags = json.loads(entry.tags) if entry.tags else []
        except Exception:
            tags = []
        return {
            "id": entry.id,
            "title": entry.title,
            "summary": entry.summary or "",
            "category": entry.category,
            "source": entry.source or "",
            "tags": tags,
            "importance": entry.importance,
            "created_at": entry.created_at.isoformat() if entry.created_at else None,
            "updated_at": entry.updated_at.isoformat() if entry.updated_at else None,
            "content_preview": (entry.content or "")[:300],
        }


learning_engine = LearningEngine()
