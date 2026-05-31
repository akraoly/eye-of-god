from database.db import get_db  # noqa: F401 — re-export for convenience
from services.chat_service import chat_service
from services.memory_service import memory_service
from services.agent_service import agent_service


def get_chat_service():
    return chat_service


def get_memory_service():
    return memory_service


def get_agent_service():
    return agent_service
