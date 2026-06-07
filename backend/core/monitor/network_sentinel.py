"""
Sentinelle réseau — détection de connexions suspectes, reverse shells,
exfiltration. Complète le NetworkMonitor existant avec whitelist persistante.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

import psutil

try:
    from core.tools.logger import get_logger
    logger = get_logger("sentinel.network")
except Exception:
    import logging
    logger = logging.getLogger(__name__)

_PRIVATE_PREFIXES = (
    '10.', '192.168.', '172.16.', '172.17.', '172.18.', '172.19.',
    '172.20.', '172.21.', '172.22.', '172.23.', '172.24.', '172.25.',
    '172.26.', '172.27.', '172.28.', '172.29.', '172.30.', '172.31.',
    '127.', '::1', 'localhost', '0.0.0.0',
)

_REVERSE_SHELL_PORTS = {4444, 4445, 1337, 6666, 6667, 9999, 31337, 8888, 1234, 54321}
_EXFIL_PORTS_SUSPECT = {21, 69, 6881, 6882}   # FTP, TFTP, BitTorrent

# Whitelist des IPs/ports légitimes (persistée en DB)
_WHITELIST: set[str] = set()
_SEEN_CONNS: set[tuple] = set()


def load_whitelist(db):
    """Charge la whitelist depuis la DB."""
    global _WHITELIST
    try:
        from database.models import MonitorBaseline
        row = db.query(MonitorBaseline).filter(MonitorBaseline.baseline_type == "network_whitelist").first()
        if row:
            _WHITELIST = set(json.loads(row.data))
    except Exception:
        pass


def add_to_whitelist(db, entry: str):
    """Ajoute une IP ou IP:port à la whitelist."""
    global _WHITELIST
    _WHITELIST.add(entry)
    _save_whitelist(db)


def _save_whitelist(db):
    try:
        from database.models import MonitorBaseline
        data = json.dumps(sorted(_WHITELIST))
        existing = db.query(MonitorBaseline).filter(MonitorBaseline.baseline_type == "network_whitelist").first()
        if existing:
            existing.data = data
            existing.updated_at = datetime.utcnow()
        else:
            row = MonitorBaseline(baseline_type="network_whitelist", data=data)
            db.add(row)
        db.commit()
    except Exception:
        pass


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
    logger.warning("[NETWORK] %s — %s", severity, title)


def check_network(db=None):
    """Analyse les connexions actives — détecte reverse shells et exfiltration."""
    global _SEEN_CONNS

    try:
        conns = psutil.net_connections(kind='inet')
    except Exception:
        return

    current: set[tuple] = set()

    for c in conns:
        if not c.raddr or not c.raddr.ip:
            continue
        if c.status not in ('ESTABLISHED', 'SYN_SENT'):
            continue

        rip = c.raddr.ip
        rport = c.raddr.port
        key = (rip, rport)
        current.add(key)

        if key in _SEEN_CONNS:
            continue  # déjà vue

        is_private = any(rip.startswith(p) for p in _PRIVATE_PREFIXES)
        is_whitelisted = (rip in _WHITELIST or f"{rip}:{rport}" in _WHITELIST)

        if is_whitelisted:
            continue

        # Reverse shell
        if rport in _REVERSE_SHELL_PORTS and not is_private:
            _fire(
                category="NETWORK", severity="CRITICAL",
                title=f"Possible reverse shell vers {rip}:{rport}",
                description=f"Connexion sortante vers un port connu C2/backdoor : {rip}:{rport}",
                details={"rip": rip, "rport": rport, "pid": c.pid},
                db=db,
            )
        # Exfiltration possible
        elif rport in _EXFIL_PORTS_SUSPECT and not is_private:
            _fire(
                category="NETWORK", severity="HIGH",
                title=f"Possible exfiltration via port {rport} vers {rip}",
                description=f"Connexion sortante vers port suspect (FTP/TFTP/BitTorrent) : {rip}:{rport}",
                details={"rip": rip, "rport": rport},
                db=db,
            )
        # Nouvelle connexion externe inconnue
        elif not is_private and not is_whitelisted:
            _fire(
                category="NETWORK", severity="LOW",
                title=f"Nouvelle connexion externe : {rip}:{rport}",
                description=f"Connexion sortante vers IP externe inconnue. Ajoutez à la whitelist si légitime.",
                details={"rip": rip, "rport": rport, "pid": c.pid},
                db=db,
            )

    _SEEN_CONNS = current
