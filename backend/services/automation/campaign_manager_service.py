"""
Campaign Manager — Bloc 7 Automation Stratégique
Orchestration multi-cibles, gestion de phases, timeline, assets/implants,
suivi de progression, reporting de campagne.
"""
from __future__ import annotations

import logging
import random
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

_CAMPAIGNS: Dict[str, Dict] = {}
_OUTPUT = Path("./data/automation/campaigns")
_OUTPUT.mkdir(parents=True, exist_ok=True)

_CAMPAIGN_STATUS = ["planning", "active", "paused", "completed", "aborted"]

_OPERATION_TYPES = {
    "apt_espionage": {
        "name": "APT Espionage",
        "typical_duration_days": 180,
        "targets_count": "3-15",
        "priority": "intelligence",
        "groups_ref": ["APT28", "APT29", "Lazarus", "APT41"],
    },
    "ransomware_campaign": {
        "name": "Campagne Ransomware",
        "typical_duration_days": 21,
        "targets_count": "1-50",
        "priority": "financial",
        "groups_ref": ["LockBit", "BlackCat", "Cl0p", "RansomHub"],
    },
    "strategic_disruption": {
        "name": "Disruption Stratégique",
        "typical_duration_days": 7,
        "targets_count": "1-5",
        "priority": "sabotage",
        "groups_ref": ["Sandworm", "Volt Typhoon", "BlackEnergy"],
    },
    "supply_chain_op": {
        "name": "Opération Supply Chain",
        "typical_duration_days": 365,
        "targets_count": "1 → hundreds",
        "priority": "scale",
        "groups_ref": ["UNC2452 (SolarWinds)", "Winnti", "BARIUM"],
    },
    "financial_operation": {
        "name": "Opération Financière",
        "typical_duration_days": 60,
        "targets_count": "1-10",
        "priority": "financial",
        "groups_ref": ["Lazarus SWIFT", "FIN7", "Carbanak"],
    },
    "hacktivist_campaign": {
        "name": "Campagne Hacktiviste",
        "typical_duration_days": 14,
        "targets_count": "5-100",
        "priority": "disruption/visibility",
        "groups_ref": ["Anonymous", "KillNet", "SiegedSec"],
    },
}

_ASSET_TYPES = {
    "c2_server":        {"desc": "Command & Control server", "risk": "HIGH"},
    "redirector":       {"desc": "Traffic redirector/CDN abuse", "risk": "MEDIUM"},
    "implant_rat":      {"desc": "Remote Access Trojan (implant actif)", "risk": "CRITICAL"},
    "implant_stealth":  {"desc": "Implant furtif (beacon sleep long)", "risk": "LOW"},
    "payload_stager":   {"desc": "Stager de payload première étape", "risk": "HIGH"},
    "credential_store": {"desc": "Base de credentials collectés", "risk": "CRITICAL"},
    "exfil_drop":       {"desc": "Serveur de réception d'exfiltration", "risk": "HIGH"},
    "domain_fronting":  {"desc": "Infrastructure domain fronting", "risk": "LOW"},
    "vpn_node":         {"desc": "Nœud VPN/proxy d'anonymisation", "risk": "LOW"},
}

_PHASE_TEMPLATES = {
    "setup": {
        "name": "Mise en place infrastructure",
        "tasks": [
            "Provisionnement serveurs C2 (VPS anonymes)",
            "Configuration redirecteurs de trafic",
            "Génération certificats TLS pour C2",
            "Test de communication C2 ↔ implant",
            "Configuration domain fronting",
        ],
        "duration_days": 7,
    },
    "reconnaissance": {
        "name": "Reconnaissance cible",
        "tasks": [
            "OSINT passif (LinkedIn, Shodan, WHOIS)",
            "Cartographie infrastructure exposée",
            "Identification des employés clés",
            "Analyse surface d'attaque",
        ],
        "duration_days": 14,
    },
    "weaponization": {
        "name": "Weaponization",
        "tasks": [
            "Développement payloads customisés",
            "Test d'évasion AV/EDR",
            "Création leurres phishing",
            "Configuration malware persistance",
        ],
        "duration_days": 10,
    },
    "delivery": {
        "name": "Livraison",
        "tasks": [
            "Campagne spear phishing ciblée",
            "Exploitation vulnérabilité publique",
            "Drop USB physique si applicable",
        ],
        "duration_days": 5,
    },
    "exploitation": {
        "name": "Exploitation & Foothold",
        "tasks": [
            "Exécution du payload initial",
            "Établissement du premier beacon C2",
            "Contournement défenses initiales",
        ],
        "duration_days": 3,
    },
    "expansion": {
        "name": "Expansion & mouvement latéral",
        "tasks": [
            "Élévation de privilèges",
            "Dump de credentials",
            "Pivot vers autres systèmes",
            "Reconnaissance interne BloodHound",
        ],
        "duration_days": 14,
    },
    "collection": {
        "name": "Collecte d'objectifs",
        "tasks": [
            "Identification des données cibles",
            "Staging des données collectées",
            "Chiffrement archive exfiltration",
        ],
        "duration_days": 7,
    },
    "exfiltration": {
        "name": "Exfiltration",
        "tasks": [
            "Transfert données via canal C2 chiffré",
            "Vérification intégrité données reçues",
            "Nettoyage traces locales",
        ],
        "duration_days": 3,
    },
    "impact": {
        "name": "Action sur objectif final",
        "tasks": [
            "Déploiement payload d'impact",
            "Exécution action finale (ransom/wipe/sabotage)",
            "Couverture des traces",
        ],
        "duration_days": 1,
    },
}


class CampaignManagerService:

    def list_operation_types(self) -> Dict:
        return _OPERATION_TYPES

    def list_asset_types(self) -> Dict:
        return _ASSET_TYPES

    def create_campaign(
        self,
        name: str,
        operation_type: str,
        targets: List[Dict],
        operator: str = "operator_1",
        start_date: Optional[str] = None,
        phases: Optional[List[str]] = None,
    ) -> Dict:
        cid = str(uuid.uuid4())
        op  = _OPERATION_TYPES.get(operation_type, _OPERATION_TYPES["apt_espionage"])

        if not start_date:
            start_date = datetime.utcnow().date().isoformat()
        start_dt = datetime.fromisoformat(start_date)

        if not phases:
            phases = ["setup","reconnaissance","weaponization","delivery","exploitation","expansion","collection","exfiltration"]

        phase_list = []
        cursor = start_dt
        for ph_name in phases:
            ph = _PHASE_TEMPLATES.get(ph_name, _PHASE_TEMPLATES["setup"])
            end_dt = cursor + timedelta(days=ph["duration_days"])
            phase_list.append({
                "name":       ph_name,
                "label":      ph["name"],
                "tasks":      ph["tasks"],
                "start":      cursor.date().isoformat(),
                "end":        end_dt.date().isoformat(),
                "duration_days": ph["duration_days"],
                "status":     "pending",
                "progress_pct": 0,
            })
            cursor = end_dt

        assets = self._gen_assets(operation_type)

        campaign = {
            "campaign_id":     cid,
            "name":            name,
            "operation_type":  operation_type,
            "operation_name":  op["name"],
            "operator":        operator,
            "status":          "planning",
            "created_at":      datetime.utcnow().isoformat(),
            "start_date":      start_date,
            "estimated_end":   cursor.date().isoformat(),
            "targets":         targets,
            "target_count":    len(targets),
            "phases":          phase_list,
            "assets":          assets,
            "compromised_hosts": [],
            "credentials_collected": 0,
            "data_collected_mb": 0,
            "alerts_triggered": 0,
            "total_days_planned": (cursor - start_dt).days,
            "simulated":       True,
        }
        _CAMPAIGNS[cid] = campaign
        return campaign

    def get_campaign(self, campaign_id: str) -> Dict:
        return _CAMPAIGNS.get(campaign_id, {"error": "campaign_not_found"})

    def list_campaigns(self) -> Dict:
        return {"campaigns": [
            {"campaign_id": k, "name": v["name"], "status": v["status"],
             "operation_type": v["operation_type"], "target_count": v["target_count"],
             "created_at": v["created_at"]}
            for k, v in _CAMPAIGNS.items()
        ]}

    def update_campaign_status(self, campaign_id: str, status: str) -> Dict:
        c = _CAMPAIGNS.get(campaign_id)
        if not c:
            return {"error": "campaign_not_found"}
        if status not in _CAMPAIGN_STATUS:
            return {"error": f"status doit être parmi: {_CAMPAIGN_STATUS}"}
        c["status"] = status
        c["updated_at"] = datetime.utcnow().isoformat()
        return {"campaign_id": campaign_id, "status": status, "updated_at": c["updated_at"]}

    def advance_phase(self, campaign_id: str, phase_name: str, progress_pct: int = 100) -> Dict:
        c = _CAMPAIGNS.get(campaign_id)
        if not c:
            return {"error": "campaign_not_found"}
        for ph in c["phases"]:
            if ph["name"] == phase_name:
                ph["progress_pct"] = min(100, max(0, progress_pct))
                ph["status"] = "completed" if progress_pct >= 100 else "in_progress"
                if progress_pct >= 100:
                    ph["completed_at"] = datetime.utcnow().isoformat()
                    # Simulate progression effects
                    if phase_name == "exploitation":
                        c["compromised_hosts"].append(f"WORKSTATION-{random.randint(100,999)}")
                    elif phase_name == "expansion":
                        for _ in range(random.randint(2, 5)):
                            c["compromised_hosts"].append(f"HOST-{random.randint(100,999)}")
                        c["credentials_collected"] += random.randint(10, 50)
                    elif phase_name == "collection":
                        c["data_collected_mb"] += random.randint(100, 5000)
                return {"campaign_id": campaign_id, "phase": phase_name,
                        "progress_pct": ph["progress_pct"], "status": ph["status"]}
        return {"error": f"phase '{phase_name}' not found"}

    def add_compromised_host(self, campaign_id: str, hostname: str, access_level: str = "user") -> Dict:
        c = _CAMPAIGNS.get(campaign_id)
        if not c:
            return {"error": "campaign_not_found"}
        entry = {
            "hostname": hostname,
            "access_level": access_level,
            "compromised_at": datetime.utcnow().isoformat(),
            "implant_active": True,
            "beacon_interval_s": random.choice([60, 300, 900, 3600]),
        }
        c["compromised_hosts"].append(entry)
        return {"added": entry, "total_hosts": len(c["compromised_hosts"])}

    def generate_campaign_report(self, campaign_id: str) -> Dict:
        c = _CAMPAIGNS.get(campaign_id)
        if not c:
            return {"error": "campaign_not_found"}
        completed = [p for p in c["phases"] if p["status"] == "completed"]
        pending   = [p for p in c["phases"] if p["status"] == "pending"]
        return {
            "campaign_id":        campaign_id,
            "name":               c["name"],
            "status":             c["status"],
            "operation_type":     c["operation_type"],
            "targets":            c["target_count"],
            "compromised_hosts":  len(c["compromised_hosts"]) if isinstance(c["compromised_hosts"], list) else c["compromised_hosts"],
            "credentials_collected": c["credentials_collected"],
            "data_collected_mb":  c["data_collected_mb"],
            "alerts_triggered":   c["alerts_triggered"],
            "phases_completed":   len(completed),
            "phases_pending":     len(pending),
            "total_phases":       len(c["phases"]),
            "progress_pct":       round(len(completed) / max(1, len(c["phases"])) * 100, 1),
            "assets_active":      len([a for a in c.get("assets", []) if a.get("status") == "active"]),
            "generated_at":       datetime.utcnow().isoformat(),
            "simulated":          True,
        }

    def _gen_assets(self, operation_type: str) -> List[Dict]:
        base_assets = [
            {"type": "c2_server",   "host": f"185.{random.randint(100,200)}.{random.randint(1,254)}.{random.randint(1,254)}", "status": "active"},
            {"type": "redirector",  "host": f"104.{random.randint(100,200)}.{random.randint(1,254)}.{random.randint(1,254)}", "status": "active"},
            {"type": "exfil_drop",  "host": f"45.{random.randint(100,200)}.{random.randint(1,254)}.{random.randint(1,254)}",  "status": "active"},
            {"type": "vpn_node",    "host": f"91.{random.randint(100,200)}.{random.randint(1,254)}.{random.randint(1,254)}",  "status": "active"},
        ]
        if operation_type in ["apt_espionage","supply_chain_op"]:
            base_assets.append({"type": "domain_fronting", "host": "d3qlr7cxsjhkxj.cloudfront.net", "status": "active"})
        return base_assets
