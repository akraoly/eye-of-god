from typing import Optional
from sqlalchemy.orm import Session
from core.memory.storage import memory_storage


class MemoryService:
    def save(
        self,
        db: Session,
        memory_type: str,
        key: str,
        value: str,
        importance: float = 0.5,
    ) -> dict:
        mem = memory_storage.save_memory(
            db=db, memory_type=memory_type, key=key, value=value, importance=importance
        )
        return {"id": mem.id, "type": mem.memory_type, "key": mem.key, "value": mem.value}

    def list(self, db: Session, memory_type: Optional[str] = None, limit: int = 50) -> list:
        mems = memory_storage.get_memories(db=db, memory_type=memory_type, limit=limit)
        return [
            {
                "id": m.id,
                "type": m.memory_type,
                "key": m.key,
                "value": m.value,
                "importance": m.importance,
            }
            for m in mems
        ]

    def delete(self, db: Session, memory_id: int) -> bool:
        return memory_storage.delete_memory(db=db, memory_id=memory_id)

    def get_profile(self, db: Session) -> dict:
        return memory_storage.get_profile(db=db)

    def update_profile(self, db: Session, field: str, value: str) -> dict:
        p = memory_storage.save_profile_field(db=db, field=field, value=value)
        return {"field": p.field, "value": p.value}


memory_service = MemoryService()
