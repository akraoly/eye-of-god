"""
Routes /api/c2/unified — C2Manager Engine unifié.

Endpoints :
  GET  /unified/               → liste des instances enregistrées
  POST /unified/register       → enregistrer un nouveau C2
  DELETE /unified/{name}       → désenregistrer
  POST /unified/{name}/connect → connecter
  POST /unified/{name}/disconnect → déconnecter
  GET  /unified/status         → dashboard état de tous les C2
  GET  /unified/{name}/status  → état d'un C2
  GET  /unified/{name}/listeners → liste des listeners
  POST /unified/{name}/listeners → créer un listener
  DELETE /unified/{name}/listeners/{id} → supprimer un listener
  GET  /unified/{name}/agents  → liste des agents
  GET  /unified/agents/all     → tous les agents de tous les C2
  POST /unified/{name}/tasks   → envoyer une tâche
  GET  /unified/{name}/tasks/{task_id} → résultat d'une tâche
  POST /unified/{name}/payload → générer un payload
  WS   /unified/events         → WebSocket flux d'événements
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from c2_manager import c2_engine, event_bus
from c2_manager.models import C2Config, C2Type, PayloadConfig
from c2_manager.interfaces import C2Error, C2ConnectionError, C2NotConnected

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Schémas de requête ────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    name:       str
    c2_type:    str
    host:       str
    port:       int
    ssl:        bool = False
    username:   str | None = None
    password:   str | None = None
    api_key:    str | None = None
    auth_token: str | None = None
    extra:      dict[str, Any] = {}


class ListenerRequest(BaseModel):
    name:      str = ""
    protocol:  str = "http"
    bind_host: str = "0.0.0.0"
    bind_port: int = 80
    options:   dict[str, Any] = {}


class TaskRequest(BaseModel):
    agent_id: str
    command:  str
    args:     list[str] = []


class PayloadRequest(BaseModel):
    name:        str
    listener_id: str
    format:      str = "exe"
    arch:        str = "x64"
    os:          str = "windows"
    obfuscation: bool = True
    sleep:       int = 60
    jitter:      int = 10
    extra:       dict[str, Any] = {}


# ── Instances ─────────────────────────────────────────────────────────────────

@router.get("/")
def list_instances():
    names = c2_engine.list_registered()
    return {"instances": names, "count": len(names)}


@router.post("/register")
def register_c2(req: RegisterRequest):
    try:
        c2_type = C2Type(req.c2_type)
    except ValueError:
        raise HTTPException(400, f"c2_type inconnu : {req.c2_type}. "
                            f"Valeurs valides : {[t.value for t in C2Type]}")
    try:
        config = C2Config(
            name       = req.name,
            c2_type    = c2_type,
            host       = req.host,
            port       = req.port,
            ssl        = req.ssl,
            username   = req.username,
            password   = req.password,
            api_key    = req.api_key,
            auth_token = req.auth_token,
            extra      = req.extra,
        )
        c2_engine.register(config)
        return {"status": "registered", "name": req.name, "c2_type": req.c2_type}
    except Exception as exc:
        raise HTTPException(400, str(exc))


@router.delete("/{name}")
def unregister_c2(name: str):
    try:
        c2_engine.unregister(name)
        return {"status": "unregistered", "name": name}
    except KeyError as exc:
        raise HTTPException(404, str(exc))


# ── Connexion ─────────────────────────────────────────────────────────────────

@router.post("/{name}/connect")
async def connect_c2(name: str):
    try:
        ok = await c2_engine.connect(name)
        return {"status": "connected" if ok else "failed", "name": name}
    except KeyError as exc:
        raise HTTPException(404, str(exc))
    except C2ConnectionError as exc:
        raise HTTPException(503, f"Connexion échouée : {exc}")
    except Exception as exc:
        raise HTTPException(500, str(exc))


@router.post("/{name}/disconnect")
async def disconnect_c2(name: str):
    try:
        await c2_engine.disconnect(name)
        return {"status": "disconnected", "name": name}
    except KeyError as exc:
        raise HTTPException(404, str(exc))


@router.post("/{name}/reconnect")
async def reconnect_c2(name: str):
    try:
        ok = await c2_engine.reconnect(name)
        return {"status": "connected" if ok else "failed", "name": name}
    except KeyError as exc:
        raise HTTPException(404, str(exc))
    except C2ConnectionError as exc:
        raise HTTPException(503, str(exc))


# ── Status ────────────────────────────────────────────────────────────────────

@router.get("/status")
async def status_all():
    return await c2_engine.status_all()


@router.get("/{name}/status")
async def status_one(name: str):
    try:
        return await c2_engine.status(name)
    except KeyError as exc:
        raise HTTPException(404, str(exc))


# ── Listeners ─────────────────────────────────────────────────────────────────

@router.get("/{name}/listeners")
async def list_listeners(name: str):
    try:
        listeners = await c2_engine.list_listeners(name)
        return {"listeners": [l.model_dump() for l in listeners]}
    except KeyError as exc:
        raise HTTPException(404, str(exc))
    except C2NotConnected as exc:
        raise HTTPException(409, str(exc))


@router.post("/{name}/listeners")
async def create_listener(name: str, req: ListenerRequest):
    try:
        listener = await c2_engine.create_listener(name, req.model_dump())
        return listener.model_dump()
    except KeyError as exc:
        raise HTTPException(404, str(exc))
    except C2NotConnected as exc:
        raise HTTPException(409, str(exc))
    except Exception as exc:
        raise HTTPException(500, str(exc))


@router.delete("/{name}/listeners/{listener_id}")
async def remove_listener(name: str, listener_id: str):
    try:
        ok = await c2_engine.remove_listener(name, listener_id)
        return {"deleted": ok, "listener_id": listener_id}
    except KeyError as exc:
        raise HTTPException(404, str(exc))


# ── Agents ────────────────────────────────────────────────────────────────────

@router.get("/{name}/agents")
async def list_agents(name: str):
    try:
        agents = await c2_engine.list_agents(name)
        return {"agents": [a.model_dump() for a in agents], "count": len(agents)}
    except KeyError as exc:
        raise HTTPException(404, str(exc))
    except C2NotConnected as exc:
        raise HTTPException(409, str(exc))


@router.get("/agents/all")
async def list_all_agents():
    data = await c2_engine.list_all_agents()
    return {
        name: [a.model_dump() for a in agents]
        for name, agents in data.items()
    }


# ── Tâches ────────────────────────────────────────────────────────────────────

@router.post("/{name}/tasks")
async def send_task(name: str, req: TaskRequest):
    try:
        task = await c2_engine.send_task(name, req.agent_id, req.command, req.args)
        return task.model_dump()
    except KeyError as exc:
        raise HTTPException(404, str(exc))
    except Exception as exc:
        raise HTTPException(500, str(exc))


@router.get("/{name}/tasks/{task_id}")
async def get_task_result(name: str, task_id: str):
    try:
        result = await c2_engine.get_task_result(name, task_id)
        return result
    except KeyError as exc:
        raise HTTPException(404, str(exc))
    except C2NotConnected as exc:
        raise HTTPException(409, str(exc))


# ── Payload ───────────────────────────────────────────────────────────────────

@router.post("/{name}/payload")
async def generate_payload(name: str, req: PayloadRequest):
    try:
        config = PayloadConfig(
            name        = req.name,
            c2_type     = c2_engine.get_config(name).c2_type,
            listener_id = req.listener_id,
            format      = req.format,
            arch        = req.arch,
            os          = req.os,
            obfuscation = req.obfuscation,
            sleep       = req.sleep,
            jitter      = req.jitter,
            extra       = req.extra,
        )
        payload_bytes = await c2_engine.generate_payload(name, config)
        if not payload_bytes:
            return {"status": "empty", "note": "Le C2 n'a pas retourné de données"}

        from fastapi.responses import Response
        ext_map = {"exe": "exe", "dll": "dll", "ps1": "ps1", "elf": "elf", "raw": "bin"}
        ext = ext_map.get(req.format, "bin")
        return Response(
            content=payload_bytes,
            media_type="application/octet-stream",
            headers={"Content-Disposition": f'attachment; filename="{req.name}.{ext}"'},
        )
    except KeyError as exc:
        raise HTTPException(404, str(exc))
    except C2NotConnected as exc:
        raise HTTPException(409, str(exc))
    except Exception as exc:
        raise HTTPException(500, str(exc))


# ── WebSocket événements ──────────────────────────────────────────────────────

@router.websocket("/events")
async def events_ws(websocket: WebSocket):
    await websocket.accept()
    event_bus.add_ws_client(websocket)
    # Envoyer l'historique récent
    history = event_bus.get_history(n=20)
    for evt in history:
        import json
        await websocket.send_text(json.dumps(evt))
    try:
        while True:
            await websocket.receive_text()  # keepalive (ignore client messages)
    except WebSocketDisconnect:
        event_bus.remove_ws_client(websocket)
