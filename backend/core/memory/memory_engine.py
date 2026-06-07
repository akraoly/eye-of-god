import re
import logging
from typing import List, Optional
from sqlalchemy.orm import Session
from core.memory.storage import memory_storage
from core.memory.vector_store import vector_store

logger = logging.getLogger(__name__)

_PATTERNS = [
    (r"je m[''`]appelle\s+(.+)", "nom"),
    (r"mon nom est\s+(.+)", "nom"),
    (r"j[''`]habite\s+(?:à|en|au)?\s*(.+)", "localisation"),
    (r"je travaille\s+(?:comme|en tant que)?\s*(.+)", "profession"),
    (r"mon projet\s+(?:principal\s+)?est\s+(.+)", "projet_principal"),
    (r"j[''`]aime\s+(.+)", "préférence"),
    (r"je préfère\s+(.+)", "préférence"),
    (r"rappelle-toi que\s+(.+)", "note"),
    (r"souviens-toi que\s+(.+)", "note"),
    (r"n[''`]oublie pas que\s+(.+)", "note"),
    (r"mon objectif est\s+(.+)", "objectif"),
]


class MemoryEngine:
    def extract_and_save(self, db: Session, message: str):
        lower = message.lower().strip()
        for pattern, key in _PATTERNS:
            m = re.search(pattern, lower)
            if m:
                value = m.group(m.lastindex).strip().rstrip(".,!?")
                if len(value) > 3:
                    mem = memory_storage.save_memory(
                        db=db,
                        memory_type="user",
                        key=key,
                        value=value,
                        importance=0.85,
                    )
                    # Indexer dans le vector store
                    vector_store.add(
                        text=f"{key}: {value}",
                        metadata={"type": "user", "key": key, "memory_id": mem.id},
                        doc_id=f"mem_{mem.id}",
                    )

    def save_exchange(
        self,
        db: Session,
        session_id: str,
        user_message: str,
        assistant_response: str,
        context_used: int = 0,
    ):
        memory_storage.save_conversation(
            db=db,
            session_id=session_id,
            user_message=user_message,
            assistant_response=assistant_response,
            context_used=context_used,
        )

    def get_relevant_memories(
        self, db: Session, query: Optional[str] = None, limit: int = 8
    ) -> List[dict]:
        """
        Si query fourni → recherche sémantique dans le vector store.
        Sinon → fallback sur les mémoires les plus importantes en DB.
        """
        from app.config import settings

        if query and vector_store.count() > 0:
            results = vector_store.search(query, k=settings.VECTOR_SEARCH_K)
            # Enrichir avec les données DB si dispo
            memories = []
            seen_ids = set()
            for r in results:
                mid = r["metadata"].get("memory_id")
                if mid and mid not in seen_ids:
                    seen_ids.add(mid)
                    memories.append({
                        "type": r["metadata"].get("type", "long"),
                        "key": r["metadata"].get("key", ""),
                        "value": r["text"],
                        "importance": r["score"],
                        "source": "semantic",
                    })
            if memories:
                return memories

        # Fallback DB
        mems = memory_storage.get_memories(db=db, limit=limit)
        return [
            {
                "type": m.memory_type,
                "key": m.key,
                "value": m.value,
                "importance": m.importance,
                "source": "db",
            }
            for m in mems
        ]

    def semantic_search(self, query: str, k: int = 5) -> List[dict]:
        """Recherche sémantique pure — pour l'endpoint /memory/search."""
        return vector_store.search(query, k=k)

    def get_user_profile(self, db: Session) -> dict:
        return memory_storage.get_profile(db=db)

    def track_vocal_usage(self, db: Session):
        """Enregistre que Mr Vitch utilise la voix — l'IA s'y adapte."""
        memory_storage.save_memory(
            db=db,
            memory_type="user",
            key="mode_interaction_préféré",
            value="vocal — Mr Vitch parle à voix haute à l'IA, réponses conversationnelles attendues",
            importance=0.95,
        )

    def learn_communication_style(self, db: Session, message: str):
        """Détecte et mémorise le style de communication de Mr Vitch."""
        words = len(message.split())
        is_technical = bool(re.search(
            r'\b(exploit|payload|ROP|shellcode|CVE|nmap|python|bash|gcc|kernel|heap|stack|overflow|pentest|reverse)\b',
            message, re.IGNORECASE
        ))
        is_command = words <= 6 and not message.endswith('?')
        is_question = message.strip().endswith('?')

        if is_technical and is_command:
            style = "commandes courtes techniques — Mr Vitch est direct, va à l'essentiel, expert"
        elif is_technical:
            style = "discussions techniques approfondies — Mr Vitch veut des détails d'expert"
        elif is_command:
            style = "ordres directs — Mr Vitch est concis, pas besoin de longueur"
        elif is_question:
            style = "questions ouvertes — Mr Vitch cherche à comprendre en profondeur"
        else:
            return

        memory_storage.save_memory(
            db=db,
            memory_type="user",
            key="style_communication",
            value=style,
            importance=0.80,
        )

    def index_existing_memories(self, db: Session):
        """Ré-indexe toutes les mémoires existantes dans le vector store (migration)."""
        mems = memory_storage.get_memories(db=db, limit=1000)
        indexed = 0
        for m in mems:
            vector_store.add(
                text=f"{m.key}: {m.value}",
                metadata={"type": m.memory_type, "key": m.key, "memory_id": m.id},
                doc_id=f"mem_{m.id}",
            )
            indexed += 1
        logger.info("MemoryEngine: %d mémoires ré-indexées dans le vector store", indexed)
        return indexed


memory_engine = MemoryEngine()
