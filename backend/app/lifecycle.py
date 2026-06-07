from database.db import init_db, SessionLocal
from database.models import AppUser, ScheduledTask
from core.auth.password import hash_password
from app.config import settings
from core.tools.logger import get_logger

logger = get_logger("lifecycle")


def _migrate_db():
    """Migrations SQLite légères — ajoute les colonnes manquantes sans supprimer."""
    from database.db import engine
    import sqlalchemy as sa
    migrations = [
        ("app_users", "email",        "VARCHAR(255)"),
        ("app_users", "role",         "VARCHAR(50) DEFAULT 'admin'"),
        ("app_users", "organization", "VARCHAR(255)"),
        ("app_users", "permissions",  "TEXT"),
    ]
    with engine.connect() as conn:
        for table, col, col_type in migrations:
            try:
                conn.execute(sa.text(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}"))
                conn.commit()
                logger.info("Migration: ajout colonne %s.%s", table, col)
            except Exception:
                pass  # Colonne déjà existante


def _ensure_admin():
    db = SessionLocal()
    try:
        if db.query(AppUser).count() == 0:
            admin = AppUser(
                username=settings.DEFAULT_ADMIN_USERNAME,
                display_name="Administrateur",
                password_hash=hash_password(settings.DEFAULT_ADMIN_PASSWORD),
            )
            db.add(admin)
            db.commit()
            logger.info(f"Compte admin créé — login: {settings.DEFAULT_ADMIN_USERNAME}")
    finally:
        db.close()


def _start_scheduler():
    from core.autonomy.scheduler import start_scheduler, schedule_task, get_scheduler
    from core.autonomy.monitors import register_monitors
    start_scheduler()
    register_monitors(get_scheduler())
    # Recharger les tâches persistées activées
    db = SessionLocal()
    try:
        tasks = db.query(ScheduledTask).filter(ScheduledTask.enabled == True).all()
        for t in tasks:
            try:
                schedule_task(t.__dict__ | {"id": t.id})
            except Exception as e:
                logger.warning(f"Impossible de recharger la tâche {t.id}: {e}")
        if tasks:
            logger.info(f"{len(tasks)} tâche(s) rechargée(s)")
    finally:
        db.close()


def _stop_scheduler():
    from core.autonomy.scheduler import stop_scheduler
    stop_scheduler()


async def _start_network_monitor():
    import asyncio
    from core.network.monitor import network_monitor
    asyncio.create_task(network_monitor.run())
    logger.info("Moniteur réseau démarré")


def _start_memory_workers():
    """Démarre le watcher filesystem + planifie l'indexeur bash history."""
    # Filesystem watcher (watchdog thread)
    try:
        from core.memory.watcher import file_watcher
        file_watcher.start()
    except Exception as e:
        logger.warning("Watcher filesystem: %s", e)

    # Bash history indexer — toutes les 30 secondes via APScheduler
    try:
        from core.autonomy.scheduler import get_scheduler
        from core.memory.bash_history import index_new_commands

        scheduler = get_scheduler()
        if scheduler:
            scheduler.add_job(
                _bash_history_job,
                trigger="interval",
                seconds=30,
                id="bash_history_indexer",
                replace_existing=True,
                misfire_grace_time=10,
            )
            logger.info("Indexeur bash history planifié (30s)")
    except Exception as e:
        logger.warning("Bash history scheduler: %s", e)

    # Session summarizer — vérifie les sessions inactives toutes les 10 minutes
    try:
        from core.autonomy.scheduler import get_scheduler
        scheduler = get_scheduler()
        if scheduler:
            scheduler.add_job(
                _session_summarizer_job,
                trigger="interval",
                minutes=10,
                id="session_summarizer",
                replace_existing=True,
                misfire_grace_time=60,
            )
            logger.info("Résumeur de sessions planifié (10min)")
    except Exception as e:
        logger.warning("Session summarizer scheduler: %s", e)


def _bash_history_job():
    """Job APScheduler — indexe les nouvelles commandes bash."""
    try:
        from core.memory.bash_history import index_new_commands
        db = SessionLocal()
        try:
            n = index_new_commands(db=db)
            if n:
                logger.debug("bash_history: %d commande(s) indexée(s)", n)
        finally:
            db.close()
    except Exception as e:
        logger.debug("bash_history job: %s", e)


def _start_sentinel():
    """Démarre le daemon Sentinel — surveillance système temps réel."""
    try:
        from core.autonomy.scheduler import get_scheduler
        from core.monitor.daemon import register_sentinel_jobs, set_event_loop
        import asyncio

        scheduler = get_scheduler()
        if scheduler:
            register_sentinel_jobs(scheduler)
            # Câbler l'event loop pour les WebSocket pushes
            try:
                loop = asyncio.get_event_loop()
                set_event_loop(loop)
            except Exception:
                pass
    except Exception as e:
        logger.warning("Sentinel: démarrage échoué: %s", e)


def _start_aegis():
    """Démarre les jobs AEGIS — veille CVE, exploits, recon, rapports."""
    try:
        from core.autonomy.scheduler import get_scheduler
        from core.aegis.daemon import register_aegis_jobs
        scheduler = get_scheduler()
        if scheduler:
            register_aegis_jobs(scheduler)
    except Exception as e:
        logger.warning("AEGIS: démarrage échoué: %s", e)


def _preload_voice_models():
    """Précharge le modèle Whisper en arrière-plan (non-bloquant)."""
    try:
        from core.voice.stt import preload_model
        preload_model()
        logger.info("Voice: préchargement Whisper lancé en arrière-plan")
    except Exception as e:
        logger.debug("Voice: préchargement optionnel: %s", e)


def _session_summarizer_job():
    """Job APScheduler — résume les sessions inactives (> 1h)."""
    try:
        import asyncio
        from core.memory.working_memory import working_memory
        from core.memory.episodic import episodic_memory

        timed_out = working_memory.get_timed_out_sessions()
        for session_id in timed_out:
            db = SessionLocal()
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(
                        episodic_memory.summarize_and_close(db=db, session_id=session_id)
                    )
                finally:
                    loop.close()
                working_memory.close_session(session_id)
                logger.info("Session '%s' résumée et fermée", session_id)
            except Exception as e:
                logger.debug("session summarizer: %s", e)
            finally:
                db.close()
    except Exception as e:
        logger.debug("session_summarizer job: %s", e)


async def startup():
    logger.info("=" * 50)
    logger.info("L'Œil de Dieu — démarrage...")
    init_db()
    _migrate_db()
    logger.info("Base de données initialisée")
    _ensure_admin()
    _start_scheduler()
    await _start_network_monitor()
    _start_memory_workers()
    _start_sentinel()
    _start_aegis()
    _preload_voice_models()
    logger.info("Système prêt")
    logger.info("=" * 50)


async def shutdown():
    from core.network.monitor import network_monitor
    network_monitor.stop()
    _stop_scheduler()
    try:
        from core.memory.watcher import file_watcher
        file_watcher.stop()
    except Exception:
        pass
    logger.info("L'Œil de Dieu — arrêt propre")
