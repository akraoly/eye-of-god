from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from services.memory_service import memory_service
from database.db import get_db

router = APIRouter()


class MemorySaveRequest(BaseModel):
    memory_type: str = "user"
    key: str
    value: str
    importance: float = 0.5


class ProfileUpdateRequest(BaseModel):
    field: str
    value: str


@router.post("/save")
async def save_memory(request: MemorySaveRequest, db: Session = Depends(get_db)):
    return memory_service.save(
        db=db,
        memory_type=request.memory_type,
        key=request.key,
        value=request.value,
        importance=request.importance,
    )


@router.get("/get")
async def get_memories(
    memory_type: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    return memory_service.list(db=db, memory_type=memory_type, limit=limit)


@router.delete("/{memory_id}")
async def delete_memory(memory_id: int, db: Session = Depends(get_db)):
    if not memory_service.delete(db=db, memory_id=memory_id):
        raise HTTPException(status_code=404, detail="Mémoire introuvable")
    return {"message": "Mémoire supprimée"}


@router.get("/profile")
async def get_profile(db: Session = Depends(get_db)):
    return memory_service.get_profile(db=db)


@router.post("/profile")
async def update_profile(request: ProfileUpdateRequest, db: Session = Depends(get_db)):
    return memory_service.update_profile(db=db, field=request.field, value=request.value)
