from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from services.memory_service import memory_service
from database.db import get_db

router = APIRouter()


@router.get("/profile")
async def get_user_profile(db: Session = Depends(get_db)):
    profile = memory_service.get_profile(db=db)
    memories = memory_service.list(db=db, memory_type="user", limit=100)
    return {
        "profile": profile,
        "user_memories": memories,
        "total_memories": len(memories),
    }
