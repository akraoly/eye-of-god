"""
Routes /api/network — Surveillance réseau temps réel.
WebSocket streaming + REST snapshot.
"""
import asyncio
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, Depends
from core.network.monitor import network_monitor
from core.auth.jwt_handler import decode_access_token
from core.auth.dependencies import get_current_user
import jwt as _jwt

router = APIRouter()


@router.websocket("/ws")
async def network_ws(websocket: WebSocket, token: str = Query(...)):
    """Stream WebSocket des événements réseau en temps réel."""
    # Auth via query param (les WS ne peuvent pas envoyer de headers Authorization)
    try:
        decode_access_token(token)
    except (_jwt.ExpiredSignatureError, _jwt.InvalidTokenError):
        await websocket.close(code=4001)
        return
    await websocket.accept()
    queue: asyncio.Queue = asyncio.Queue(maxsize=100)
    network_monitor.subscribe(queue)

    # Envoyer l'historique récent
    for evt in network_monitor.get_history(30):
        try:
            await websocket.send_text(json.dumps(evt, ensure_ascii=False))
        except Exception:
            break

    try:
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=3.0)
                await websocket.send_text(json.dumps(event, ensure_ascii=False))
            except asyncio.TimeoutError:
                # Keepalive ping
                await websocket.send_text(json.dumps({"type": "ping"}))
    except (WebSocketDisconnect, Exception):
        pass
    finally:
        network_monitor.unsubscribe(queue)


@router.get("/snapshot", dependencies=[Depends(get_current_user)])
async def network_snapshot():
    """Snapshot instantané de l'état réseau (connexions + interfaces)."""
    return network_monitor.get_snapshot()


@router.get("/history", dependencies=[Depends(get_current_user)])
async def network_history(n: int = 50):
    """Derniers N événements réseau."""
    return {"events": network_monitor.get_history(n)}
