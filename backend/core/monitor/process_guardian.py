"""
Gardien des processus — compare la liste courante avec la baseline.
Détecte : nouveaux processus inconnus, processus depuis /tmp ou /home,
consommation CPU anormale, processus cachés.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime

import psutil

try:
    from core.tools.logger import get_logger
    logger = get_logger("sentinel.processes")
except Exception:
    import logging
    logger = logging.getLogger(__name__)

_SUSPICIOUS_PATHS = ["/tmp/", "/dev/shm/", "/var/tmp/", "/run/user/"]
_CPU_PROC_THRESHOLD = 80.0   # % CPU pour un seul processus
_KNOWN_HIGH_CPU = {"python3", "uvicorn", "node", "code", "chromium", "firefox"}

# Processus connus légitimes — whitelist partielle
_PROCESS_WHITELIST_PATTERNS = [
    r"^python", r"^uvicorn", r"^node", r"^bash", r"^sh$", r"^zsh",
    r"^ssh", r"^sshd", r"^systemd", r"^dbus", r"^NetworkManager",
    r"^cron", r"^rsyslog", r"^journald", r"^udevd", r"^thermald",
    r"^cups", r"^avahi", r"^colord", r"^polkit", r"^gdm",
    r"^Xorg", r"^gnome", r"^kwin", r"^mutter", r"^pulseaudio",
    r"^pipewire", r"^wireplumber", r"^bluetoothd", r"^wpa_supplicant",
    r"^dhclient", r"^ntpd", r"^chronyd", r"^vmtoolsd", r"^VBoxClient",
    r"^apt", r"^dpkg", r"^git", r"^curl", r"^wget", r"^cat", r"^grep",
    r"^awk", r"^sed", r"^find", r"^ls$", r"^ps$", r"^top$",
    r"^kworker", r"^ksoftirqd", r"^migration", r"^watchdog",
    r"^irq", r"^rcu_", r"^jbd2", r"^ext4", r"^xfsaild",
    r"^postgres", r"^mysql", r"^mariadb", r"^nginx", r"^apache",
    r"^supervisord", r"^gunicorn", r"^celery",
]

_compiled_whitelist = [re.compile(p) for p in _PROCESS_WHITELIST_PATTERNS]


def _get_procs_snapshot() -> dict[int, dict]:
    procs = {}
    for proc in psutil.process_iter(['pid', 'name', 'exe', 'cmdline', 'username', 'cpu_percent']):
        try:
            info = proc.info
            procs[info['pid']] = {
                'name': info['name'] or '',
                'exe':  info['exe'] or '',
                'cmdline': ' '.join(info['cmdline'] or [])[:200],
                'username': info['username'] or '',
            }
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return procs


def build_baseline(db) -> dict:
    """Établit la baseline des processus au premier lancement."""
    procs = _get_procs_snapshot()
    data = json.dumps(procs)
    try:
        from database.models import MonitorBaseline
        existing = db.query(MonitorBaseline).filter(MonitorBaseline.baseline_type == "processes").first()
        if existing:
            existing.data = data
            existing.updated_at = datetime.utcnow()
        else:
            row = MonitorBaseline(baseline_type="processes", data=data)
            db.add(row)
        db.commit()
        logger.info("process_guardian: baseline établie (%d processus)", len(procs))
    except Exception as e:
        logger.error("process_guardian: erreur baseline: %s", e)
    return procs


def _load_baseline(db) -> dict[int, dict]:
    try:
        from database.models import MonitorBaseline
        row = db.query(MonitorBaseline).filter(MonitorBaseline.baseline_type == "processes").first()
        if row:
            return json.loads(row.data)
    except Exception:
        pass
    return {}


def _is_whitelisted(name: str) -> bool:
    for pat in _compiled_whitelist:
        if pat.match(name):
            return True
    return False


def _fire(category, severity, title, description, details=None, db=None):
    from core.monitor.event_bus import sentinel_bus
    sentinel_bus.publish({
        "type": "security_event",
        "category": category, "severity": severity,
        "title": title, "description": description,
        "details": details or {},
    })
    if db is not None:
        try:
            from database.models import SecurityEventLog
            row = SecurityEventLog(
                category=category, severity=severity,
                title=title, description=description,
                details=json.dumps(details or {}),
            )
            db.add(row)
            db.commit()
        except Exception:
            pass
    logger.warning("[PROCESS] %s — %s", severity, title)


def check_processes(db=None):
    """Vérifie les processus et alerte si anomalie détectée."""
    baseline = _load_baseline(db)
    if not baseline:
        if db is not None:
            build_baseline(db)
        return

    current = _get_procs_snapshot()
    baseline_names = {v['name'] for v in baseline.values()}

    for pid, info in current.items():
        name = info['name']
        exe  = info['exe']
        cmdline = info['cmdline']

        # Processus depuis chemin suspect
        if exe and any(exe.startswith(p) for p in _SUSPICIOUS_PATHS):
            _fire(
                category="PROCESS", severity="HIGH",
                title=f"Processus depuis chemin suspect : {name}",
                description=f"PID {pid} — exécutable: {exe}",
                details={"pid": pid, "name": name, "exe": exe, "cmdline": cmdline},
                db=db,
            )

        # Nouveau processus inconnu non-whitelisté
        elif name not in baseline_names and not _is_whitelisted(name) and name:
            _fire(
                category="PROCESS", severity="MEDIUM",
                title=f"Nouveau processus inconnu : {name} (PID {pid})",
                description=f"Ce processus n'était pas dans la baseline. CMD: {cmdline[:100]}",
                details={"pid": pid, "name": name, "exe": exe, "cmdline": cmdline},
                db=db,
            )

    # Vérification CPU anormal par processus
    try:
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent']):
            try:
                cpu_p = proc.info['cpu_percent'] or 0
                pname = proc.info['name'] or ''
                if cpu_p > _CPU_PROC_THRESHOLD and pname.lower() not in _KNOWN_HIGH_CPU:
                    _fire(
                        category="PROCESS", severity="MEDIUM",
                        title=f"Processus haute consommation CPU : {pname} ({cpu_p:.0f}%)",
                        description=f"PID {proc.pid} utilise {cpu_p:.1f}% CPU",
                        details={"pid": proc.pid, "name": pname, "cpu_pct": cpu_p},
                        db=db,
                    )
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    except Exception:
        pass


def get_process_list() -> list[dict]:
    procs = []
    for proc in psutil.process_iter(['pid', 'name', 'exe', 'cpu_percent', 'memory_percent', 'status', 'username']):
        try:
            info = proc.info
            procs.append({
                'pid': info['pid'],
                'name': info['name'],
                'exe': info['exe'] or '',
                'cpu_pct': round(info['cpu_percent'] or 0, 1),
                'mem_pct': round(info['memory_percent'] or 0, 1),
                'status': info['status'],
                'user': info['username'] or '',
                'suspicious': bool(info['exe'] and any(info['exe'].startswith(p) for p in _SUSPICIOUS_PATHS)),
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return sorted(procs, key=lambda x: x['cpu_pct'], reverse=True)[:50]
