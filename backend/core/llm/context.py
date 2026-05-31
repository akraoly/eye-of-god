from typing import List, Optional
from core.llm.prompts import build_system_prompt
from app.config import settings


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

    def build_messages(self, session_id: str, new_message: str) -> List[dict]:
        messages = list(self.get_session(session_id))
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
