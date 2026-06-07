from typing import List, Optional
from core.llm.prompts import build_system_prompt
from app.config import settings
import logging

logger = logging.getLogger(__name__)

# Tours (user+assistant) chargés depuis la DB au démarrage de session
HISTORY_TURNS = 15


class ContextBuilder:
    def __init__(self):
        self._sessions: dict[str, list] = {}

    def get_session(self, session_id: str) -> list:
        return self._sessions.setdefault(session_id, [])

    def add_message(self, session_id: str, role: str, content: str):
        session = self.get_session(session_id)
        session.append({"role": role, "content": content})
        limit = settings.SHORT_TERM_LIMIT * 2
        if len(session) > limit:
            self._sessions[session_id] = session[-limit:]

    def warm_from_db(self, db, session_id: str) -> int:
        """
        Pré-charge l'historique depuis la DB si le cache RAM est vide.
        Appelé au début de chaque requête /chat.
        Retourne le nombre de messages chargés.
        """
        if self._sessions.get(session_id):
            return 0  # cache déjà chaud, rien à faire

        try:
            from core.memory.storage import memory_storage
            convs = memory_storage.get_recent_conversations(db, session_id, HISTORY_TURNS)
            if not convs:
                return 0

            messages = []
            for conv in reversed(convs):          # ordre chronologique (le plus ancien en premier)
                messages.append({"role": "user",     "content": conv.user_message})
                messages.append({"role": "assistant", "content": conv.assistant_response})

            self._sessions[session_id] = messages
            logger.info(f"[CTX] {session_id[:8]}… → {len(messages)} msgs rechargés depuis DB")
            return len(messages)
        except Exception as e:
            logger.warning(f"[CTX] Chargement historique échoué : {e}")
            return 0

    def build_messages(self, session_id: str, new_message: str, max_turns: int = 12) -> List[dict]:
        session = self.get_session(session_id)
        # Limiter l'historique envoyé à Claude (max_turns paires user/assistant)
        messages = list(session[-(max_turns * 2):])
        messages.append({"role": "user", "content": new_message})
        return messages

    def build_system(
        self,
        user_memories: Optional[list] = None,
        user_profile: Optional[dict] = None,
    ) -> str:
        return build_system_prompt(user_memories=user_memories, user_profile=user_profile)

    def clear_session(self, session_id: str):
        self._sessions.pop(session_id, None)

    def list_sessions(self) -> list:
        return list(self._sessions.keys())


context_builder = ContextBuilder()
