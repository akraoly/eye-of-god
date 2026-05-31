from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from services.chat_service import chat_service
from database.db import get_db

router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"


class ChatResponse(BaseModel):
    response: str
    session_id: str
    memories_used: int


@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest, db: Session = Depends(get_db)):
    result = await chat_service.chat(
        db=db,
        message=request.message,
        session_id=request.session_id,
    )
    return ChatResponse(**result)


@router.delete("/session/{session_id}")
async def clear_session(session_id: str):
    chat_service.clear_session(session_id)
    return {"message": f"Session '{session_id}' effacée"}
