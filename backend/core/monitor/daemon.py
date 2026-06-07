"""
Daemon Sentinel — orchestre tous les modules de surveillance.
Enregistre les jobs APScheduler au démarrage du serveur.
"""
from __future__ import annotations

import asyncio
from database.db import SessionLocal

try:
    from core.tools.logger import get_logger
    logger = get_logger("sentinel.daemon")
except Exception:
    import logging
    logger = logging.getLogger(__name__)


def _db_job(fn, *args, **kwargs):
    """Exécute une fonction avec une session DB temporaire."""
    db = SessionLocal()
    try:
        fn(*args, db=db, **kwargs)
    except Exception as e:
        logger.debug("sentinel job %s: %s", fn.__name__, e)
    finally:
        db.close()


# ── Jobs ──────────────────────────────────────────────────────────────────────

def job_metrics():
    from core.monitor.metrics_collector import collect_metrics
    _db_job(collect_metrics)

def job_processes():
    from core.monitor.process_guardian import check_processes
    _db_job(check_processes)

def job_network():
    from core.monitor.network_sentinel import check_network
    _db_job(check_network)

def job_logs():
    from core.monitor.log_analyzer import analyze_logs
    _db_job(analyze_logs)

def job_integrity():
    from core.monitor.integrity_checker import check_integrity
    _db_job(check_integrity)

def job_ports():
    from core.monitor.port_sentinel import check_ports
    _db_job(check_ports)

def job_rules():
    from core.monitor.rules_engine import rules_engine
    from core.monitor.metrics_collector import collect_metrics
    db = SessionLocal()
    try:
        import psutil
        cpu   = psutil.cpu_percent(interval=0.1)
        ram   = psutil.virtual_memory().percent
        disk  = psutil.disk_usage("/").percent
        swap  = psutil.swap_memory().percent
        context = {"cpu_pct": cpu, "ram_pct": ram, "disk_pct": disk, "swap_pct": swap}
        rules_engine.apply_rules(context, db=db)
    except Exception as e:
        logger.debug("job_rules: %s", e)
    finally:
        db.close()

def job_baseline_init():
    """Initialise les baselines si elles n'existent pas encore."""
    db = SessionLocal()
    try:
        from database.models import MonitorBaseline
        existing = {r.baseline_type for r in db.query(MonitorBaseline).all()}

        if "processes" not in existing:
            from core.monitor.process_guardian import build_baseline
            build_baseline(db)

        if "ports" not in existing:
            from core.monitor.port_sentinel import build_baseline as bp
            bp(db)

        if "files" not in existing:
            from core.monitor.integrity_checker import build_baseline as bi
            bi(db)

        # Charger la whitelist réseau
        from core.monitor.network_sentinel import load_whitelist
        load_whitelist(db)

        # Charger les règles personnalisées
        from core.monitor.rules_engine import rules_engine
        rules_engine.load_rules(db)

        logger.info("sentinel: baselines initialisées")
    except Exception as e:
        logger.error("sentinel: erreur init baselines: %s", e)
    finally:
        db.close()


# ── Enregistrement des jobs ───────────────────────────────────────────────────

def register_sentinel_jobs(scheduler):
    """Enregistre tous les jobs de surveillance dans APScheduler."""

    jobs = [
        ("sentinel_metrics",    job_metrics,   30),    # toutes les 30s
        ("sentinel_network",    job_network,   15),    # toutes les 15s
        ("sentinel_logs",       job_logs,      20),    # toutes les 20s
        ("sentinel_processes",  job_processes, 60),    # toutes les 60s
        ("sentinel_ports",      job_ports,     60),    # toutes les 60s
        ("sentinel_rules",      job_rules,     30),    # toutes les 30s
        ("sentinel_integrity",  job_integrity, 600),   # toutes les 10 min
    ]

    for job_id, fn, interval_s in jobs:
        scheduler.add_job(
            fn,
            trigger="interval",
            seconds=interval_s,
            id=job_id,
            replace_existing=True,
            max_instances=1,
            misfire_grace_time=10,
        )

    # Initialisation des baselines (une fois au démarrage)
    scheduler.add_job(
        job_baseline_init,
        trigger="date",
        id="sentinel_baseline_init",
        replace_existing=True,
    )

    logger.info("sentinel: 7 jobs enregistrés (metrics·network·logs·processes·ports·rules·integrity)")


def set_event_loop(loop: asyncio.AbstractEventLoop):
    """Câble l'event loop asyncio dans le bus d'événements."""
    from core.monitor.event_bus import sentinel_bus
    sentinel_bus.set_loop(loop)
    logger.info("sentinel: event loop câblée")
