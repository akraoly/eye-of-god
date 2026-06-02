from database.db import init_db, SessionLocal
from database.models import AppUser
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


async def startup():
    logger.info("=" * 50)
    logger.info("L'Œil de Dieu — démarrage...")
    init_db()
    logger.info("Base de données initialisée")
    _ensure_admin()
    logger.info("Système prêt")
    logger.info("=" * 50)


async def shutdown():
    logger.info("L'Œil de Dieu — arrêt propre")
