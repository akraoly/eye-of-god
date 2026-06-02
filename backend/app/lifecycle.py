from database.db import init_db, SessionLocal
from database.models import AppUser, ScheduledTask
from core.auth.password import hash_password
from app.config import settings
from core.tools.logger import get_logger

logger = get_logger("lifecycle")


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


async def startup():
    logger.info("=" * 50)
    logger.info("L'Œil de Dieu — démarrage...")
    init_db()
    logger.info("Base de données initialisée")
    _ensure_admin()
    _start_scheduler()
    logger.info("Système prêt")
    logger.info("=" * 50)


async def shutdown():
    _stop_scheduler()
    logger.info("L'Œil de Dieu — arrêt propre")
