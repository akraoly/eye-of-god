"""
OPSEC (Operations Security) — Bloc 7 Automation Stratégique
Évaluation OPSEC, réduction d'attribution, rotation d'infrastructure,
obfuscation du trafic, contre-mesures forensiques.
"""
from __future__ import annotations

import logging
import random
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

_ASSESSMENTS: Dict[str, Dict] = {}
_OUTPUT = Path("./data/automation/opsec")
_OUTPUT.mkdir(parents=True, exist_ok=True)

_OPSEC_CATEGORIES = {
    "infrastructure": {
        "name": "Infrastructure",
        "checks": [
            {"id": "infra_01", "name": "Serveurs C2 sur réseau dédié",           "weight": 10},
            {"id": "infra_02", "name": "Redirecteurs de trafic en place",          "weight": 8},
            {"id": "infra_03", "name": "Domain fronting configuré",               "weight": 9},
            {"id": "infra_04", "name": "Certificats TLS valides sur C2",          "weight": 7},
            {"id": "infra_05", "name": "Infrastructure non liée aux opérations précédentes","weight": 10},
            {"id": "infra_06", "name": "Pas de réutilisation d'IP connues",       "weight": 9},
        ],
    },
    "attribution": {
        "name": "Réduction Attribution",
        "checks": [
            {"id": "attr_01", "name": "Paiement anonyme des infras (crypto/cash)","weight": 9},
            {"id": "attr_02", "name": "Registrations domaines avec fausses infos","weight": 8},
            {"id": "attr_03", "name": "VPN/Tor pour administration",              "weight": 9},
            {"id": "attr_04", "name": "Pas d'artefacts linguistiques identifiables","weight": 7},
            {"id": "attr_05", "name": "Timestamps cohérents avec timezone cible", "weight": 6},
            {"id": "attr_06", "name": "IOCs uniques (pas de réutilisation tooling)","weight": 10},
        ],
    },
    "traffic": {
        "name": "Trafic réseau",
        "checks": [
            {"id": "traf_01", "name": "C2 trafic mimique applications légitimes", "weight": 9},
            {"id": "traf_02", "name": "Beacon jitter configuré (>20%)",           "weight": 8},
            {"id": "traf_03", "name": "Protocoles chiffrés exclusivement",        "weight": 9},
            {"id": "traf_04", "name": "Volumes trafic normaux (pas de spikes)",   "weight": 7},
            {"id": "traf_05", "name": "DNS requests normales (pas de DGA évident)","weight": 7},
            {"id": "traf_06", "name": "Pas de trafic aux heures suspectes",       "weight": 6},
        ],
    },
    "malware_opsec": {
        "name": "OPSEC Malware",
        "checks": [
            {"id": "mal_01", "name": "Pas de strings identifiables en clair",    "weight": 8},
            {"id": "mal_02", "name": "Compiler artifacts supprimés",             "weight": 7},
            {"id": "mal_03", "name": "Debug symbols strippés",                   "weight": 8},
            {"id": "mal_04", "name": "Pas de PDB paths résiduels",               "weight": 7},
            {"id": "mal_05", "name": "Pas de test environment artifacts",        "weight": 8},
            {"id": "mal_06", "name": "Timestamps PE cohérents avec contexte",    "weight": 6},
        ],
    },
    "operational": {
        "name": "Discipline opérationnelle",
        "checks": [
            {"id": "ops_01", "name": "Accès C2 via proxies/VPN uniquement",      "weight": 10},
            {"id": "ops_02", "name": "Pas de recherches Google liées à l'op",    "weight": 9},
            {"id": "ops_03", "name": "Séparation stricte des identités",         "weight": 9},
            {"id": "ops_04", "name": "Chiffrement communications internes",      "weight": 8},
            {"id": "ops_05", "name": "Compartimentage des opérateurs (need-to-know)","weight": 8},
            {"id": "ops_06", "name": "Protocole de nettoyage post-opération défini","weight": 7},
        ],
    },
}

_ATTRIBUTION_TECHNIQUES = {
    "false_flag": {
        "name": "False Flag (impersonation d'APT connu)",
        "techniques": [
            "Réutilisation d'outils/IOCs publics d'un autre groupe",
            "Insertion de chaînes en langue étrangère (caractères cyrilliques, chinois)",
            "Imitation de TTPs publiquement documentées",
            "Usage de malware open-source associé à un autre acteur",
        ],
        "examples": ["APT10 false flag (Tick)", "Fancy Bear attribution confusion"],
        "difficulty": "MEDIUM",
        "effectiveness": "HIGH",
    },
    "infrastructure_misdirection": {
        "name": "Misdirection Infrastructure",
        "techniques": [
            "Routage via pays tiers non impliqués",
            "Achat d'infra via proxy/straw man",
            "Réutilisation de serveurs compromis comme redirecteurs",
            "Exit nodes TOR dans pays ciblé",
        ],
        "difficulty": "LOW",
        "effectiveness": "MEDIUM",
    },
    "timing_manipulation": {
        "name": "Manipulation Temporelle",
        "techniques": [
            "Opérations pendant les heures ouvrées de la timezone cible",
            "Timestamps artifacts manipulés",
            "Délai artificiel post-compromission (simuler timezone différente)",
        ],
        "difficulty": "LOW",
        "effectiveness": "LOW",
    },
    "toolmark_removal": {
        "name": "Suppression des toolmarks",
        "techniques": [
            "Modification du code source des outils publics",
            "Recompilation des outils avec paramètres différents",
            "Remplacement des magic bytes/headers caractéristiques",
            "Changement des User-Agent strings hardcodés",
        ],
        "difficulty": "MEDIUM",
        "effectiveness": "HIGH",
    },
    "living_off_the_land": {
        "name": "Living off the Land",
        "techniques": [
            "Utilisation exclusive de binaires système (LOLBins)",
            "PowerShell/WMI/COM pour toutes les actions",
            "Pas de dépose d'outils custom sur disque",
            "Utilisation de features natives (certutil, bitsadmin, etc.)",
        ],
        "difficulty": "HIGH",
        "effectiveness": "VERY_HIGH",
    },
}

_INFRA_ROTATION_STRATEGIES = {
    "burn_after_use": {
        "name": "Burn After Use",
        "desc": "Chaque serveur utilisé une seule fois puis abandonné",
        "cost": "HIGH",
        "opsec_level": "MAXIMUM",
        "rotation_trigger": "Immédiatement après chaque utilisation",
    },
    "time_based": {
        "name": "Rotation temporelle",
        "desc": "Rotation sur période fixe (7/14/30 jours)",
        "cost": "MEDIUM",
        "opsec_level": "HIGH",
        "rotation_trigger": "Selon calendrier prédéfini",
    },
    "detection_triggered": {
        "name": "Rotation sur détection",
        "desc": "Rotation si indicateurs de détection (block, scan, analysis)",
        "cost": "LOW",
        "opsec_level": "MEDIUM",
        "rotation_trigger": "Si IP bloquée, domaine blacklisté, scan de sécurité détecté",
    },
    "phase_based": {
        "name": "Rotation par phase",
        "desc": "Infrastructure différente par phase d'opération",
        "cost": "MEDIUM",
        "opsec_level": "HIGH",
        "rotation_trigger": "Transition de phase (recon→access→post-exploit)",
    },
}


class OpsecService:

    def list_categories(self) -> Dict:
        return {k: {"name": v["name"], "checks_count": len(v["checks"])}
                for k, v in _OPSEC_CATEGORIES.items()}

    def list_attribution_techniques(self) -> Dict:
        return {k: {"name": v["name"], "difficulty": v["difficulty"], "effectiveness": v["effectiveness"]}
                for k, v in _ATTRIBUTION_TECHNIQUES.items()}

    def list_rotation_strategies(self) -> Dict:
        return _INFRA_ROTATION_STRATEGIES

    def assess_opsec(
        self,
        operation_name: str,
        checks_passed: Dict[str, List[str]],
    ) -> Dict:
        assessment_id = str(uuid.uuid4())
        results = {}
        total_score = 0
        total_weight = 0
        category_scores = {}

        for cat_id, cat in _OPSEC_CATEGORIES.items():
            passed_ids = set(checks_passed.get(cat_id, []))
            cat_score = 0
            cat_weight = 0
            check_results = []
            for check in cat["checks"]:
                w = check["weight"]
                passed = check["id"] in passed_ids
                cat_score  += w if passed else 0
                cat_weight += w
                check_results.append({
                    "id":     check["id"],
                    "name":   check["name"],
                    "weight": w,
                    "passed": passed,
                })
            pct = round(cat_score / cat_weight * 100, 1) if cat_weight > 0 else 0
            category_scores[cat_id] = {"name": cat["name"], "score_pct": pct, "checks": check_results}
            total_score  += cat_score
            total_weight += cat_weight

        overall_pct = round(total_score / total_weight * 100, 1) if total_weight > 0 else 0
        if overall_pct >= 85:   risk_level = "LOW"
        elif overall_pct >= 65: risk_level = "MEDIUM"
        elif overall_pct >= 40: risk_level = "HIGH"
        else:                   risk_level = "CRITICAL"

        failed = []
        for cat_id, cat in _OPSEC_CATEGORIES.items():
            passed_ids = set(checks_passed.get(cat_id, []))
            for check in cat["checks"]:
                if check["id"] not in passed_ids:
                    failed.append({"category": cat["name"], "check": check["name"], "weight": check["weight"]})
        failed.sort(key=lambda x: -x["weight"])

        assessment = {
            "assessment_id":    assessment_id,
            "operation_name":   operation_name,
            "assessed_at":      datetime.utcnow().isoformat(),
            "overall_score_pct": overall_pct,
            "risk_level":       risk_level,
            "category_scores":  category_scores,
            "top_failures":     failed[:5],
            "recommendations":  self._gen_opsec_recommendations(failed[:5], overall_pct),
            "simulated":        True,
        }
        _ASSESSMENTS[assessment_id] = assessment
        return assessment

    def quick_assess(self, operation_name: str) -> Dict:
        score = random.uniform(45, 95)
        if score >= 85:   risk = "LOW"
        elif score >= 65: risk = "MEDIUM"
        elif score >= 40: risk = "HIGH"
        else:             risk = "CRITICAL"
        return {
            "assessment_id":     str(uuid.uuid4()),
            "operation_name":    operation_name,
            "overall_score_pct": round(score, 1),
            "risk_level":        risk,
            "quick_wins": [
                "Activer le beacon jitter (20-50%)",
                "Utiliser domain fronting",
                "Payer l'infrastructure en Monero",
                "Configurer les redirecteurs de trafic",
            ],
            "simulated":         True,
        }

    def plan_attribution_reduction(
        self,
        techniques: List[str],
        operation_type: str = "apt_espionage",
    ) -> Dict:
        selected = []
        for t in techniques:
            if t in _ATTRIBUTION_TECHNIQUES:
                selected.append({"technique": t, **_ATTRIBUTION_TECHNIQUES[t]})
        overall_effectiveness = max(
            ([self._eff_score(t["effectiveness"]) for t in selected] or [0])
        )
        return {
            "techniques_selected": len(selected),
            "techniques":          selected,
            "overall_effectiveness": ["VERY_LOW","LOW","MEDIUM","HIGH","VERY_HIGH"][min(4, overall_effectiveness)],
            "recommendation": "Combiner false_flag + living_off_the_land + toolmark_removal pour attribution maximale",
            "simulated":       True,
        }

    def generate_rotation_plan(
        self,
        strategy: str,
        current_assets: List[Dict],
        campaign_duration_days: int = 90,
    ) -> Dict:
        st    = _INFRA_ROTATION_STRATEGIES.get(strategy, _INFRA_ROTATION_STRATEGIES["phase_based"])
        rotations = []
        if strategy == "time_based":
            interval = 14
            for day in range(interval, campaign_duration_days, interval):
                rotations.append({
                    "day":    day,
                    "action": "rotate_all_c2",
                    "new_ip": f"194.{random.randint(100,200)}.{random.randint(1,254)}.{random.randint(1,254)}",
                    "note":   "Nouveaux serveurs provisionnés, anciens abandonnés",
                })
        elif strategy == "phase_based":
            phases = ["recon","initial_access","post_exploit","exfil"]
            for i, phase in enumerate(phases):
                rotations.append({
                    "phase":  phase,
                    "action": "full_infra_change",
                    "assets": f"Set_{i+1} (4 serveurs nouveaux)",
                    "note":   f"Infrastructure dédiée à la phase {phase}",
                })
        return {
            "strategy":              strategy,
            "strategy_name":         st["name"],
            "opsec_level":           st["opsec_level"],
            "rotations_planned":     len(rotations),
            "rotation_events":       rotations,
            "current_assets_count":  len(current_assets),
            "estimated_infra_cost":  f"${len(rotations) * 4 * random.randint(10,50)}/opération",
            "simulated":             True,
        }

    def get_assessment(self, assessment_id: str) -> Dict:
        return _ASSESSMENTS.get(assessment_id, {"error": "not_found"})

    def _gen_opsec_recommendations(self, failures: List[Dict], score: float) -> List[str]:
        recs = []
        for f in failures:
            recs.append(f"[{f['category']}] Corriger: {f['check']} (poids: {f['weight']})")
        if score < 50:
            recs.append("Score critique — envisager de reporter l'opération")
        recs.append("Documenter et valider chaque check OPSEC avant lancement")
        return recs

    def _eff_score(self, eff: str) -> int:
        return {"VERY_LOW": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3, "VERY_HIGH": 4}.get(eff, 2)
