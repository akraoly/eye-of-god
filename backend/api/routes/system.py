import os
import socket
import time
from datetime import datetime, timedelta
from pathlib import Path
from fastapi import APIRouter, Depends
import psutil
from sqlalchemy.orm import Session
from app.config import settings
from database.db import get_db
from core.auth.dependencies import get_current_user
from services.agent_service import agent_service

router = APIRouter()

_BOOT_TIME = time.time()


def _fmt_uptime(seconds: float) -> str:
    td = timedelta(seconds=int(seconds))
    d, r = divmod(td.seconds, 86400)
    h, r = divmod(r, 3600)
    m = r // 60
    days = td.days
    if days:
        return f"{days}j {h}h {m}m"
    if h:
        return f"{h}h {m}m"
    return f"{m}m"


def _check_port(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.5):
            return True
    except OSError:
        return False


def _db_stats(db: Session) -> dict:
    tables = [
        ("conversations", "Conversations"),
        ("memories", "Souvenirs"),
        ("knowledge", "Knowledge base"),
        ("user_profile", "Profil utilisateur"),
        ("soc_alerts", "Alertes SOC"),
        ("siem_events", "Événements SIEM"),
        ("edr_agents", "Agents EDR"),
        ("threat_iocs", "IOCs"),
        ("osint_actors", "Acteurs OSINT"),
        ("app_users", "Utilisateurs"),
        ("scheduled_tasks", "Tâches planifiées"),
    ]
    result = []
    for table, label in tables:
        try:
            count = db.execute(__import__("sqlalchemy").text(f"SELECT COUNT(*) FROM {table}")).scalar()
            result.append({"table": table, "label": label, "count": count})
        except Exception:
            result.append({"table": table, "label": label, "count": 0})
    return result


def _chroma_stats() -> dict:
    chroma_dir = Path("./data/chroma")
    if not chroma_dir.exists():
        return {"status": "absent", "size_mb": 0, "collections": 0}
    size = sum(f.stat().st_size for f in chroma_dir.rglob("*") if f.is_file())
    try:
        import chromadb
        client = chromadb.PersistentClient(path=str(chroma_dir))
        colls = len(client.list_collections())
    except Exception:
        colls = 0
    return {"status": "ok", "size_mb": round(size / 1e6, 2), "collections": colls}


def _recent_logs(n: int = 30) -> list[str]:
    log_candidates = [
        Path("./logs/app.log"),
        Path("./app.log"),
        Path("/tmp/eye_of_god.log"),
    ]
    for lp in log_candidates:
        if lp.exists():
            try:
                lines = lp.read_text(errors="replace").splitlines()
                return lines[-n:]
            except Exception:
                pass
    return []


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


@router.get("/diagnostic")
async def diagnostic(db: Session = Depends(get_db)):
    # ── Système ──
    vm = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    cpu = psutil.cpu_percent(interval=0.3)
    sys_uptime = time.time() - psutil.boot_time()
    app_uptime = time.time() - _BOOT_TIME
    load = os.getloadavg() if hasattr(os, "getloadavg") else (0, 0, 0)

    # ── Services ──
    db_path = Path("./data/memory.db")
    services = [
        {
            "name": "Backend API",
            "port": 8001,
            "status": "online" if _check_port(8001) else "offline",
            "detail": f"FastAPI — {settings.APP_NAME} v{settings.APP_VERSION}",
        },
        {
            "name": "Frontend",
            "port": 3001,
            "status": "online" if _check_port(3001) else "offline",
            "detail": "React/Vite — Prod",
        },
        {
            "name": "SQLite DB",
            "port": None,
            "status": "online" if db_path.exists() else "offline",
            "detail": f"{round(db_path.stat().st_size / 1e6, 2)} MB" if db_path.exists() else "Introuvable",
        },
        {
            "name": "ChromaDB",
            "port": None,
            "status": "online" if Path("./data/chroma").exists() else "offline",
            "detail": f"Vecteurs persistants",
        },
    ]

    # ── Agents ──
    agents = [
        {"name": a["name"], "description": a["description"], "status": "ready"}
        for a in agent_service.list_agents()
    ]

    # ── Top processus ──
    procs = []
    for p in sorted(psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent", "status"]),
                    key=lambda x: x.info.get("cpu_percent") or 0, reverse=True)[:8]:
        try:
            procs.append({
                "pid": p.info["pid"],
                "name": p.info["name"],
                "cpu": round(p.info.get("cpu_percent") or 0, 1),
                "mem": round(p.info.get("memory_percent") or 0, 1),
                "status": p.info.get("status", "?"),
            })
        except Exception:
            pass

    return {
        "timestamp": datetime.utcnow().isoformat(),
        "system": {
            "cpu_percent": cpu,
            "cpu_count": psutil.cpu_count(),
            "load_avg": [round(x, 2) for x in load],
            "ram_total_gb": round(vm.total / 1e9, 1),
            "ram_used_gb": round((vm.total - vm.available) / 1e9, 1),
            "ram_percent": vm.percent,
            "disk_total_gb": round(disk.total / 1e9, 1),
            "disk_used_gb": round(disk.used / 1e9, 1),
            "disk_percent": disk.percent,
            "sys_uptime": _fmt_uptime(sys_uptime),
            "app_uptime": _fmt_uptime(app_uptime),
            "hostname": socket.gethostname(),
            "os": f"{os.uname().sysname} {os.uname().release}" if hasattr(os, "uname") else "Linux",
        },
        "services": services,
        "agents": agents,
        "db_stats": _db_stats(db),
        "chroma": _chroma_stats(),
        "top_processes": procs,
        "logs": _recent_logs(30),
    }


# ── Terminal PTY WebSocket (MODULE 10) ────────────────────────────────────────

import asyncio as _asyncio
import fcntl as _fcntl
import pty as _pty
import select as _select
import signal as _signal
import struct as _struct
import termios as _termios
from fastapi import Query, WebSocket
from starlette.websockets import WebSocketDisconnect
from core.auth.jwt_handler import decode_access_token as decode_token


def _verify_ws_token(token: str | None) -> bool:
    if not token:
        return False
    try:
        decode_token(token)
        return True
    except Exception:
        return False


def _set_pty_size(fd: int, rows: int, cols: int) -> None:
    try:
        size = _struct.pack("HHHH", rows, cols, 0, 0)
        _fcntl.ioctl(fd, _termios.TIOCSWINSZ, size)
    except Exception:
        pass


@router.websocket("/terminal-ws")
async def terminal_websocket(websocket: WebSocket, token: str = Query(None)):
    """Interactive PTY terminal over WebSocket. Token via ?token= query param."""
    if not _verify_ws_token(token):
        await websocket.close(code=4001, reason="Unauthorized")
        return

    await websocket.accept()

    master_fd, slave_fd = _pty.openpty()
    pid = os.fork()
    if pid == 0:
        os.setsid()
        _fcntl.ioctl(slave_fd, _termios.TIOCSCTTY, 0)
        os.dup2(slave_fd, 0)
        os.dup2(slave_fd, 1)
        os.dup2(slave_fd, 2)
        os.close(master_fd)
        os.close(slave_fd)
        shell = os.environ.get("SHELL", "/bin/bash")
        os.execv(shell, [shell, "--login"])
        os._exit(1)

    os.close(slave_fd)
    loop = _asyncio.get_event_loop()

    async def read_pty():
        try:
            while True:
                ready, _, _ = await loop.run_in_executor(
                    None, lambda: _select.select([master_fd], [], [], 0.05)
                )
                if ready:
                    try:
                        data = os.read(master_fd, 4096)
                        if not data:
                            break
                        await websocket.send_bytes(data)
                    except OSError:
                        break
        except Exception:
            pass

    async def write_pty():
        try:
            while True:
                msg = await websocket.receive()
                if msg.get("type") == "websocket.disconnect":
                    break
                if "bytes" in msg:
                    os.write(master_fd, msg["bytes"])
                elif "text" in msg:
                    text = msg["text"]
                    try:
                        import json as _j
                        d = _j.loads(text)
                        if d.get("type") == "resize":
                            _set_pty_size(master_fd, d.get("rows", 24), d.get("cols", 80))
                        else:
                            os.write(master_fd, text.encode())
                    except Exception:
                        os.write(master_fd, text.encode())
        except WebSocketDisconnect:
            pass
        except Exception:
            pass

    try:
        await _asyncio.gather(read_pty(), write_pty())
    finally:
        try:
            os.kill(pid, _signal.SIGKILL)
        except ProcessLookupError:
            pass
        try:
            os.waitpid(pid, os.WNOHANG)
        except ChildProcessError:
            pass
        try:
            os.close(master_fd)
        except OSError:
            pass
