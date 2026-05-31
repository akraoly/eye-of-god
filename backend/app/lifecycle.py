from database.db import init_db
from core.tools.logger import get_logger

logger = get_logger("lifecycle")


async def startup():
    logger.info("=" * 50)
    logger.info("L'Œil de Dieu — démarrage...")
    init_db()
    logger.info("Base de données initialisée")
    logger.info("Système prêt")
    logger.info("=" * 50)


async def shutdown():
    logger.info("L'Œil de Dieu — arrêt propre")
