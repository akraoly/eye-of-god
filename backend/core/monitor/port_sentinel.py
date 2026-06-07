"""
Sentinelle des ports — compare les ports ouverts avec la baseline.
Détecte : nouveau port ouvert, service critique arrêté.
"""
from __future__ import annotations

import json
from datetime import datetime

import psutil

try:
    from core.tools.logger import get_logger
    logger = get_logger("sentinel.ports")
except Exception:
    import logging
    logger = logging.getLogger(__name__)

# Services critiques à surveiller
_CRITICAL_SERVICES = [
    {"name": "backend FastAPI", "port": 8001, "host": "127.0.0.1"},
]

# Ports légitimes attendus sur une machine de dev/kali
_EXPECTED_PORTS = {22, 80, 443, 8001, 8080, 3000, 3001, 5432, 3306, 6379}


def _get_listening_ports() -> set[int]:
    ports = set()
    try:
        for c in psutil.net_connections(kind='inet'):
            if c.status == 'LISTEN' and c.laddr:
                ports.add(c.laddr.port)
    except Exception:
        pass
    return ports


def build_baseline(db) -> set[int]:
    ports = _get_listening_ports()
    data = json.dumps(sorted(ports))
    try:
        from database.models import MonitorBaseline
        existing = db.query(MonitorBaseline).filter(MonitorBaseline.baseline_type == "ports").first()
        if existing:
            existing.data = data
            existing.updated_at = datetime.utcnow()
        else:
            row = MonitorBaseline(baseline_type="ports", data=data)
            db.add(row)
        db.commit()
        logger.info("port_sentinel: baseline établie (%d ports)", len(ports))
    except Exception as e:
        logger.error("port_sentinel: erreur baseline: %s", e)
    return ports


def _load_baseline(db) -> set[int]:
    try:
        from database.models import MonitorBaseline
        row = db.query(MonitorBaseline).filter(MonitorBaseline.baseline_type == "ports").first()
        if row:
            return set(json.loads(row.data))
    except Exception:
        pass
    return set()


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
    logger.warning("[PORT] %s — %s", severity, title)


def check_ports(db=None):
    baseline = _load_baseline(db)
    if not baseline:
        if db is not None:
            build_baseline(db)
        return

    current = _get_listening_ports()
    new_ports = current - baseline

    for port in new_ports:
        if port in _EXPECTED_PORTS:
            continue
        severity = "HIGH" if port < 1024 or port in {4444, 31337, 1337} else "MEDIUM"
        _fire(
            category="PORT", severity=severity,
            title=f"Nouveau port ouvert : {port}",
            description=f"Le port {port} n'était pas dans la baseline. Possible backdoor ou service non autorisé.",
            details={"port": port, "new_ports": list(new_ports)},
            db=db,
        )

    # Vérifier les services critiques
    for svc in _CRITICAL_SERVICES:
        if svc["port"] not in current:
            _fire(
                category="PORT", severity="HIGH",
                title=f"Service critique arrêté : {svc['name']} (port {svc['port']})",
                description=f"Le service {svc['name']} n'est plus accessible sur le port {svc['port']}.",
                details=svc,
                db=db,
            )


def get_ports_status() -> dict:
    current = _get_listening_ports()
    services = []
    for svc in _CRITICAL_SERVICES:
        services.append({
            **svc,
            "running": svc["port"] in current,
        })
    return {
        "listening_ports": sorted(current),
        "count": len(current),
        "services": services,
    }
