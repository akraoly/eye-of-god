from typing import List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from database.models import Conversation, Memory, UserProfile


class MemoryStorage:
    def save_conversation(
        self,
        db: Session,
        session_id: str,
        user_message: str,
        assistant_response: str,
        context_used: int = 0,
    ) -> Conversation:
        conv = Conversation(
            session_id=session_id,
            user_message=user_message,
            assistant_response=assistant_response,
            context_used=context_used,
        )
        db.add(conv)
        db.commit()
        db.refresh(conv)
        return conv

    def get_recent_conversations(
        self, db: Session, session_id: str, limit: int = 10
    ) -> List[Conversation]:
        return (
            db.query(Conversation)
            .filter(Conversation.session_id == session_id)
            .order_by(Conversation.timestamp.desc())
            .limit(limit)
            .all()
        )

    def save_memory(
        self,
        db: Session,
        memory_type: str,
        key: str,
        value: str,
        importance: float = 0.5,
        priority: str = "normal",
    ) -> Memory:
        existing = (
            db.query(Memory)
            .filter(Memory.memory_type == memory_type, Memory.key == key)
            .first()
        )
        if existing:
            existing.value = value
            existing.importance = importance
            existing.priority = priority
            existing.updated_at = datetime.utcnow()
            db.commit()
            return existing

        mem = Memory(
            memory_type=memory_type, key=key, value=value,
            importance=importance, priority=priority,
        )
        db.add(mem)
        db.commit()
        db.refresh(mem)
        return mem

    def get_memories_by_priority(
        self, db: Session, priority: str, limit: int = 10
    ) -> List[Memory]:
        return (
            db.query(Memory)
            .filter(Memory.priority == priority)
            .order_by(Memory.importance.desc())
            .limit(limit)
            .all()
        )

    def get_memories(
        self, db: Session, memory_type: Optional[str] = None, limit: int = 50
    ) -> List[Memory]:
        q = db.query(Memory)
        if memory_type:
            q = q.filter(Memory.memory_type == memory_type)
        return q.order_by(Memory.importance.desc(), Memory.updated_at.desc()).limit(limit).all()

    def delete_memory(self, db: Session, memory_id: int) -> bool:
        mem = db.query(Memory).filter(Memory.id == memory_id).first()
        if mem:
            db.delete(mem)
            db.commit()
            return True
        return False

    def save_profile_field(self, db: Session, field: str, value: str) -> UserProfile:
        existing = db.query(UserProfile).filter(UserProfile.field == field).first()
        if existing:
            existing.value = value
            existing.updated_at = datetime.utcnow()
            db.commit()
            return existing
        p = UserProfile(field=field, value=value)
        db.add(p)
        db.commit()
        db.refresh(p)
        return p

    def get_profile(self, db: Session) -> dict:
        return {f.field: f.value for f in db.query(UserProfile).all()}


memory_storage = MemoryStorage()
