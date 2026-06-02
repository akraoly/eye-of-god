from pathlib import Path
from pydantic_settings import BaseSettings
from typing import List

# .env est à la racine du projet (un niveau au-dessus de backend/)
_ENV_FILE = Path(__file__).parent.parent.parent / ".env"


class Settings(BaseSettings):
    # Claude API
    ANTHROPIC_API_KEY: str = ""
    CLAUDE_MODEL: str = "claude-sonnet-4-6"
    CLAUDE_MAX_TOKENS: int = 4096

    # App
    APP_NAME: str = "L'Œil de Dieu"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    HOST: str = "0.0.0.0"
    PORT: int = 8001

    # Database
    DATABASE_URL: str = "sqlite:///./data/memory.db"

    # Memory
    SHORT_TERM_LIMIT: int = 20
    USER_MEMORY_LIMIT: int = 100

    # Vector store (v1.1)
    CHROMA_DIR: str = "./data/chroma"
    VECTOR_SEARCH_K: int = 8
    SUMMARY_THRESHOLD: int = 50   # résume après N échanges
    SUMMARY_BATCH: int = 20       # nombre d'échanges résumés à la fois

    # Auth JWT
    JWT_SECRET: str = "change-me-in-production-use-a-long-random-string"
    JWT_EXPIRE_HOURS: int = 24
    DEFAULT_ADMIN_USERNAME: str = "admin"
    DEFAULT_ADMIN_PASSWORD: str = "oeil2026"

    # CORS
    ALLOWED_ORIGINS: str = "http://localhost:3001,http://localhost:3000"

    @property
    def origins_list(self) -> List[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",")]

    model_config = {"env_file": str(_ENV_FILE)}


settings = Settings()
