"""
Collecteur de métriques système — toutes les 30 secondes.
Stocke dans SystemMetricHistory (SQLite).
Alerte si CPU > 90% pendant plus de 2 minutes.
"""
from __future__ import annotations

import json
from datetime import datetime
from collections import deque

import psutil

try:
    from core.tools.logger import get_logger
    logger = get_logger("sentinel.metrics")
except Exception:
    import logging
    logger = logging.getLogger(__name__)

# CPU > 90% compteur : 4 checks * 30s = 120s = 2 min
_CPU_HIGH_THRESHOLD   = 90.0
_CPU_HIGH_TICKS_LIMIT = 4   # nombre de checks consécutifs
_cpu_high_ticks       = 0
_cpu_alert_cooldown   = 0   # ticks avant re-alerte


def collect_metrics(db=None) -> dict:
    """Collecte et stocke les métriques. Retourne le snapshot."""
    global _cpu_high_ticks, _cpu_alert_cooldown

    try:
        cpu   = psutil.cpu_percent(interval=0.5)
        ram   = psutil.virtual_memory()
        disk  = psutil.disk_usage("/")
        swap  = psutil.swap_memory()
        net   = psutil.net_io_counters()
        procs = len(psutil.pids())

        # Température CPU (Linux)
        cpu_temp = None
        try:
            temps = psutil.sensors_temperatures()
            for name, entries in temps.items():
                if entries:
                    cpu_temp = round(entries[0].current, 1)
                    break
        except Exception:
            pass

        open_ports = 0
        try:
            conns = psutil.net_connections(kind='inet')
            open_ports = sum(1 for c in conns if c.status == 'LISTEN')
        except Exception:
            pass

        from core.monitor.health_score import compute_health_score
        health = compute_health_score(
            cpu_pct=cpu, ram_pct=ram.percent, disk_pct=disk.percent,
            swap_pct=swap.percent, cpu_temp=cpu_temp,
        )

        snapshot = {
            "timestamp": datetime.utcnow().isoformat(),
            "cpu_pct":    round(cpu, 1),
            "ram_pct":    round(ram.percent, 1),
            "ram_used_gb": round(ram.used / 1024**3, 2),
            "ram_total_gb": round(ram.total / 1024**3, 2),
            "disk_pct":   round(disk.percent, 1),
            "disk_free_gb": round(disk.free / 1024**3, 2),
            "disk_total_gb": round(disk.total / 1024**3, 2),
            "swap_pct":   round(swap.percent, 1),
            "cpu_temp":   cpu_temp,
            "net_sent_mb": round(net.bytes_sent / 1024**2, 2),
            "net_recv_mb": round(net.bytes_recv / 1024**2, 2),
            "process_count": procs,
            "open_ports": open_ports,
            "health_score": health,
        }

        # Stocker en base
        if db is not None:
            try:
                from database.models import SystemMetricHistory
                row = SystemMetricHistory(
                    cpu_pct=cpu, ram_pct=ram.percent, disk_pct=disk.percent,
                    swap_pct=swap.percent, cpu_temp=cpu_temp,
                    net_sent_mb=round(net.bytes_sent / 1024**2, 2),
                    net_recv_mb=round(net.bytes_recv / 1024**2, 2),
                    process_count=procs, open_ports=open_ports, health_score=health,
                )
                db.add(row)
                db.commit()
            except Exception as e:
                logger.debug("metrics: erreur DB: %s", e)

        # Publier snapshot sur le bus
        from core.monitor.event_bus import sentinel_bus
        sentinel_bus.publish({"type": "metrics", **snapshot})

        # CPU > 90% depuis 2 min
        if _cpu_alert_cooldown > 0:
            _cpu_alert_cooldown -= 1
        if cpu >= _CPU_HIGH_THRESHOLD:
            _cpu_high_ticks += 1
            if _cpu_high_ticks >= _CPU_HIGH_TICKS_LIMIT and _cpu_alert_cooldown == 0:
                _cpu_alert_cooldown = 20  # 10 min cooldown
                _cpu_high_ticks = 0
                _fire_critical_alert(
                    category="METRIC",
                    severity="CRITICAL",
                    title=f"CPU élevé depuis 2 minutes : {cpu:.0f}%",
                    description=f"Le CPU dépasse {_CPU_HIGH_THRESHOLD:.0f}% de manière continue. Processus suspects possibles.",
                    details={"cpu_pct": cpu},
                    db=db,
                )
        else:
            _cpu_high_ticks = max(0, _cpu_high_ticks - 1)

        # RAM critique
        if ram.percent >= 95:
            _fire_critical_alert(
                category="METRIC", severity="HIGH",
                title=f"RAM critique : {ram.percent:.0f}%",
                description=f"{ram.used // 1024**3:.1f} GB / {ram.total // 1024**3:.1f} GB utilisés",
                details={"ram_pct": ram.percent},
                db=db, cooldown_key="ram_high",
            )

        return snapshot

    except Exception as e:
        logger.error("metrics_collector: %s", e)
        return {}


_COOLDOWNS: dict[str, int] = {}

def _fire_critical_alert(category, severity, title, description, details=None,
                          db=None, cooldown_key: str = None):
    if cooldown_key:
        if _COOLDOWNS.get(cooldown_key, 0) > 0:
            _COOLDOWNS[cooldown_key] -= 1
            return
        _COOLDOWNS[cooldown_key] = 20

    from core.monitor.event_bus import sentinel_bus
    sentinel_bus.publish({
        "type": "security_event",
        "category": category,
        "severity": severity,
        "title": title,
        "description": description,
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

    logger.warning("[SENTINEL] %s — %s", severity, title)


def get_history(db, limit: int = 100) -> list[dict]:
    try:
        from database.models import SystemMetricHistory
        rows = (
            db.query(SystemMetricHistory)
            .order_by(SystemMetricHistory.timestamp.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "timestamp": r.timestamp.isoformat(),
                "cpu_pct": r.cpu_pct, "ram_pct": r.ram_pct,
                "disk_pct": r.disk_pct, "swap_pct": r.swap_pct,
                "cpu_temp": r.cpu_temp, "health_score": r.health_score,
                "net_sent_mb": r.net_sent_mb, "net_recv_mb": r.net_recv_mb,
                "process_count": r.process_count, "open_ports": r.open_ports,
            }
            for r in reversed(rows)
        ]
    except Exception:
        return []
