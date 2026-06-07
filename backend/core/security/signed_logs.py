"""
SignedLogChain — Chaîne de hachage pour l'intégrité des logs.

Chaque entrée contient le hash SHA256 du log précédent (blockchain légère).
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_CHAIN_FILE = Path("./data/log_chain.jsonl")
_GENESIS_HASH = "0" * 64


def _sha256(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


class SignedLogChain:
    """Chaîne de logs avec hash de chaque entrée incluant le hash précédent."""

    def __init__(self, chain_file: Optional[str] = None):
        self._file = Path(chain_file) if chain_file else _CHAIN_FILE
        self._file.parent.mkdir(parents=True, exist_ok=True)
        self._last_hash: str = self._load_last_hash()

    def _load_last_hash(self) -> str:
        if not self._file.exists():
            return _GENESIS_HASH
        try:
            lines = self._file.read_text("utf-8").strip().splitlines()
            if not lines:
                return _GENESIS_HASH
            last = json.loads(lines[-1])
            return last.get("current_hash", _GENESIS_HASH)
        except Exception:
            return _GENESIS_HASH

    async def append_log(
        self,
        action: str,
        data: dict,
        user_id: Optional[str] = None,
    ) -> str:
        """Ajoute un log signé. Retourne le hash courant."""
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "action": action,
            "user_id": user_id or "system",
            "data": data,
            "previous_hash": self._last_hash,
        }
        entry_str = json.dumps(entry, ensure_ascii=False, sort_keys=True)
        current_hash = _sha256(self._last_hash + entry_str)
        entry["current_hash"] = current_hash

        line = json.dumps(entry, ensure_ascii=False)
        with self._file.open("a", encoding="utf-8") as f:
            f.write(line + "\n")

        self._last_hash = current_hash
        return current_hash

    def append_log_sync(self, action: str, data: dict, user_id: Optional[str] = None) -> str:
        """Version synchrone pour les contextes non-async."""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Appel depuis un contexte async — utiliser create_task serait risqué ici
                # On écrit directement en sync
                return self._append_sync(action, data, user_id)
            return loop.run_until_complete(self.append_log(action, data, user_id))
        except RuntimeError:
            return self._append_sync(action, data, user_id)

    def _append_sync(self, action: str, data: dict, user_id: Optional[str] = None) -> str:
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "action": action,
            "user_id": user_id or "system",
            "data": data,
            "previous_hash": self._last_hash,
        }
        entry_str = json.dumps(entry, ensure_ascii=False, sort_keys=True)
        current_hash = _sha256(self._last_hash + entry_str)
        entry["current_hash"] = current_hash

        with self._file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        self._last_hash = current_hash
        return current_hash

    async def verify_chain(self) -> dict:
        """Vérifie l'intégrité de toute la chaîne."""
        if not self._file.exists():
            return {
                "valid": True,
                "total_logs": 0,
                "first_broken_index": None,
                "verified_at": datetime.utcnow().isoformat(),
                "message": "Chaîne vide",
            }

        lines = self._file.read_text("utf-8").strip().splitlines()
        if not lines:
            return {
                "valid": True,
                "total_logs": 0,
                "first_broken_index": None,
                "verified_at": datetime.utcnow().isoformat(),
            }

        prev_hash = _GENESIS_HASH
        for i, line in enumerate(lines):
            try:
                entry = json.loads(line)
                stored_prev = entry.get("previous_hash", "")
                stored_curr = entry.get("current_hash", "")

                if stored_prev != prev_hash:
                    return {
                        "valid": False,
                        "total_logs": len(lines),
                        "first_broken_index": i,
                        "verified_at": datetime.utcnow().isoformat(),
                        "message": f"Hash précédent incorrect à l'entrée {i}",
                    }

                # Recompute
                entry_copy = {k: v for k, v in entry.items() if k != "current_hash"}
                entry_str = json.dumps(entry_copy, ensure_ascii=False, sort_keys=True)
                expected_hash = _sha256(prev_hash + entry_str)

                if expected_hash != stored_curr:
                    return {
                        "valid": False,
                        "total_logs": len(lines),
                        "first_broken_index": i,
                        "verified_at": datetime.utcnow().isoformat(),
                        "message": f"Hash courant invalide à l'entrée {i}",
                    }

                prev_hash = stored_curr
            except Exception as e:
                return {
                    "valid": False,
                    "total_logs": len(lines),
                    "first_broken_index": i,
                    "verified_at": datetime.utcnow().isoformat(),
                    "message": f"Erreur parsing entrée {i}: {e}",
                }

        return {
            "valid": True,
            "total_logs": len(lines),
            "first_broken_index": None,
            "verified_at": datetime.utcnow().isoformat(),
            "last_hash": prev_hash,
        }

    async def export_proof(self, from_date: Optional[str] = None, to_date: Optional[str] = None) -> dict:
        """Exporte une preuve d'intégrité pour une période donnée."""
        if not self._file.exists():
            return {"logs": [], "total": 0, "verified": True}

        lines = self._file.read_text("utf-8").strip().splitlines()
        entries = []
        for line in lines:
            try:
                entry = json.loads(line)
                ts = entry.get("timestamp", "")
                if from_date and ts < from_date:
                    continue
                if to_date and ts > to_date:
                    continue
                entries.append(entry)
            except Exception:
                continue

        verify_result = await self.verify_chain()
        return {
            "logs": entries,
            "total": len(entries),
            "chain_valid": verify_result["valid"],
            "exported_at": datetime.utcnow().isoformat(),
            "from_date": from_date,
            "to_date": to_date,
        }

    async def get_recent(self, n: int = 50) -> list[dict]:
        """Retourne les n dernières entrées."""
        if not self._file.exists():
            return []
        lines = self._file.read_text("utf-8").strip().splitlines()
        result = []
        for line in lines[-n:]:
            try:
                result.append(json.loads(line))
            except Exception:
                pass
        return list(reversed(result))


signed_log_chain = SignedLogChain()
