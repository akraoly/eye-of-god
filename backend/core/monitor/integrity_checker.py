"""
Vérificateur d'intégrité des fichiers — baseline SHA256.
Vérifie toutes les 10 minutes. Alerte sur toute modification non attendue.
"""
from __future__ import annotations

import json
import hashlib
import os
from datetime import datetime
from pathlib import Path

try:
    from core.tools.logger import get_logger
    logger = get_logger("sentinel.integrity")
except Exception:
    import logging
    logger = logging.getLogger(__name__)

# Fichiers/répertoires à surveiller
_WATCHED_PATHS = [
    # Binaires critiques
    Path("/usr/bin/python3"),
    Path("/usr/bin/ssh"),
    Path("/usr/bin/sudo"),
    Path("/usr/bin/su"),
    Path("/bin/bash"),
    Path("/bin/sh"),
    # Config système
    Path("/etc/passwd"),
    Path("/etc/shadow"),
    Path("/etc/sudoers"),
    Path("/etc/hosts"),
    Path("/etc/ssh/sshd_config"),
    # Projet L'Œil de Dieu — fichiers core
    Path("/home/kali/eye-of-god/backend/app/lifecycle.py"),
    Path("/home/kali/eye-of-god/backend/app/main.py"),
    Path("/home/kali/eye-of-god/backend/api/router.py"),
    Path("/home/kali/eye-of-god/backend/core/auth/jwt_handler.py"),
]

_MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB


def _sha256(path: Path) -> str | None:
    try:
        if path.stat().st_size > _MAX_FILE_SIZE:
            return f"LARGE:{path.stat().st_size}"
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return None


def build_baseline(db):
    """Calcule et stocke le hash SHA256 de tous les fichiers surveillés."""
    hashes = {}
    for path in _WATCHED_PATHS:
        if path.exists():
            h = _sha256(path)
            if h:
                hashes[str(path)] = {"hash": h, "mtime": path.stat().st_mtime}

    data = json.dumps(hashes)
    try:
        from database.models import MonitorBaseline
        existing = db.query(MonitorBaseline).filter(MonitorBaseline.baseline_type == "files").first()
        if existing:
            existing.data = data
            existing.updated_at = datetime.utcnow()
        else:
            row = MonitorBaseline(baseline_type="files", data=data)
            db.add(row)
        db.commit()
        logger.info("integrity_checker: baseline établie (%d fichiers)", len(hashes))
    except Exception as e:
        logger.error("integrity_checker: erreur baseline: %s", e)
    return hashes


def _load_baseline(db) -> dict:
    try:
        from database.models import MonitorBaseline
        row = db.query(MonitorBaseline).filter(MonitorBaseline.baseline_type == "files").first()
        if row:
            return json.loads(row.data)
    except Exception:
        pass
    return {}


def _fire(category, severity, title, description, details=None, db=None):
    from core.monitor.event_bus import sentinel_bus
    sentinel_bus.publish({
        "type": "security_event",
        "category": category, "severity": severity,
        "title": title, "description": description,
        "details": details or {},
    })
    if db is not None:
        try:
            from database.models import SecurityEventLog
            row = SecurityEventLog(
                category=category, severity=severity,
                title=title, description=description,
                details=json.dumps(details or {}),
            )
            db.add(row)
            db.commit()
        except Exception:
            pass
    logger.warning("[INTEGRITY] %s — %s", severity, title)


def check_integrity(db=None):
    """Compare les hashes actuels avec la baseline. Alerte si différence."""
    baseline = _load_baseline(db)
    if not baseline:
        if db is not None:
            build_baseline(db)
        return

    for path in _WATCHED_PATHS:
        path_str = str(path)
        if not path.exists():
            if path_str in baseline:
                _fire(
                    category="FILE", severity="HIGH",
                    title=f"Fichier critique supprimé : {path.name}",
                    description=f"Le fichier {path_str} a été supprimé.",
                    details={"path": path_str},
                    db=db,
                )
            continue

        current_hash = _sha256(path)
        if not current_hash:
            continue

        if path_str in baseline:
            old_hash = baseline[path_str]["hash"]
            if current_hash != old_hash:
                _fire(
                    category="FILE", severity="CRITICAL",
                    title=f"Modification non autorisée : {path.name}",
                    description=f"Le fichier {path_str} a été modifié depuis la baseline. Possible tampering ou rootkit.",
                    details={"path": path_str, "old_hash": old_hash[:16] + "...", "new_hash": current_hash[:16] + "..."},
                    db=db,
                )
        else:
            # Nouveau fichier non connu — mettre à jour la baseline
            baseline[path_str] = {"hash": current_hash, "mtime": path.stat().st_mtime}


def get_integrity_status(db) -> dict:
    baseline = _load_baseline(db)
    results = []
    for path in _WATCHED_PATHS:
        path_str = str(path)
        exists = path.exists()
        current_hash = _sha256(path) if exists else None
        base_entry = baseline.get(path_str, {})
        ok = current_hash == base_entry.get("hash") if current_hash and base_entry else exists
        results.append({
            "path": path_str,
            "name": path.name,
            "exists": exists,
            "ok": ok,
            "modified": not ok and exists and bool(base_entry),
        })
    return {
        "total": len(results),
        "ok": sum(1 for r in results if r["ok"]),
        "modified": sum(1 for r in results if r["modified"]),
        "missing": sum(1 for r in results if not r["exists"]),
        "files": results,
    }
