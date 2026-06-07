"""
Indexeur d'historique bash — lit ~/.bash_history et indexe les nouvelles
commandes dans ChromaDB + BashCommandLog (SQLite).
Appelé toutes les 30 secondes par APScheduler.
"""
from __future__ import annotations

import os
import logging
from datetime import datetime
from pathlib import Path

try:
    from core.tools.logger import get_logger
    logger = get_logger("memory.bash_history")
except Exception:
    logger = logging.getLogger(__name__)

HISTORY_FILE = Path.home() / ".bash_history"
_MARKER_FILE = Path("/tmp/.eog_bash_history_pos")

_SKIP_PREFIXES = ("ls ", "pwd", "cd ", "clear", "history", "exit", "cat ")
_MIN_LEN = 5


def _read_new_commands() -> list[str]:
    if not HISTORY_FILE.exists():
        return []

    last_pos = 0
    if _MARKER_FILE.exists():
        try:
            last_pos = int(_MARKER_FILE.read_text().strip())
        except Exception:
            last_pos = 0

    try:
        with open(HISTORY_FILE, "r", errors="replace") as f:
            f.seek(last_pos)
            new_lines = f.readlines()
            new_pos = f.tell()
        _MARKER_FILE.write_text(str(new_pos))
    except Exception as e:
        logger.warning("bash_history: lecture échouée: %s", e)
        return []

    cmds = []
    for line in new_lines:
        cmd = line.strip()
        if len(cmd) >= _MIN_LEN and not any(cmd.startswith(p) for p in _SKIP_PREFIXES):
            cmds.append(cmd)
    return cmds


def index_new_commands(db=None):
    """Indexe les nouvelles commandes bash dans ChromaDB et SQLite."""
    from core.memory.vector_store import vector_store

    cmds = _read_new_commands()
    if not cmds:
        return 0

    indexed = 0
    for cmd in cmds:
        doc_id = f"bash_{abs(hash(cmd + datetime.utcnow().isoformat()))}"
        vector_store.add(
            text=f"[bash] {cmd}",
            metadata={
                "type": "bash",
                "command": cmd,
                "timestamp": datetime.utcnow().isoformat(),
            },
            doc_id=doc_id,
        )

        if db is not None:
            try:
                from database.models import BashCommandLog
                entry = BashCommandLog(
                    command=cmd,
                    cwd=os.getcwd(),
                    timestamp=datetime.utcnow(),
                    indexed=True,
                )
                db.add(entry)
            except Exception:
                pass

        indexed += 1

    if db is not None:
        try:
            db.commit()
        except Exception:
            pass

    if indexed:
        logger.info("bash_history: %d commande(s) indexée(s)", indexed)
    return indexed


def search_command_history(query: str, k: int = 5) -> list[dict]:
    """Recherche sémantique dans l'historique des commandes."""
    from core.memory.vector_store import vector_store
    results = vector_store.search(query, k=k * 3)
    bash_results = [r for r in results if r.get("metadata", {}).get("type") == "bash"]
    return bash_results[:k]
