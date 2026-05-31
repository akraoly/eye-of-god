"""
Résumé automatique — compresse les vieux échanges en mémoires long terme.
Déclenché par MemoryEngine quand le nombre d'échanges dépasse SUMMARY_THRESHOLD.
"""
from __future__ import annotations

import logging
from sqlalchemy.orm import Session
from database.models import Conversation, Memory
from datetime import datetime

logger = logging.getLogger(__name__)


class ConversationSummarizer:
    async def summarize_if_needed(self, db: Session) -> bool:
        """
        Si le nombre total de conversations dépasse le seuil, résume les plus
        anciennes non encore résumées et les compresse en une mémoire long terme.
        Retourne True si un résumé a été effectué.
        """
        from app.config import settings
        from core.llm.client import llm_client
        from core.memory.vector_store import vector_store

        total = db.query(Conversation).count()
        if total < settings.SUMMARY_THRESHOLD:
            return False

        # Prendre les plus vieux échanges non résumés
        old = (
            db.query(Conversation)
            .filter(Conversation.context_used != -1)  # -1 = déjà résumé
            .order_by(Conversation.timestamp.asc())
            .limit(settings.SUMMARY_BATCH)
            .all()
        )
        if not old:
            return False

        # Construire le texte à résumer
        lines = []
        for c in old:
            lines.append(f"User: {c.user_message}")
            lines.append(f"Assistant: {c.assistant_response}")
        text = "\n".join(lines)

        try:
            summary = await llm_client.complete(
                messages=[{"role": "user", "content": text}],
                system=(
                    "Tu es un assistant de synthèse. "
                    "Résume les échanges suivants en 3 à 6 points clés, "
                    "en gardant les informations importantes sur l'utilisateur, "
                    "ses projets, préférences et décisions. "
                    "Sois concis et factuel. Réponse en français."
                ),
                max_tokens=512,
            )
        except Exception as e:
            logger.error("Summarizer: erreur Claude: %s", e)
            return False

        # Sauvegarder comme mémoire long terme
        key = f"résumé_{old[0].timestamp.strftime('%Y%m%d_%H%M')}"
        mem = Memory(
            memory_type="long",
            key=key,
            value=summary,
            importance=0.7,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(mem)

        # Marquer les échanges comme résumés (context_used = -1)
        for c in old:
            c.context_used = -1
        db.commit()
        db.refresh(mem)

        # Indexer le résumé dans le vector store
        vector_store.add(
            text=f"{key}: {summary}",
            metadata={"type": "long", "key": key, "memory_id": mem.id},
            doc_id=f"mem_{mem.id}",
        )

        logger.info("Summarizer: %d échanges résumés → mémoire '%s'", len(old), key)
        return True


summarizer = ConversationSummarizer()
