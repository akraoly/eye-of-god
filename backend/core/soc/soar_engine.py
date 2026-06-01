"""
SOAR Engine — Security Orchestration, Automation & Response.
Playbooks de réponse automatisée, portés depuis AEGIS AI v2.0.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import logging

log = logging.getLogger("SOC.SOAR")


@dataclass
class PlaybookStep:
    order: int
    action: str
    description: str
    auto_execute: bool
    requires_confirmation: bool = False
    params: dict = field(default_factory=dict)


@dataclass
class Playbook:
    id: str
    name: str
    description: str
    attack_categories: list
    min_severity: str
    steps: list
    estimated_duration: str
    financial_impact_usd: int
    financial_source: str
    tags: list = field(default_factory=list)


PLAYBOOKS: dict[str, Playbook] = {
    "pb_brute_force": Playbook(
        id="pb_brute_force", name="SSH/RDP Brute Force Response",
        description="Réponse automatisée aux attaques brute force — blocage IP, audit, scan persistance",
        attack_categories=["BRUTE_FORCE", "UNAUTHORIZED_ACCESS"],
        min_severity="MEDIUM", estimated_duration="45 secondes",
        financial_impact_usd=4_880_000,
        financial_source="IBM Cost of Data Breach Report 2024 — avg $4.88M",
        tags=["authentication", "credential", "ssh", "rdp"],
        steps=[
            PlaybookStep(1, "BLOCK_IP",          "Bloquer l'IP attaquante (iptables)",            False, True),
            PlaybookStep(2, "LOG_EVIDENCE",       "Capturer les logs d'authentification",          True),
            PlaybookStep(3, "INCREASE_MONITOR",   "Augmenter la surveillance sur l'hôte cible",    True),
            PlaybookStep(4, "SCAN_PERSISTENCE",   "Scanner les mécanismes de persistance",         False, True),
            PlaybookStep(5, "NOTIFY_ADMIN",       "Notifier l'administrateur",                     True),
            PlaybookStep(6, "GENERATE_REPORT",    "Générer rapport d'incident",                    True),
        ],
    ),
    "pb_port_scan": Playbook(
        id="pb_port_scan", name="Port Scan Response",
        description="Réponse à un scan de reconnaissance réseau",
        attack_categories=["PORT_SCAN"],
        min_severity="LOW", estimated_duration="20 secondes",
        financial_impact_usd=50_000,
        financial_source="Estimation coût reconnaissance avant attaque",
        tags=["recon", "network", "scan"],
        steps=[
            PlaybookStep(1, "LOG_EVIDENCE",    "Logger les détails du scan",         True),
            PlaybookStep(2, "INCREASE_MONITOR","Activer surveillance renforcée",      True),
            PlaybookStep(3, "RATE_LIMIT",      "Rate-limiter l'IP source",           False, True),
            PlaybookStep(4, "NOTIFY_ADMIN",    "Notifier si scan persistant",        True),
        ],
    ),
    "pb_intrusion": Playbook(
        id="pb_intrusion", name="Active Intrusion Response",
        description="Réponse à une intrusion active — isolation, forensique, éradication",
        attack_categories=["INTRUSION", "MALWARE", "UNAUTHORIZED_ACCESS"],
        min_severity="HIGH", estimated_duration="5 minutes",
        financial_impact_usd=9_440_000,
        financial_source="IBM 2024 — avg $9.44M attaque destructive",
        tags=["intrusion", "incident", "critical"],
        steps=[
            PlaybookStep(1, "ISOLATE_HOST",     "Isoler l'hôte compromis du réseau",          False, True),
            PlaybookStep(2, "CAPTURE_TRAFFIC",  "Capturer le trafic pour forensique",         False, True),
            PlaybookStep(3, "FORENSIC_ANALYSIS","Analyser artefacts et timeline",             False, True),
            PlaybookStep(4, "SCAN_PERSISTENCE", "Scanner persistances (cron, services, reg)", False, True),
            PlaybookStep(5, "CREATE_INCIDENT",  "Créer incident P1 — CRITICAL",               True),
            PlaybookStep(6, "NOTIFY_ADMIN",     "Notification d'urgence — SOC + Direction",  True),
            PlaybookStep(7, "GENERATE_REPORT",  "Rapport forensique complet",                 True),
        ],
    ),
    "pb_data_exfiltration": Playbook(
        id="pb_data_exfiltration", name="Data Exfiltration Response",
        description="Réponse à une exfiltration de données en cours",
        attack_categories=["DATA_EXFILTRATION"],
        min_severity="HIGH", estimated_duration="3 minutes",
        financial_impact_usd=4_450_000,
        financial_source="IBM 2024 — avg breach cost",
        tags=["data", "exfil", "dlp"],
        steps=[
            PlaybookStep(1, "BLOCK_IP",          "Bloquer la destination d'exfiltration",     False, True),
            PlaybookStep(2, "CAPTURE_TRAFFIC",   "Capturer le trafic sortant",                True),
            PlaybookStep(3, "LOG_EVIDENCE",      "Logger les fichiers accédés/exfiltrés",     True),
            PlaybookStep(4, "FORENSIC_ANALYSIS", "Identifier les données compromises",        False, True),
            PlaybookStep(5, "RESET_CREDENTIALS", "Révoquer credentials exposés",              False, True),
            PlaybookStep(6, "NOTIFY_ADMIN",      "Notification urgente + DPO si RGPD",        True),
        ],
    ),
    "pb_ransomware": Playbook(
        id="pb_ransomware", name="Ransomware Response",
        description="Réponse immédiate à une infection ransomware",
        attack_categories=["RANSOMWARE", "MALWARE"],
        min_severity="CRITICAL", estimated_duration="2 minutes",
        financial_impact_usd=5_130_000,
        financial_source="IBM 2024 — avg ransomware cost $5.13M",
        tags=["ransomware", "critical", "isolation"],
        steps=[
            PlaybookStep(1, "ISOLATE_HOST",     "Isolation réseau IMMÉDIATE",                False, True),
            PlaybookStep(2, "BLOCK_IP",         "Bloquer C2 identifiés",                     True),
            PlaybookStep(3, "SCAN_PERSISTENCE", "Identifier variante + IOCs",               False, True),
            PlaybookStep(4, "CAPTURE_TRAFFIC",  "Préserver trafic chiffrement",              True),
            PlaybookStep(5, "FORENSIC_ANALYSIS","Analyser vecteur d'entrée",                 False, True),
            PlaybookStep(6, "CREATE_INCIDENT",  "Incident P0 — CRISIS",                      True),
            PlaybookStep(7, "NOTIFY_ADMIN",     "Cellule de crise + ANSSI si nécessaire",    True),
        ],
    ),
    "pb_c2": Playbook(
        id="pb_c2", name="C2 Communication Response",
        description="Réponse à une communication Command & Control détectée",
        attack_categories=["C2"],
        min_severity="HIGH", estimated_duration="3 minutes",
        financial_impact_usd=9_440_000,
        financial_source="IBM 2024 — APT breach avg",
        tags=["c2", "apt", "lateral"],
        steps=[
            PlaybookStep(1, "BLOCK_IP",         "Bloquer le serveur C2",                     False, True),
            PlaybookStep(2, "ISOLATE_HOST",     "Isoler l'hôte infecté",                     False, True),
            PlaybookStep(3, "CAPTURE_TRAFFIC",  "Capturer communications C2",                True),
            PlaybookStep(4, "FORENSIC_ANALYSIS","Analyser implant et TTPs",                  False, True),
            PlaybookStep(5, "SCAN_PERSISTENCE", "Chercher backdoors additionnels",           False, True),
            PlaybookStep(6, "NOTIFY_ADMIN",     "Rapport APT suspect",                       True),
        ],
    ),
}


class SoarEngine:

    def list_playbooks(self, category: str = None) -> list:
        pbs = list(PLAYBOOKS.values())
        if category:
            pbs = [p for p in pbs if category.upper() in p.attack_categories]
        return [self._pb_dict(p) for p in pbs]

    def get_playbook(self, playbook_id: str) -> Optional[dict]:
        pb = PLAYBOOKS.get(playbook_id)
        return self._pb_dict(pb) if pb else None

    def recommend(self, alert_category: str, severity: str) -> Optional[dict]:
        """Recommande le playbook le plus adapté pour une alerte."""
        candidates = []
        for pb in PLAYBOOKS.values():
            if alert_category.upper() in pb.attack_categories:
                sev_order = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
                if sev_order.index(severity.upper()) >= sev_order.index(pb.min_severity):
                    candidates.append(pb)
        if not candidates:
            return None
        # Préférer le plus spécifique (plus de steps)
        best = max(candidates, key=lambda p: len(p.steps))
        return self._pb_dict(best)

    def execute_step(self, playbook_id: str, step_order: int,
                     context: dict = None) -> dict:
        """Simule l'exécution d'une étape de playbook."""
        pb = PLAYBOOKS.get(playbook_id)
        if not pb:
            return {"success": False, "error": "Playbook introuvable"}
        step = next((s for s in pb.steps if s.order == step_order), None)
        if not step:
            return {"success": False, "error": "Étape introuvable"}

        # En production : exécuter l'action réelle (iptables, isolation, etc.)
        # Pour l'instant : simulation avec journalisation
        log.info(f"[SOAR] {playbook_id} step {step_order}: {step.action} — {step.description}")
        return {
            "success": True,
            "playbook_id": playbook_id,
            "step": step_order,
            "action": step.action,
            "description": step.description,
            "auto_executed": step.auto_execute,
            "requires_confirmation": step.requires_confirmation,
            "timestamp": datetime.utcnow().isoformat(),
            "note": "Simulation — action journalisée" if not step.auto_execute else "Exécuté automatiquement",
        }

    def _pb_dict(self, pb: Playbook) -> dict:
        return {
            "id": pb.id, "name": pb.name, "description": pb.description,
            "attack_categories": pb.attack_categories, "min_severity": pb.min_severity,
            "estimated_duration": pb.estimated_duration,
            "financial_impact_usd": pb.financial_impact_usd,
            "financial_source": pb.financial_source, "tags": pb.tags,
            "steps": [{"order": s.order, "action": s.action, "description": s.description,
                       "auto_execute": s.auto_execute,
                       "requires_confirmation": s.requires_confirmation}
                      for s in pb.steps],
        }


soar_engine = SoarEngine()
