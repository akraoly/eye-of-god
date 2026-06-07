"""
Watcher filesystem — surveille les répertoires clés et indexe automatiquement
les fichiers créés ou modifiés dans ChromaDB.
Utilise watchdog. Démarré en thread via lifecycle.py.
"""
from __future__ import annotations

import os
import logging
import threading
from pathlib import Path
from datetime import datetime
from typing import Optional

try:
    from core.tools.logger import get_logger
    logger = get_logger("memory.watcher")
except Exception:
    logger = logging.getLogger(__name__)

WATCH_DIRS = [
    Path.home() / "eye-of-god",
    Path.home() / "Desktop",
    Path.home() / "Downloads",
    Path.home() / "Documents",
]

TEXT_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".md", ".txt", ".json",
    ".yaml", ".yml", ".sh", ".html", ".css", ".sql", ".conf",
    ".env", ".toml", ".ini", ".log",
}
MAX_FILE_SIZE = 100 * 1024  # 100 KB

_IGNORE_DIRS = {
    "__pycache__", ".git", "node_modules", ".venv", "venv",
    "dist", "build", ".cache", "chroma", "data",
}


def _should_index(path: Path) -> bool:
    if path.suffix.lower() not in TEXT_EXTENSIONS:
        return False
    if path.stat().st_size > MAX_FILE_SIZE:
        return False
    for part in path.parts:
        if part in _IGNORE_DIRS:
            return False
    return True


def _index_file(path: Path):
    try:
        content = path.read_text(errors="replace")
        if not content.strip():
            return
        from core.memory.vector_store import vector_store
        doc_id = f"file_{abs(hash(str(path)))}"
        vector_store.add(
            text=f"[fichier {path.name}]\n{content[:3000]}",
            metadata={
                "type": "file",
                "path": str(path),
                "name": path.name,
                "extension": path.suffix,
                "timestamp": datetime.utcnow().isoformat(),
            },
            doc_id=doc_id,
        )
        logger.debug("watcher: indexé %s", path)
    except Exception as e:
        logger.debug("watcher: impossible d'indexer %s: %s", path, e)


class _MemoryEventHandler:
    def __init__(self):
        try:
            from watchdog.events import FileSystemEventHandler
            self._base = FileSystemEventHandler
        except ImportError:
            self._base = object

    def dispatch(self, event):
        if event.is_directory:
            return
        path = Path(event.src_path)
        if _should_index(path):
            _index_file(path)


class FileWatcher:
    def __init__(self):
        self._observer: Optional[object] = None
        self._running = False

    def start(self):
        try:
            from watchdog.observers import Observer
            from watchdog.events import FileSystemEventHandler

            class _Handler(FileSystemEventHandler):
                def on_created(self, event):
                    if not event.is_directory:
                        p = Path(event.src_path)
                        if _should_index(p):
                            _index_file(p)

                def on_modified(self, event):
                    if not event.is_directory:
                        p = Path(event.src_path)
                        if _should_index(p):
                            _index_file(p)

            self._observer = Observer()
            handler = _Handler()

            watched = 0
            for d in WATCH_DIRS:
                if d.exists():
                    self._observer.schedule(handler, str(d), recursive=True)
                    watched += 1
                    logger.info("watcher: surveille %s", d)

            if watched == 0:
                logger.warning("watcher: aucun répertoire à surveiller n'existe")
                return

            self._observer.start()
            self._running = True
            logger.info("watcher: démarré (%d répertoire(s))", watched)

        except ImportError:
            logger.warning("watcher: watchdog non disponible, désactivé")
        except Exception as e:
            logger.error("watcher: erreur démarrage: %s", e)

    def stop(self):
        if self._observer and self._running:
            try:
                self._observer.stop()
                self._observer.join(timeout=5)
            except Exception:
                pass
            self._running = False
            logger.info("watcher: arrêté")

    def is_running(self) -> bool:
        return self._running


file_watcher = FileWatcher()
