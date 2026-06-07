"""
AEGIS Daemon — Jobs APScheduler pour la collecte automatique.
- CVE NVD : toutes les heures
- Exploits GitHub : toutes les 2h
- Recon passive cibles : toutes les 6h
- Rapport hebdomadaire : dimanche 09:00
"""
from __future__ import annotations

from database.db import SessionLocal

try:
    from core.tools.logger import get_logger
    logger = get_logger("aegis.daemon")
except Exception:
    import logging
    logger = logging.getLogger(__name__)


def _get_config() -> dict:
    """Lit la config AEGIS depuis l'env ou les valeurs par défaut."""
    import os
    return {
        "nvd_key":        os.getenv("AEGIS_NVD_KEY", ""),
        "github_token":   os.getenv("AEGIS_GITHUB_TOKEN", ""),
        "cvss_threshold": float(os.getenv("AEGIS_CVSS_THRESHOLD", "9.0")),
    }


# ── Jobs ──────────────────────────────────────────────────────────────────────

def job_collect_cves():
    """Collecte les CVE NVD + CISA KEV."""
    cfg = _get_config()
    db = SessionLocal()
    try:
        from core.aegis.nvd_collector import (
            fetch_nvd_recent, fetch_cisa_kev, ingest_cves, correlate_with_projects
        )
        from database.models import AegisCVE

        # NVD — dernière heure
        nvd_cves = fetch_nvd_recent(days=1, api_key=cfg["nvd_key"])
        added, alerts = ingest_cves(db, nvd_cves, cvss_threshold=cfg["cvss_threshold"])

        # Corrélation projets pour les nouveaux CVE critiques
        crits = db.query(AegisCVE).filter(
            AegisCVE.affects_project == False,
            AegisCVE.cvss_score >= cfg["cvss_threshold"],
        ).limit(20).all()
        for cve in crits:
            if correlate_with_projects(db, cve):
                cve.affects_project = True
        db.commit()

        # CISA KEV (moins fréquent — on ignore si pas de token NVD pour éviter le flood)
        if cfg["nvd_key"] and added == 0:
            kev = fetch_cisa_kev()
            ingest_cves(db, kev, cvss_threshold=cfg["cvss_threshold"])

        logger.info("aegis.job_cves: %d ajoutés, %d alertes", added, alerts)
    except Exception as e:
        logger.error("aegis.job_cves error: %s", e)
    finally:
        db.close()


def job_watch_exploits():
    """Surveille les nouveaux exploits sur GitHub."""
    cfg = _get_config()
    if not cfg["github_token"]:
        logger.debug("aegis.exploits: pas de token GitHub, skip")
        return
    db = SessionLocal()
    try:
        from core.aegis.exploit_watcher import search_exploit_repos, ingest_exploits
        repos = search_exploit_repos(days=1, token=cfg["github_token"])
        added = ingest_exploits(db, repos)
        logger.info("aegis.job_exploits: %d exploit(s) ajouté(s)", added)
    except Exception as e:
        logger.error("aegis.job_exploits error: %s", e)
    finally:
        db.close()


def job_passive_recon():
    """Reconnaissance passive sur toutes les cibles autorisées actives."""
    db = SessionLocal()
    try:
        from database.models import AegisTarget
        from core.aegis.target_sentinel import run_passive_recon
        targets = db.query(AegisTarget).filter(
            AegisTarget.active == True,
            AegisTarget.authorization_confirmed == True,
        ).all()
        for t in targets:
            run_passive_recon(db, t.target_id)
        logger.info("aegis.recon: %d cible(s) vérifiée(s)", len(targets))
    except Exception as e:
        logger.error("aegis.job_recon error: %s", e)
    finally:
        db.close()


def job_weekly_report():
    """Génère le rapport de veille hebdomadaire (dimanche 09:00)."""
    import asyncio
    db = SessionLocal()
    try:
        from core.aegis.report_generator import generate_weekly_report
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(generate_weekly_report(db))
        finally:
            loop.close()
        logger.info("aegis: rapport hebdomadaire généré")
    except Exception as e:
        logger.error("aegis.job_report error: %s", e)
    finally:
        db.close()


# ── Enregistrement des jobs ───────────────────────────────────────────────────

def register_aegis_jobs(scheduler):
    """Enregistre tous les jobs AEGIS dans APScheduler."""
    jobs = [
        # id, fonction, type, kwargs
        ("aegis_cve_collect",  job_collect_cves,   "interval", {"hours": 1}),
        ("aegis_exploit_watch",job_watch_exploits, "interval", {"hours": 2}),
        ("aegis_recon",        job_passive_recon,  "interval", {"hours": 6}),
    ]
    for job_id, fn, trigger, kwargs in jobs:
        scheduler.add_job(
            fn, trigger=trigger, id=job_id,
            replace_existing=True, max_instances=1,
            misfire_grace_time=120,
            **kwargs,
        )

    # Rapport hebdomadaire : dimanche 09:00
    scheduler.add_job(
        job_weekly_report,
        trigger="cron",
        day_of_week="sun",
        hour=9, minute=0,
        id="aegis_weekly_report",
        replace_existing=True,
    )

    # Collecte initiale au démarrage (une seule fois)
    scheduler.add_job(
        job_collect_cves,
        trigger="date",
        id="aegis_initial_collect",
        replace_existing=True,
    )

    logger.info("aegis: 4 jobs enregistrés (CVE·exploits·recon·rapport)")
