import re
from typing import List
from sqlalchemy.orm import Session
from core.memory.storage import memory_storage

# Patterns pour extraire automatiquement les infos importantes
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
                    memory_storage.save_memory(
                        db=db,
                        memory_type="user",
                        key=key,
                        value=value,
                        importance=0.85,
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

    def get_relevant_memories(self, db: Session, limit: int = 15) -> List[dict]:
        mems = memory_storage.get_memories(db=db, limit=limit)
        return [
            {"type": m.memory_type, "key": m.key, "value": m.value, "importance": m.importance}
            for m in mems
        ]

    def get_user_profile(self, db: Session) -> dict:
        return memory_storage.get_profile(db=db)


memory_engine = MemoryEngine()
