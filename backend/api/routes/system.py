from datetime import datetime
from fastapi import APIRouter
import psutil
from app.config import settings
from services.agent_service import agent_service

router = APIRouter()


@router.get("/health")
async def health():
    return {
        "status": "online",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/metrics")
async def metrics():
    vm = psutil.virtual_memory()
    return {
        "cpu_percent": psutil.cpu_percent(interval=0.1),
        "memory": {
            "total_gb": round(vm.total / 1e9, 2),
            "available_gb": round(vm.available / 1e9, 2),
            "percent": vm.percent,
        },
        "disk_percent": psutil.disk_usage("/").percent,
    }


@router.get("/agents")
async def list_agents():
    return agent_service.list_agents()


@router.post("/agents/dispatch")
async def dispatch_agent(task: str):
    return await agent_service.dispatch(task=task)
