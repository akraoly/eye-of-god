import json
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from services.chat_service import chat_service
from core.memory.storage import memory_storage
from database.db import get_db

router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"
    vocal_input: bool = False
    voice_energy: str = "normal"
    voice_duration: float = 0.0
    image_b64: str = ""
    media_type: str = "image/png"


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
        image_b64=request.image_b64,
        media_type=request.media_type,
    )
    return ChatResponse(**result)


@router.post("/stream")
async def chat_stream(request: ChatRequest, db: Session = Depends(get_db)):
    """
    Endpoint streaming SSE — envoie les tokens au fur et à mesure.
    Le frontend peut démarrer le TTS dès la première phrase complète.
    """
    async def event_generator():
        full_response = ""
        try:
            async for chunk in chat_service.stream(
                db=db,
                message=request.message,
                session_id=request.session_id,
                vocal_input=request.vocal_input,
                voice_energy=request.voice_energy,
                voice_duration=request.voice_duration,
                image_b64=request.image_b64,
                media_type=request.media_type,
            ):
                full_response += chunk
                payload = json.dumps({"chunk": chunk}, ensure_ascii=False)
                yield f"data: {payload}\n\n"

            # Fin du stream : envoyer le signal + métadonnées
            yield f"data: {json.dumps({'done': True, 'full': full_response}, ensure_ascii=False)}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/history/{session_id}")
def get_history(
    session_id: str,
    db: Session = Depends(get_db),
    limit: int = Query(default=30, le=100),
):
    convs = memory_storage.get_recent_conversations(db, session_id, limit)
    messages = []
    for conv in reversed(convs):
        messages.append({"role": "user",      "content": conv.user_message,      "ts": conv.timestamp.isoformat()})
        messages.append({"role": "assistant", "content": conv.assistant_response, "ts": conv.timestamp.isoformat()})
    return {"session_id": session_id, "messages": messages, "count": len(messages)}


@router.delete("/session/{session_id}")
async def clear_session(session_id: str, db: Session = Depends(get_db)):
    chat_service.clear_session(session_id)
    return {"message": f"Session '{session_id}' effacée du cache"}
