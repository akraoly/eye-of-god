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

_CRITICAL_KEYWORDS = [
    "ne jamais", "toujours", "impératif", "critique", "interdit",
    "obligatoire", "priorité absolue", "règle", "never", "always",
    "critical", "important", "remember",
]


def _detect_priority(message: str, key: str) -> str:
    lower = (message + " " + key).lower()
    if any(kw in lower for kw in _CRITICAL_KEYWORDS):
        return "critical"
    if any(w in lower for w in ["important", "essentiel", "fondamental", "key"]):
        return "important"
    return "normal"


class MemoryEngine:
    def extract_and_save(self, db: Session, message: str):
        lower = message.lower().strip()
        for pattern, key in _PATTERNS:
            m = re.search(pattern, lower)
            if m:
                value = m.group(m.lastindex).strip().rstrip(".,!?")
                if len(value) > 3:
                    priority = _detect_priority(message, key)
                    mem = memory_storage.save_memory(
                        db=db,
                        memory_type="user",
                        key=key,
                        value=value,
                        importance=0.85 if priority == "critical" else 0.75,
                        priority=priority,
                    )
                    vector_store.add(
                        text=f"{key}: {value}",
                        metadata={
                            "type": "user",
                            "key": key,
                            "memory_id": mem.id,
                            "priority": priority,
                        },
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

        # Auto-indexation de chaque échange dans ChromaDB
        try:
            from database.models import Conversation
            from datetime import datetime
            total = db.query(Conversation).filter(
                Conversation.session_id == session_id
            ).count()
            doc_id = f"conv_{session_id}_{total}"
            vector_store.add(
                text=f"[Q] {user_message}\n[A] {assistant_response[:500]}",
                metadata={
                    "type": "conversation",
                    "session_id": session_id,
                    "exchange": total,
                    "timestamp": datetime.utcnow().isoformat(),
                    "agent": "chat",
                },
                doc_id=doc_id,
            )
        except Exception as e:
            logger.debug("MemoryEngine: auto-index échange échoué: %s", e)

    def get_relevant_memories(
        self, db: Session, query: Optional[str] = None, limit: int = 10
    ) -> List[dict]:
        from app.config import settings

        memories = []
        seen_ids = set()

        # 1. Mémoires critiques — toujours injectées en premier
        try:
            critical = memory_storage.get_memories_by_priority(db=db, priority="critical", limit=5)
            for m in critical:
                mid = f"crit_{m.id}"
                if mid not in seen_ids:
                    seen_ids.add(mid)
                    memories.append({
                        "type": m.memory_type,
                        "key": m.key,
                        "value": m.value,
                        "importance": 1.0,
                        "priority": "critical",
                        "source": "critical",
                    })
        except Exception:
            pass

        # 2. Recherche sémantique dans ChromaDB
        if query and vector_store.count() > 0:
            results = vector_store.search(query, k=settings.VECTOR_SEARCH_K)
            for r in results:
                meta = r["metadata"]
                rid = r["id"]
                if rid not in seen_ids:
                    seen_ids.add(rid)
                    prio = meta.get("priority", "normal")
                    if prio == "archive":
                        continue
                    memories.append({
                        "type": meta.get("type", "long"),
                        "key": meta.get("key", ""),
                        "value": r["text"],
                        "importance": r["score"],
                        "priority": prio,
                        "source": "semantic",
                    })
            if memories:
                return memories[:limit]

        # 3. Fallback DB
        db_mems = memory_storage.get_memories(db=db, limit=limit)
        for m in db_mems:
            mid = f"db_{m.id}"
            if mid not in seen_ids:
                seen_ids.add(mid)
                prio = getattr(m, "priority", "normal") or "normal"
                if prio != "archive":
                    memories.append({
                        "type": m.memory_type,
                        "key": m.key,
                        "value": m.value,
                        "importance": m.importance,
                        "priority": prio,
                        "source": "db",
                    })

        return memories[:limit]

    def semantic_search(self, query: str, k: int = 5) -> List[dict]:
        return vector_store.search(query, k=k)

    def get_user_profile(self, db: Session) -> dict:
        return memory_storage.get_profile(db=db)

    def track_vocal_usage(self, db: Session):
        memory_storage.save_memory(
            db=db,
            memory_type="user",
            key="mode_interaction_préféré",
            value="vocal — Mr Vitch parle à voix haute à l'IA, réponses conversationnelles attendues",
            importance=0.95,
            priority="important",
        )

    def learn_communication_style(self, db: Session, message: str):
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
        mems = memory_storage.get_memories(db=db, limit=1000)
        indexed = 0
        for m in mems:
            vector_store.add(
                text=f"{m.key}: {m.value}",
                metadata={
                    "type": m.memory_type,
                    "key": m.key,
                    "memory_id": m.id,
                    "priority": getattr(m, "priority", "normal") or "normal",
                },
                doc_id=f"mem_{m.id}",
            )
            indexed += 1
        logger.info("MemoryEngine: %d mémoires ré-indexées dans le vector store", indexed)
        return indexed

    def save_critical_memory(self, db: Session, key: str, value: str):
        mem = memory_storage.save_memory(
            db=db,
            memory_type="user",
            key=key,
            value=value,
            importance=1.0,
            priority="critical",
        )
        vector_store.add(
            text=f"{key}: {value}",
            metadata={"type": "user", "key": key, "memory_id": mem.id, "priority": "critical"},
            doc_id=f"mem_{mem.id}",
        )
        return mem


memory_engine = MemoryEngine()
