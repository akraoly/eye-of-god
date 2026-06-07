"""
Moteur de règles personnalisées — applique les règles JSON définies par Mr Vitch.
Règles dynamiques sans redémarrage du serveur.
"""
from __future__ import annotations

import json
import re
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

try:
    from core.tools.logger import get_logger
    logger = get_logger("sentinel.rules")
except Exception:
    import logging
    logger = logging.getLogger(__name__)


class RulesEngine:
    def __init__(self):
        self._rules: list[dict] = []

    def load_rules(self, db):
        """Charge les règles actives depuis la DB."""
        try:
            from database.models import CustomMonitorRule
            rows = db.query(CustomMonitorRule).filter(CustomMonitorRule.enabled == True).all()
            self._rules = [
                {
                    "id": r.rule_id,
                    "name": r.name,
                    "rule_type": r.rule_type,
                    "condition": json.loads(r.condition),
                    "action": r.action,
                }
                for r in rows
            ]
        except Exception as e:
            logger.debug("rules_engine: erreur chargement: %s", e)

    def apply_rules(self, context: dict, db=None):
        """Applique toutes les règles au contexte courant."""
        for rule in self._rules:
            try:
                self._apply_rule(rule, context, db)
            except Exception as e:
                logger.debug("rules_engine: règle %s échouée: %s", rule.get("name"), e)

    def _apply_rule(self, rule: dict, context: dict, db):
        rtype = rule["rule_type"]
        cond  = rule["condition"]

        if rtype == "alert_metric":
            metric = cond.get("metric", "cpu_pct")
            threshold = float(cond.get("threshold", 90))
            value = context.get(metric, 0)
            if isinstance(value, (int, float)) and value >= threshold:
                self._fire(
                    title=f"Règle : {rule['name']}",
                    description=f"{metric} = {value} (seuil: {threshold})",
                    severity=cond.get("severity", "MEDIUM"),
                    db=db,
                )

        elif rtype == "watch_dir":
            watch_path = cond.get("path", "")
            # La vérification filesystem est faite par le watcher — ici on vérifie l'existence
            if watch_path and not Path(watch_path).exists():
                self._fire(
                    title=f"Règle : {rule['name']} — répertoire manquant",
                    description=f"Le répertoire {watch_path} n'existe plus.",
                    severity="HIGH", db=db,
                )

        elif rtype == "watch_process":
            proc_name = cond.get("process", "")
            import psutil
            running = any(p.name() == proc_name for p in psutil.process_iter(['name']))
            if not running:
                self._fire(
                    title=f"Règle : {rule['name']} — processus arrêté",
                    description=f"Le processus '{proc_name}' n'est plus en cours d'exécution.",
                    severity="HIGH", db=db,
                )

        elif rtype == "ignore_port":
            pass  # Géré dans port_sentinel

    def _fire(self, title, description, severity="MEDIUM", db=None):
        from core.monitor.event_bus import sentinel_bus
        sentinel_bus.publish({
            "type": "security_event",
            "category": "RULE",
            "severity": severity,
            "title": title,
            "description": description,
            "details": {},
        })
        if db is not None:
            try:
                from database.models import SecurityEventLog
                row = SecurityEventLog(
                    category="RULE", severity=severity,
                    title=title, description=description,
                    details="{}",
                )
                db.add(row)
                db.commit()
            except Exception:
                pass

    def create_rule_from_text(self, db, text: str) -> dict:
        """Parse une règle en langage naturel et la crée en DB."""
        text_lower = text.lower()
        rule_type = "alert_metric"
        condition = {}
        name = text[:80]

        if "surveille" in text_lower and "dossier" in text_lower:
            rule_type = "watch_dir"
            m = re.search(r'[/~]\S+', text)
            condition = {"path": m.group(0) if m else "/tmp"}
        elif "processus" in text_lower or "process" in text_lower:
            rule_type = "watch_process"
            m = re.search(r"(?:processus|process)\s+([a-zA-Z0-9_.-]+)", text_lower)
            condition = {"process": m.group(1) if m else "unknown"}
        elif "port" in text_lower and "ignore" in text_lower:
            rule_type = "ignore_port"
            m = re.search(r"\d+", text)
            condition = {"port": int(m.group(0)) if m else 0}
        elif "cpu" in text_lower or "ram" in text_lower:
            metric = "cpu_pct" if "cpu" in text_lower else "ram_pct"
            m = re.search(r"\d+", text)
            condition = {"metric": metric, "threshold": int(m.group(0)) if m else 90}
        else:
            condition = {"raw": text}

        try:
            from database.models import CustomMonitorRule
            import uuid
            row = CustomMonitorRule(
                rule_id=str(uuid.uuid4()),
                name=name,
                description=text,
                rule_type=rule_type,
                condition=json.dumps(condition),
                action="alert",
                enabled=True,
            )
            db.add(row)
            db.commit()
            self.load_rules(db)
            return {"id": row.rule_id, "name": name, "type": rule_type, "condition": condition}
        except Exception as e:
            logger.error("rules_engine: erreur création: %s", e)
            return {}


rules_engine = RulesEngine()
