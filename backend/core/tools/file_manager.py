import os
from pathlib import Path
from core.tools.logger import get_logger

logger = get_logger(__name__)

# Seul ce répertoire est accessible en lecture/écriture par les agents
SAFE_ROOT = Path("./data/user_files")
SAFE_ROOT.mkdir(parents=True, exist_ok=True)


class FileManager:
    def _safe_path(self, filename: str) -> Path:
        p = (SAFE_ROOT / filename).resolve()
        if not str(p).startswith(str(SAFE_ROOT.resolve())):
            raise PermissionError("Accès refusé : chemin hors de la zone sécurisée")
        return p

    def read(self, filename: str) -> str:
        p = self._safe_path(filename)
        return p.read_text(encoding="utf-8")

    def write(self, filename: str, content: str):
        p = self._safe_path(filename)
        p.write_text(content, encoding="utf-8")
        logger.info(f"Fichier écrit : {p}")

    def list(self) -> list:
        return [f.name for f in SAFE_ROOT.iterdir() if f.is_file()]

    def delete(self, filename: str) -> bool:
        p = self._safe_path(filename)
        if p.exists():
            p.unlink()
            logger.info(f"Fichier supprimé : {p}")
            return True
        return False


file_manager = FileManager()
