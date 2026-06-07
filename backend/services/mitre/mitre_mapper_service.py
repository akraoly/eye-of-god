"""
MitreMapperService — Cartographie automatique MITRE ATT&CK.
Enregistre chaque action opérationnelle en tant qu'événement MITRE,
met à jour les stats de campagne et expose graphes / heatmaps / recommandations.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from database.models_mitre import MitreEvent, MitreCampaignStats

logger = logging.getLogger("mitre_mapper")

# ── Mapping action → technique MITRE ─────────────────────────────────────────

ACTIONS_MAP: dict[str, dict[str, Any]] = {
    "port_scan":                    {"technique": "T1046",     "tactic": "TA0043", "score": 3},
    "service_enumeration":          {"technique": "T1046",     "tactic": "TA0043", "score": 4},
    "subdomain_discovery":          {"technique": "T1583",     "tactic": "TA0043", "score": 2},
    "dns_enumeration":              {"technique": "T1590",     "tactic": "TA0043", "score": 2},
    "directory_fuzzing":            {"technique": "T1589",     "tactic": "TA0043", "score": 3},
    "c2_beacon":                    {"technique": "T1071",     "tactic": "TA0011", "score": 5},
    "c2_sliver_implant":            {"technique": "T1055",     "tactic": "TA0005", "score": 5},
    "c2_havoc_implant":             {"technique": "T1055",     "tactic": "TA0005", "score": 5},
    "c2_command_exec":              {"technique": "T1059",     "tactic": "TA0002", "score": 4},
    "keylogger":                    {"technique": "T1056.001", "tactic": "TA0006", "score": 5},
    "clipboard_capture":            {"technique": "T1115",     "tactic": "TA0006", "score": 4},
    "form_grabber":                 {"technique": "T1056.003", "tactic": "TA0006", "score": 5},
    "credential_dumping":           {"technique": "T1003",     "tactic": "TA0006", "score": 5},
    "network_sniffing":             {"technique": "T1040",     "tactic": "TA0006", "score": 4},
    "audio_capture":                {"technique": "T1123",     "tactic": "TA0009", "score": 5},
    "webcam_capture":               {"technique": "T1125",     "tactic": "TA0009", "score": 5},
    "screen_capture":               {"technique": "T1113",     "tactic": "TA0009", "score": 4},
    "camera_snapshot":              {"technique": "T1125",     "tactic": "TA0009", "score": 4},
    "exfil_dns":                    {"technique": "T1048.003", "tactic": "TA0010", "score": 5},
    "exfil_icmp":                   {"technique": "T1048.004", "tactic": "TA0010", "score": 5},
    "exfil_http":                   {"technique": "T1048.002", "tactic": "TA0010", "score": 4},
    "exfil_websocket":              {"technique": "T1048",     "tactic": "TA0010", "score": 4},
    "persistence_scheduled_task":   {"technique": "T1053.005", "tactic": "TA0003", "score": 4},
    "persistence_registry":         {"technique": "T1547.001", "tactic": "TA0003", "score": 4},
    "privilege_escalation":         {"technique": "T1068",     "tactic": "TA0004", "score": 5},
    "rfid_scan":                    {"technique": "T1557.001", "tactic": "TA0042", "score": 3},
    "rfid_clone":                   {"technique": "T1557.001", "tactic": "TA0042", "score": 5},
    "sdr_listen":                   {"technique": "T1025",     "tactic": "TA0009", "score": 4},
    "sdr_replay":                   {"technique": "T1557.002", "tactic": "TA0042", "score": 5},
    "ble_scan":                     {"technique": "T1557.003", "tactic": "TA0042", "score": 3},
    "ble_gatt_read":                {"technique": "T1557.003", "tactic": "TA0042", "score": 4},
    "ble_gatt_write":               {"technique": "T1557.003", "tactic": "TA0042", "score": 5},
    "sql_injection":                {"technique": "T1190",     "tactic": "TA0001", "score": 5},
    "xss":                          {"technique": "T1059.007", "tactic": "TA0001", "score": 4},
    "command_injection":            {"technique": "T1059",     "tactic": "TA0002", "score": 5},
    "ssrf":                         {"technique": "T1190",     "tactic": "TA0001", "score": 4},
    "onvif_scan":                   {"technique": "T1046",     "tactic": "TA0043", "score": 3},
    "camera_fingerprint":           {"technique": "T1590",     "tactic": "TA0043", "score": 2},
    "cve_hikvision":                {"technique": "T1190",     "tactic": "TA0001", "score": 5},
    "cve_dahua":                    {"technique": "T1190",     "tactic": "TA0001", "score": 5},
    "cve_generic":                  {"technique": "T1190",     "tactic": "TA0001", "score": 4},
    "trigger_auto_action":          {"technique": "T1053",     "tactic": "TA0002", "score": 3},
}

# ── Mapping tactic_id → métadonnées ──────────────────────────────────────────

TACTICS_MAP: dict[str, dict[str, str]] = {
    "TA0043": {"name": "Reconnaissance",        "phase": "Recon"},
    "TA0042": {"name": "Resource Development",  "phase": "Resource Dev"},
    "TA0001": {"name": "Initial Access",        "phase": "Initial Access"},
    "TA0002": {"name": "Execution",             "phase": "Execution"},
    "TA0003": {"name": "Persistence",           "phase": "Persistence"},
    "TA0004": {"name": "Privilege Escalation",  "phase": "Priv Esc"},
    "TA0005": {"name": "Defense Evasion",       "phase": "Defense Evasion"},
    "TA0006": {"name": "Credential Access",     "phase": "Cred Access"},
    "TA0007": {"name": "Discovery",             "phase": "Discovery"},
    "TA0008": {"name": "Lateral Movement",      "phase": "Lateral Move"},
    "TA0009": {"name": "Collection",            "phase": "Collection"},
    "TA0010": {"name": "Exfiltration",          "phase": "Exfil"},
    "TA0011": {"name": "Command and Control",   "phase": "C2"},
}

# Ordre de la Kill Chain (ATT&CK pour Enterprise)
KILL_CHAIN_ORDER = [
    "TA0043", "TA0042", "TA0001", "TA0002", "TA0003",
    "TA0004", "TA0005", "TA0006", "TA0009", "TA0010", "TA0011",
]


class MitreMapperService:
    """Service central de mapping MITRE ATT&CK."""

    # ── Log d'une action ─────────────────────────────────────────────────────

    async def log_action(
        self,
        campaign_id: str,
        action_type: str,
        details: dict | None = None,
        db: Optional[Session] = None,
    ) -> dict[str, Any]:
        """Enregistre une action dans la DB et met à jour les stats de campagne."""
        if details is None:
            details = {}

        mapping = ACTIONS_MAP.get(action_type)
        if not mapping:
            logger.debug("Action inconnue ignorée pour MITRE: %s", action_type)
            return {"status": "unknown_action", "action_type": action_type}

        if db is None:
            logger.warning("log_action appelé sans session DB — ignoré")
            return {"status": "no_db"}

        technique_id = mapping["technique"]
        tactic_id = mapping["tactic"]
        score = mapping["score"]

        event = MitreEvent(
            campaign_id=campaign_id,
            action_type=action_type,
            technique_id=technique_id,
            tactic_id=tactic_id,
            score=score,
            success=True,
            details=details,
            timestamp=datetime.utcnow(),
        )
        db.add(event)
        db.commit()
        db.refresh(event)

        await self._update_campaign_stats(campaign_id, db)

        return {
            "status": "logged",
            "event_id": event.event_id,
            "technique": technique_id,
            "tactic": tactic_id,
            "score": score,
        }

    # ── Mise à jour stats campagne ────────────────────────────────────────────

    async def _update_campaign_stats(self, campaign_id: str, db: Session) -> None:
        """Recalcule et persiste les stats agrégées d'une campagne."""
        events = (
            db.query(MitreEvent)
            .filter(MitreEvent.campaign_id == campaign_id)
            .all()
        )

        techniques: dict[str, int] = {}
        tactics: set[str] = set()
        total_score = 0

        for ev in events:
            techniques[ev.technique_id] = techniques.get(ev.technique_id, 0) + 1
            tactics.add(ev.tactic_id)
            total_score += ev.score

        coverage = round(len(techniques) / 200 * 100, 2)

        # Phases complétées (au moins 1 événement par tactic)
        completed_phases = [
            TACTICS_MAP[t]["phase"]
            for t in KILL_CHAIN_ORDER
            if t in tactics and t in TACTICS_MAP
        ]

        stats = (
            db.query(MitreCampaignStats)
            .filter(MitreCampaignStats.campaign_id == campaign_id)
            .first()
        )
        if stats is None:
            stats = MitreCampaignStats(
                campaign_id=campaign_id,
                created_at=datetime.utcnow(),
            )
            db.add(stats)

        stats.total_techniques = len(techniques)
        stats.total_tactics = len(tactics)
        stats.total_score = total_score
        stats.coverage = coverage
        stats.completed_phases = completed_phases
        stats.updated_at = datetime.utcnow()
        db.commit()

    # ── Stats campagne ────────────────────────────────────────────────────────

    async def get_campaign_mitre_stats(
        self, campaign_id: str, db: Session
    ) -> dict[str, Any]:
        """Retourne les stats MITRE agrégées d'une campagne."""
        stats = (
            db.query(MitreCampaignStats)
            .filter(MitreCampaignStats.campaign_id == campaign_id)
            .first()
        )
        if stats is None:
            return {
                "campaign_id": campaign_id,
                "total_techniques": 0,
                "total_tactics": 0,
                "total_score": 0,
                "coverage": 0.0,
                "completed_phases": [],
                "top_techniques": [],
            }

        # Top 5 techniques
        rows = (
            db.query(
                MitreEvent.technique_id,
                MitreEvent.tactic_id,
                func.count(MitreEvent.id).label("count"),
                func.sum(MitreEvent.score).label("total_score"),
            )
            .filter(MitreEvent.campaign_id == campaign_id)
            .group_by(MitreEvent.technique_id, MitreEvent.tactic_id)
            .order_by(func.count(MitreEvent.id).desc())
            .limit(5)
            .all()
        )
        top_techniques = [
            {
                "technique_id": r.technique_id,
                "tactic_id": r.tactic_id,
                "tactic_name": TACTICS_MAP.get(r.tactic_id, {}).get("name", ""),
                "count": r.count,
                "total_score": r.total_score,
            }
            for r in rows
        ]

        return {
            "campaign_id": campaign_id,
            "total_techniques": stats.total_techniques,
            "total_tactics": stats.total_tactics,
            "total_score": stats.total_score,
            "coverage": stats.coverage,
            "completed_phases": stats.completed_phases or [],
            "top_techniques": top_techniques,
            "updated_at": stats.updated_at.isoformat() if stats.updated_at else None,
        }

    # ── Graphe d'attaque ──────────────────────────────────────────────────────

    async def get_attack_graph(
        self, campaign_id: str, db: Session
    ) -> dict[str, Any]:
        """Retourne un graphe de noeuds/arêtes utilisable par un renderer SVG."""
        rows = (
            db.query(
                MitreEvent.technique_id,
                MitreEvent.tactic_id,
                MitreEvent.action_type,
                func.count(MitreEvent.id).label("count"),
                func.sum(MitreEvent.score).label("total_score"),
                func.min(MitreEvent.timestamp).label("first_seen"),
            )
            .filter(MitreEvent.campaign_id == campaign_id)
            .group_by(MitreEvent.technique_id, MitreEvent.tactic_id, MitreEvent.action_type)
            .order_by(func.min(MitreEvent.timestamp))
            .all()
        )

        # Construire les noeuds
        nodes: list[dict] = []
        seen_techniques: set[str] = set()
        phase_order = {tac: idx for idx, tac in enumerate(KILL_CHAIN_ORDER)}

        for r in rows:
            node_id = r.technique_id
            if node_id not in seen_techniques:
                tactic_meta = TACTICS_MAP.get(r.tactic_id, {"name": r.tactic_id, "phase": r.tactic_id})
                nodes.append({
                    "id": node_id,
                    "technique_id": r.technique_id,
                    "name": r.action_type,
                    "tactic": r.tactic_id,
                    "tactic_name": tactic_meta["name"],
                    "phase": tactic_meta["phase"],
                    "score": r.total_score,
                    "count": r.count,
                    "phase_order": phase_order.get(r.tactic_id, 99),
                })
                seen_techniques.add(node_id)

        # Trier les noeuds par phase pour créer les arêtes chronologiques
        nodes_sorted = sorted(nodes, key=lambda n: n["phase_order"])

        edges: list[dict] = []
        for i in range(len(nodes_sorted) - 1):
            edges.append({
                "source": nodes_sorted[i]["technique_id"],
                "target": nodes_sorted[i + 1]["technique_id"],
            })

        # Phases présentes
        phases_present = sorted(
            {n["tactic"] for n in nodes},
            key=lambda t: phase_order.get(t, 99),
        )

        # Kill chain progress (ratio phases présentes / total kill chain)
        kill_chain_progress = round(len(phases_present) / len(KILL_CHAIN_ORDER) * 100, 1)

        return {
            "nodes": nodes_sorted,
            "edges": edges,
            "phases": phases_present,
            "kill_chain_progress": kill_chain_progress,
        }

    # ── Heatmap ───────────────────────────────────────────────────────────────

    async def get_heatmap(
        self, campaign_id: str, db: Session
    ) -> dict[str, Any]:
        """
        Retourne une matrice tactic_id → {technique_id: count}
        pour les 13 tactiques standard.
        """
        rows = (
            db.query(
                MitreEvent.tactic_id,
                MitreEvent.technique_id,
                func.count(MitreEvent.id).label("count"),
            )
            .filter(MitreEvent.campaign_id == campaign_id)
            .group_by(MitreEvent.tactic_id, MitreEvent.technique_id)
            .all()
        )

        # Initialiser toutes les tactiques à vide
        matrix: dict[str, dict[str, int]] = {
            tac: {} for tac in TACTICS_MAP
        }

        for r in rows:
            if r.tactic_id in matrix:
                matrix[r.tactic_id][r.technique_id] = r.count

        # Sérialiser en liste ordonnée pour le frontend
        heatmap = []
        for tac_id in KILL_CHAIN_ORDER:
            if tac_id not in TACTICS_MAP:
                continue
            tac_meta = TACTICS_MAP[tac_id]
            techniques = matrix.get(tac_id, {})
            heatmap.append({
                "tactic_id": tac_id,
                "tactic_name": tac_meta["name"],
                "phase": tac_meta["phase"],
                "techniques": techniques,
                "total_hits": sum(techniques.values()),
            })

        return {"heatmap": heatmap, "campaign_id": campaign_id}

    # ── Recommandations ───────────────────────────────────────────────────────

    async def recommend_next_techniques(
        self, campaign_id: str, db: Session
    ) -> list[dict[str, Any]]:
        """
        Suggère les techniques non encore utilisées dans la kill chain,
        prioritisées par score décroissant.
        """
        used_techniques = {
            r.technique_id
            for r in db.query(MitreEvent.technique_id)
            .filter(MitreEvent.campaign_id == campaign_id)
            .distinct()
            .all()
        }

        recommendations: list[dict] = []
        phase_order = {tac: idx for idx, tac in enumerate(KILL_CHAIN_ORDER)}

        for action_type, mapping in ACTIONS_MAP.items():
            technique_id = mapping["technique"]
            if technique_id in used_techniques:
                continue

            tactic_id = mapping["tactic"]
            tac_meta = TACTICS_MAP.get(tactic_id, {"name": tactic_id, "phase": tactic_id})

            recommendations.append({
                "action_type": action_type,
                "technique_id": technique_id,
                "tactic_id": tactic_id,
                "tactic_name": tac_meta["name"],
                "phase": tac_meta["phase"],
                "score": mapping["score"],
                "phase_order": phase_order.get(tactic_id, 99),
                "priority": (
                    "haute" if mapping["score"] >= 5
                    else "moyenne" if mapping["score"] >= 3
                    else "faible"
                ),
                "reason": f"Technique {technique_id} non couverte en {tac_meta['phase']}",
            })

        # Tri: d'abord par order kill chain puis par score décroissant
        recommendations.sort(key=lambda r: (r["phase_order"], -r["score"]))
        return recommendations

    # ── Rapport complet ───────────────────────────────────────────────────────

    async def generate_mitre_report(
        self,
        campaign_id: str,
        format: str = "json",
        db: Optional[Session] = None,
    ) -> dict[str, Any]:
        """Génère un rapport MITRE complet pour une campagne."""
        if db is None:
            return {"error": "no_db"}

        stats = await self.get_campaign_mitre_stats(campaign_id, db)
        graph = await self.get_attack_graph(campaign_id, db)
        heatmap = await self.get_heatmap(campaign_id, db)
        recommendations = await self.recommend_next_techniques(campaign_id, db)

        # Événements récents
        recent_events = (
            db.query(MitreEvent)
            .filter(MitreEvent.campaign_id == campaign_id)
            .order_by(MitreEvent.timestamp.desc())
            .limit(50)
            .all()
        )
        events_list = [
            {
                "event_id": e.event_id,
                "action_type": e.action_type,
                "technique_id": e.technique_id,
                "tactic_id": e.tactic_id,
                "score": e.score,
                "success": e.success,
                "timestamp": e.timestamp.isoformat() if e.timestamp else None,
            }
            for e in recent_events
        ]

        return {
            "campaign_id": campaign_id,
            "generated_at": datetime.utcnow().isoformat(),
            "format": format,
            "stats": stats,
            "attack_graph": graph,
            "heatmap": heatmap,
            "recommendations": recommendations[:20],
            "recent_events": events_list,
        }
