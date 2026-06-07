"""
Mémoire épisodique — gère les sessions de travail (début, suivi, fin + résumé).
Une session = ensemble d'échanges entre deux périodes d'inactivité > 1h.
Résumé généré par Claude stocké dans SQLite + ChromaDB.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session

try:
    from core.tools.logger import get_logger
    logger = get_logger("memory.episodic")
except Exception:
    logger = logging.getLogger(__name__)


class EpisodicMemory:

    def ensure_session(self, db: Session, session_id: str) -> "EpisodicSession":
        from database.models import EpisodicSession
        ep = db.query(EpisodicSession).filter(EpisodicSession.session_id == session_id).first()
        if not ep:
            ep = EpisodicSession(session_id=session_id)
            db.add(ep)
            db.commit()
            db.refresh(ep)
            logger.info("episodic: nouvelle session '%s'", session_id)
        return ep

    def record_exchange(self, db: Session, session_id: str, user_message: str,
                        assistant_response: str = ""):
        from database.models import EpisodicSession
        ep = self.ensure_session(db, session_id)
        ep.exchange_count = (ep.exchange_count or 0) + 1

        # Auto-indexation de l'échange dans ChromaDB avec métadonnées riches
        try:
            from core.memory.vector_store import vector_store
            doc_id = f"conv_{session_id}_{ep.exchange_count}"
            vector_store.add(
                text=f"[Q] {user_message}\n[A] {assistant_response[:500]}",
                metadata={
                    "type": "conversation",
                    "session_id": session_id,
                    "exchange": ep.exchange_count,
                    "timestamp": datetime.utcnow().isoformat(),
                    "agent": "chat",
                },
                doc_id=doc_id,
            )
        except Exception as e:
            logger.debug("episodic: auto-index conversation échoué: %s", e)

        db.commit()

    def update_goal(self, db: Session, session_id: str, goal: str):
        from database.models import EpisodicSession
        ep = self.ensure_session(db, session_id)
        if not ep.goal:
            ep.goal = goal[:500]
            db.commit()

    def add_file_touched(self, db: Session, session_id: str, filepath: str):
        from database.models import EpisodicSession
        ep = self.ensure_session(db, session_id)
        files = json.loads(ep.files_touched or "[]")
        if filepath not in files:
            files.append(filepath)
            ep.files_touched = json.dumps(files[-50:])
            db.commit()

    def add_key_command(self, db: Session, session_id: str, command: str):
        from database.models import EpisodicSession
        ep = self.ensure_session(db, session_id)
        cmds = json.loads(ep.key_commands or "[]")
        cmds.append(command)
        ep.key_commands = json.dumps(cmds[-30:])
        db.commit()

    async def summarize_and_close(self, db: Session, session_id: str) -> bool:
        """Génère un résumé structuré de la session via Claude → stocké en mémoire long terme."""
        from database.models import EpisodicSession, Conversation
        from core.llm.client import llm_client
        from core.memory.storage import memory_storage
        from core.memory.vector_store import vector_store

        ep = db.query(EpisodicSession).filter(EpisodicSession.session_id == session_id).first()
        if not ep or ep.is_summarized:
            return False

        # Récupérer les 20 derniers échanges de cette session
        convs = (
            db.query(Conversation)
            .filter(Conversation.session_id == session_id)
            .order_by(Conversation.timestamp.desc())
            .limit(20)
            .all()
        )
        if not convs:
            ep.is_summarized = True
            ep.ended_at = datetime.utcnow()
            db.commit()
            return False

        lines = []
        for c in reversed(convs):
            lines.append(f"User: {c.user_message[:300]}")
            lines.append(f"IA: {c.assistant_response[:300]}")

        context = "\n".join(lines)
        meta_parts = []
        if ep.goal:
            meta_parts.append(f"Objectif déclaré : {ep.goal}")
        if ep.files_touched:
            files = json.loads(ep.files_touched)
            if files:
                meta_parts.append(f"Fichiers touchés : {', '.join(files[:10])}")
        if ep.key_commands:
            cmds = json.loads(ep.key_commands)
            if cmds:
                meta_parts.append(f"Commandes clés : {', '.join(cmds[:10])}")

        meta = "\n".join(meta_parts)

        try:
            summary = await llm_client.complete(
                messages=[{
                    "role": "user",
                    "content": (
                        f"{meta}\n\n---\nÉchanges de la session :\n{context}"
                    ),
                }],
                system=(
                    "Tu es un système de mémoire épisodique. "
                    "Résume cette session de travail en 4-8 points clés : "
                    "ce qui a été accompli, les décisions prises, les problèmes résolus, "
                    "les fichiers/commandes importants, l'objectif atteint ou non. "
                    "Format : bullet points en français, concis et factuels."
                ),
                max_tokens=600,
            )
        except Exception as e:
            logger.error("episodic: erreur résumé Claude: %s", e)
            summary = f"Session {session_id} — {ep.exchange_count} échanges"

        ep.summary = summary
        ep.ended_at = datetime.utcnow()
        ep.is_summarized = True
        db.commit()

        # Stocker en mémoire long terme
        key = f"épisode_{session_id}_{ep.started_at.strftime('%Y%m%d_%H%M')}"
        mem = memory_storage.save_memory(
            db=db,
            memory_type="long",
            key=key,
            value=summary,
            importance=0.75,
        )

        # Indexer dans ChromaDB
        try:
            vector_store.add(
                text=f"[épisode] {key}: {summary}",
                metadata={
                    "type": "episodic",
                    "session_id": session_id,
                    "key": key,
                    "memory_id": mem.id,
                    "timestamp": ep.started_at.isoformat(),
                },
                doc_id=f"ep_{session_id}",
            )
        except Exception as e:
            logger.debug("episodic: indexation ChromaDB échouée: %s", e)

        logger.info("episodic: session '%s' résumée (%d échanges)", session_id, ep.exchange_count)
        return True

    def get_recent_episodes(self, db: Session, limit: int = 5) -> list[dict]:
        from database.models import EpisodicSession
        eps = (
            db.query(EpisodicSession)
            .filter(EpisodicSession.is_summarized == True)
            .order_by(EpisodicSession.ended_at.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "session_id": e.session_id,
                "started_at": e.started_at.isoformat() if e.started_at else None,
                "ended_at": e.ended_at.isoformat() if e.ended_at else None,
                "exchange_count": e.exchange_count,
                "goal": e.goal,
                "summary": e.summary,
            }
            for e in eps
        ]


episodic_memory = EpisodicMemory()
