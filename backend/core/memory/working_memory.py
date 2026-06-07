"""
Mémoire de travail courte durée — par session, in-memory.
Stocke : objectif de session, 20 dernières commandes, fichiers ouverts,
dernier timestamp d'activité (pour détecter la fin de session).
"""
from __future__ import annotations

import json
import re
import logging
from datetime import datetime, timedelta
from collections import deque
from typing import Optional

logger = logging.getLogger(__name__)

SESSION_TIMEOUT_MINUTES = 60
MAX_RECENT_COMMANDS = 20
MAX_OPEN_FILES = 30

_FILE_PATTERN = re.compile(
    r"(?:ouvre|lis|modifie|édite|créé|crée|affiche|regarde|analyse|check)\s+"
    r"([/~]\S+\.\w+|[\w.-]+\.\w{2,5})",
    re.IGNORECASE,
)
_GOAL_KEYWORDS = [
    "je veux", "j'ai besoin", "mon objectif", "mon but", "je cherche",
    "aide-moi à", "help me", "i want", "i need",
]


class _SessionState:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.goal: Optional[str] = None
        self.recent_commands: deque[str] = deque(maxlen=MAX_RECENT_COMMANDS)
        self.open_files: list[str] = []
        self.exchange_count: int = 0
        self.started_at: datetime = datetime.utcnow()
        self.last_activity: datetime = datetime.utcnow()
        self.topics: list[str] = []

    def is_timed_out(self) -> bool:
        return datetime.utcnow() - self.last_activity > timedelta(minutes=SESSION_TIMEOUT_MINUTES)

    def touch(self):
        self.last_activity = datetime.utcnow()

    def to_context_string(self) -> str:
        parts = []
        if self.goal:
            parts.append(f"Objectif de session : {self.goal}")
        if self.open_files:
            parts.append(f"Fichiers actifs : {', '.join(self.open_files[-5:])}")
        if self.recent_commands:
            cmds = list(self.recent_commands)[-5:]
            parts.append(f"Commandes récentes : {' | '.join(cmds)}")
        if self.topics:
            parts.append(f"Sujets abordés : {', '.join(self.topics[-5:])}")
        return "\n".join(parts)


class WorkingMemory:
    """Registre de mémoire courte durée — une entrée par session_id."""

    def __init__(self):
        self._sessions: dict[str, _SessionState] = {}

    def _get(self, session_id: str) -> _SessionState:
        if session_id not in self._sessions:
            self._sessions[session_id] = _SessionState(session_id)
        return self._sessions[session_id]

    def update(self, session_id: str, user_message: str, assistant_response: str = ""):
        s = self._get(session_id)
        s.exchange_count += 1
        s.touch()

        # Extraire l'objectif depuis le premier message (si pas encore défini)
        if not s.goal:
            lower = user_message.lower()
            for kw in _GOAL_KEYWORDS:
                if kw in lower:
                    idx = lower.find(kw)
                    s.goal = user_message[idx:idx+200].strip()
                    break

        # Extraire les fichiers mentionnés
        for m in _FILE_PATTERN.finditer(user_message):
            fpath = m.group(1)
            if fpath not in s.open_files:
                s.open_files.append(fpath)
                if len(s.open_files) > MAX_OPEN_FILES:
                    s.open_files.pop(0)

    def add_command(self, session_id: str, command: str):
        self._get(session_id).recent_commands.append(command)
        self._get(session_id).touch()

    def set_goal(self, session_id: str, goal: str):
        self._get(session_id).goal = goal

    def add_topic(self, session_id: str, topic: str):
        s = self._get(session_id)
        if topic not in s.topics:
            s.topics.append(topic)

    def get_context_string(self, session_id: str) -> str:
        if session_id not in self._sessions:
            return ""
        return self._sessions[session_id].to_context_string()

    def get_state(self, session_id: str) -> Optional[dict]:
        if session_id not in self._sessions:
            return None
        s = self._sessions[session_id]
        return {
            "session_id": session_id,
            "goal": s.goal,
            "exchange_count": s.exchange_count,
            "open_files": s.open_files,
            "recent_commands": list(s.recent_commands),
            "topics": s.topics,
            "started_at": s.started_at.isoformat(),
            "last_activity": s.last_activity.isoformat(),
            "timed_out": s.is_timed_out(),
        }

    def get_timed_out_sessions(self) -> list[str]:
        return [sid for sid, s in self._sessions.items() if s.is_timed_out()]

    def close_session(self, session_id: str):
        self._sessions.pop(session_id, None)

    def get_all_recent_commands(self) -> list[str]:
        cmds = []
        for s in self._sessions.values():
            cmds.extend(list(s.recent_commands))
        return cmds[-MAX_RECENT_COMMANDS:]


working_memory = WorkingMemory()
