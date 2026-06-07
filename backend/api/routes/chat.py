from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from services.chat_service import chat_service
from core.memory.storage import memory_storage
from database.db import get_db

router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"
    vocal_input: bool = False       # True quand le message vient de la voix (STT)
    voice_energy: str = "normal"    # "calme" | "normal" | "intense" — détecté par analyse audio
    voice_duration: float = 0.0     # durée de l'enregistrement en secondes


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
        vocal_input=request.vocal_input,
        voice_energy=request.voice_energy,
        voice_duration=request.voice_duration,
    )
    return ChatResponse(**result)


@router.get("/history/{session_id}")
def get_history(
    session_id: str,
    db: Session = Depends(get_db),
    limit: int = Query(default=30, le=100),
):
    """
    Retourne l'historique de conversation d'une session.
    Utilisé par le frontend pour réafficher les échanges après rechargement.
    """
    convs = memory_storage.get_recent_conversations(db, session_id, limit)
    messages = []
    for conv in reversed(convs):          # ordre chronologique
        messages.append({
            "role": "user",
            "content": conv.user_message,
            "ts": conv.timestamp.isoformat(),
        })
        messages.append({
            "role": "assistant",
            "content": conv.assistant_response,
            "ts": conv.timestamp.isoformat(),
        })
    return {"session_id": session_id, "messages": messages, "count": len(messages)}


@router.delete("/session/{session_id}")
async def clear_session(session_id: str, db: Session = Depends(get_db)):
    """Efface la session RAM + (optionnel) propose un reset DB."""
    chat_service.clear_session(session_id)
    return {"message": f"Session '{session_id}' effacée du cache"}
