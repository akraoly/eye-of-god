"""
Routes /api/c2 — gestion asynchrone des frameworks C2.
"""
from fastapi import APIRouter
from pydantic import BaseModel
from core.tools.c2_manager import c2_manager

router = APIRouter()


@router.get("/")
def list_c2():
    return {"c2s": c2_manager.list_all()}


@router.get("/status/{name}")
def get_status(name: str):
    return c2_manager.status(name)


class StartRequest(BaseModel):
    name: str


@router.post("/start")
def start_c2(req: StartRequest):
    return c2_manager.start(req.name)


@router.post("/stop/{name}")
def stop_c2(name: str):
    return c2_manager.stop(name)


@router.get("/logs/{name}")
def get_logs(name: str, n: int = 100):
    return c2_manager.logs(name, n)
