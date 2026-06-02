"""
Scheduler APScheduler — gestion des tâches planifiées et des moniteurs système.
"""
import asyncio
import subprocess
import uuid
from datetime import datetime, timezone
from typing import Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from core.tools.logger import get_logger
from core.autonomy.alert_store import alert_store

logger = get_logger("scheduler")
_scheduler: Optional[AsyncIOScheduler] = None


def get_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler(timezone="UTC")
    return _scheduler


def start_scheduler():
    s = get_scheduler()
    if not s.running:
        s.start()
        logger.info("Scheduler démarré")


def stop_scheduler():
    s = get_scheduler()
    if s.running:
        s.shutdown(wait=False)
        logger.info("Scheduler arrêté")


# ── Exécution d'une tâche shell ───────────────────────────────────────────────

async def _run_shell_task(task_id: str, command: str, name: str):
    logger.info(f"[task:{task_id}] Exécution: {command}")
    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
        output = (stdout or b"").decode(errors="replace")
        err    = (stderr or b"").decode(errors="replace")
        code   = proc.returncode

        result_summary = output[:300] if output else (err[:200] if err else "(aucune sortie)")
        level = "info" if code == 0 else "warning"
        alert_store.add(
            title=f"✅ Tâche exécutée : {name}" if code == 0 else f"⚠️ Tâche échouée : {name}",
            body=f"Exit {code} — {result_summary}",
            level=level,
            source="task",
            meta={"task_id": task_id, "command": command, "exit_code": code},
        )
    except asyncio.TimeoutError:
        alert_store.add(
            title=f"⏱️ Timeout : {name}",
            body=f"La commande n'a pas répondu dans les 60s : {command}",
            level="warning",
            source="task",
            meta={"task_id": task_id},
        )
    except Exception as e:
        alert_store.add(
            title=f"❌ Erreur tâche : {name}",
            body=str(e),
            level="error",
            source="task",
            meta={"task_id": task_id},
        )


async def _run_http_check(task_id: str, url: str, name: str):
    import aiohttp
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.get(url) as resp:
                level = "info" if resp.status < 400 else "warning"
                alert_store.add(
                    title=f"🌐 Check HTTP : {name}",
                    body=f"{url} → HTTP {resp.status}",
                    level=level,
                    source="task",
                    meta={"task_id": task_id, "url": url, "status": resp.status},
                )
    except Exception as e:
        alert_store.add(
            title=f"🔴 URL injoignable : {name}",
            body=f"{url} — {e}",
            level="error",
            source="task",
            meta={"task_id": task_id, "url": url},
        )


# ── API publique ──────────────────────────────────────────────────────────────

def schedule_task(task: dict) -> str:
    """Planifie une tâche. Retourne le job_id APScheduler."""
    s = get_scheduler()
    task_id = task["id"]
    name    = task["name"]
    kind    = task.get("kind", "shell")
    sched   = task.get("schedule_type", "interval")

    if kind == "shell":
        fn = lambda: asyncio.ensure_future(_run_shell_task(task_id, task.get("command","echo ok"), name))
    elif kind == "http_check":
        fn = lambda: asyncio.ensure_future(_run_http_check(task_id, task.get("url",""), name))
    else:
        fn = lambda: asyncio.ensure_future(_run_shell_task(task_id, task.get("command","echo ok"), name))

    if sched == "cron":
        trigger = CronTrigger.from_crontab(task["cron"])
    elif sched == "once":
        trigger = DateTrigger(run_date=datetime.fromisoformat(task["run_at"]))
    else:  # interval
        trigger = IntervalTrigger(seconds=int(task.get("interval_seconds", 3600)))

    job = s.add_job(fn, trigger=trigger, id=task_id, replace_existing=True, max_instances=1)
    return job.id


def remove_task(task_id: str):
    s = get_scheduler()
    try:
        s.remove_job(task_id)
    except Exception:
        pass


def run_task_now(task: dict):
    asyncio.ensure_future(_run_shell_task(task["id"], task.get("command","echo ok"), task["name"]))


def list_jobs() -> list[dict]:
    s = get_scheduler()
    result = []
    for job in s.get_jobs():
        result.append({
            "job_id": job.id,
            "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
            "trigger": str(job.trigger),
        })
    return result
