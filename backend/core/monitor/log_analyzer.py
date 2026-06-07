"""
Analyseur de logs en temps réel — tail sur syslog, auth.log, kern.log.
Détecte les patterns dangereux via regex.
"""
from __future__ import annotations

import os
import json
import re
from pathlib import Path
from datetime import datetime

try:
    from core.tools.logger import get_logger
    logger = get_logger("sentinel.logs")
except Exception:
    import logging
    logger = logging.getLogger(__name__)

# Fichiers de log à surveiller
_LOG_FILES = [
    Path("/var/log/syslog"),
    Path("/var/log/auth.log"),
    Path("/var/log/kern.log"),
    Path("/tmp/eog_backend.log"),
]

# Patterns dangereux
_PATTERNS = [
    (re.compile(r"Failed password for .+ from .+ port \d+", re.I), "AUTH", "HIGH",
     "Tentative de connexion SSH échouée"),
    (re.compile(r"authentication failure", re.I), "AUTH", "MEDIUM",
     "Échec d'authentification"),
    (re.compile(r"sudo:.+COMMAND=", re.I), "AUTH", "INFO",
     "Exécution sudo"),
    (re.compile(r"Invalid user .+ from", re.I), "AUTH", "HIGH",
     "Utilisateur SSH invalide"),
    (re.compile(r"segfault at", re.I), "SYSTEM", "HIGH",
     "Segfault détecté"),
    (re.compile(r"kernel panic", re.I), "SYSTEM", "CRITICAL",
     "Kernel panic"),
    (re.compile(r"Out of memory|OOM killer", re.I), "SYSTEM", "HIGH",
     "Manque de mémoire — OOM killer"),
    (re.compile(r"permission denied", re.I), "AUTH", "MEDIUM",
     "Accès refusé"),
    (re.compile(r"Connection refused", re.I), "NETWORK", "INFO",
     "Connexion refusée"),
    (re.compile(r"Accepted (password|publickey) for .+ from", re.I), "AUTH", "INFO",
     "Connexion SSH acceptée"),
    (re.compile(r"error|ERROR", re.IGNORECASE), "SYSTEM", "LOW",
     "Erreur applicative"),
    (re.compile(r"CRITICAL|FATAL", re.IGNORECASE), "SYSTEM", "HIGH",
     "Événement critique applicatif"),
    (re.compile(r"reverse shell|nc -e|bash -i|/dev/tcp", re.I), "SYSTEM", "CRITICAL",
     "Tentative reverse shell détectée"),
    (re.compile(r"nmap|masscan|hydra|john|hashcat", re.I), "SYSTEM", "HIGH",
     "Outil d'attaque détecté dans les logs"),
]

# Marqueurs de position (chemin → offset)
_OFFSETS: dict[str, int] = {}


def analyze_logs(db=None):
    """Lit les nouvelles lignes de chaque log et analyse les patterns."""
    for log_path in _LOG_FILES:
        if not log_path.exists():
            continue
        _analyze_file(log_path, db)


def _analyze_file(path: Path, db):
    key = str(path)
    try:
        size = path.stat().st_size
    except Exception:
        return

    # Initialiser ou détecter rotation
    prev = _OFFSETS.get(key, size)
    if size < prev:
        prev = 0  # rotation
    _OFFSETS[key] = size

    if prev == size:
        return  # rien de nouveau

    try:
        with open(path, "r", errors="replace") as f:
            f.seek(prev)
            lines = f.readlines()
            _OFFSETS[key] = f.tell()
    except Exception:
        return

    for line in lines[-500:]:  # max 500 nouvelles lignes
        line = line.strip()
        if not line:
            continue
        for pat, category, severity, label in _PATTERNS:
            if pat.search(line):
                _fire(
                    category=category, severity=severity,
                    title=f"{label} [{path.name}]",
                    description=line[:300],
                    details={"log_file": str(path), "line": line[:500]},
                    db=db,
                )
                break  # une seule alerte par ligne


def _fire(category, severity, title, description, details=None, db=None):
    from core.monitor.event_bus import sentinel_bus
    sentinel_bus.publish({
        "type": "security_event",
        "category": category, "severity": severity,
        "title": title, "description": description,
        "details": details or {},
    })
    if db is not None and severity in ("HIGH", "CRITICAL", "MEDIUM"):
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
