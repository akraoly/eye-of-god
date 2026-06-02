"""
Moniteurs système proactifs — CPU, RAM, Disk, Backend health.
"""
import psutil
from datetime import datetime, timezone
from apscheduler.triggers.interval import IntervalTrigger
from core.autonomy.alert_store import alert_store
from core.tools.logger import get_logger

logger = get_logger("monitors")

# Seuils d'alerte
THRESHOLDS = {
    "cpu_pct":    90.0,   # %
    "ram_pct":    90.0,   # %
    "disk_pct":   95.0,   # %
    "disk_warn":  80.0,   # avertissement
}

# État pour éviter les alertes répétées
_last_alerts: dict[str, datetime] = {}
_COOLDOWN_SECONDS = 300  # 5 min entre deux alertes du même type


def _should_alert(key: str) -> bool:
    now = datetime.now(timezone.utc)
    last = _last_alerts.get(key)
    if last is None or (now - last).total_seconds() >= _COOLDOWN_SECONDS:
        _last_alerts[key] = now
        return True
    return False


def check_system():
    """Vérifie CPU, RAM, disque et crée des alertes si nécessaire."""
    try:
        cpu = psutil.cpu_percent(interval=1)
        ram = psutil.virtual_memory()
        disk = psutil.disk_usage("/")

        if cpu >= THRESHOLDS["cpu_pct"] and _should_alert("cpu_high"):
            alert_store.add(
                title=f"🔥 CPU élevé : {cpu:.0f}%",
                body=f"Le CPU dépasse {THRESHOLDS['cpu_pct']:.0f}% depuis plusieurs secondes.",
                level="warning", source="monitor",
                meta={"metric": "cpu", "value": cpu},
            )

        ram_pct = ram.percent
        if ram_pct >= THRESHOLDS["ram_pct"] and _should_alert("ram_high"):
            alert_store.add(
                title=f"🧠 RAM critique : {ram_pct:.0f}%",
                body=f"{ram.used // 1024**3:.1f} GB utilisés sur {ram.total // 1024**3:.1f} GB.",
                level="warning", source="monitor",
                meta={"metric": "ram", "value": ram_pct},
            )

        disk_pct = disk.percent
        if disk_pct >= THRESHOLDS["disk_pct"] and _should_alert("disk_critical"):
            alert_store.add(
                title=f"💾 Disque plein : {disk_pct:.0f}%",
                body=f"{disk.free // 1024**3:.1f} GB libres sur {disk.total // 1024**3:.1f} GB.",
                level="error", source="monitor",
                meta={"metric": "disk", "value": disk_pct},
            )
        elif disk_pct >= THRESHOLDS["disk_warn"] and _should_alert("disk_warn"):
            alert_store.add(
                title=f"💾 Disque presque plein : {disk_pct:.0f}%",
                body=f"{disk.free // 1024**3:.1f} GB libres sur {disk.total // 1024**3:.1f} GB.",
                level="warning", source="monitor",
                meta={"metric": "disk", "value": disk_pct},
            )

    except Exception as e:
        logger.warning(f"check_system error: {e}")


def get_system_snapshot() -> dict:
    """Retourne un snapshot instantané des métriques système."""
    try:
        cpu    = psutil.cpu_percent(interval=0.1)
        ram    = psutil.virtual_memory()
        disk   = psutil.disk_usage("/")
        net    = psutil.net_io_counters()
        procs  = len(psutil.pids())
        return {
            "cpu_pct":    round(cpu, 1),
            "ram_pct":    round(ram.percent, 1),
            "ram_used_gb":round(ram.used / 1024**3, 2),
            "ram_total_gb":round(ram.total / 1024**3, 2),
            "disk_pct":   round(disk.percent, 1),
            "disk_free_gb":round(disk.free / 1024**3, 2),
            "disk_total_gb":round(disk.total / 1024**3, 2),
            "net_sent_mb":round(net.bytes_sent / 1024**2, 1),
            "net_recv_mb":round(net.bytes_recv / 1024**2, 1),
            "processes":  procs,
            "ts":         datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        return {"error": str(e)}


MONITORS = [
    {
        "id":          "system_health",
        "name":        "Santé système",
        "description": "CPU · RAM · Disque — alertes si seuils dépassés",
        "interval_seconds": 60,
        "fn":          check_system,
        "enabled":     True,
    },
]


def register_monitors(scheduler):
    """Enregistre tous les moniteurs dans le scheduler."""
    for m in MONITORS:
        if m["enabled"]:
            scheduler.add_job(
                m["fn"],
                trigger=IntervalTrigger(seconds=m["interval_seconds"]),
                id=f"monitor_{m['id']}",
                replace_existing=True,
                max_instances=1,
            )
            logger.info(f"Moniteur démarré : {m['name']}")
