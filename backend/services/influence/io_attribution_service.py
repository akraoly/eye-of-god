"""
IO Attribution & Counter-Intelligence — Bloc 9 Guerre de l'Information
Attribution des opérations d'influence, fingerprinting d'acteurs,
contre-ingérence, compartimentage, détection de taupes.
"""
from __future__ import annotations

import logging
import random
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

_ANALYSES: Dict[str, Dict] = {}
_OUTPUT = Path("./data/influence/attribution")
_OUTPUT.mkdir(parents=True, exist_ok=True)

_KNOWN_IO_ACTORS = {
    "apt_ira": {
        "name": "Internet Research Agency (IRA/Troll Farm)",
        "country": "Russia",
        "ttps": ["Sockpuppets en anglais", "Exploitation divisions raciales/politiques US", "Achat publicités Facebook", "Amplification RT/Sputnik"],
        "platforms": ["Facebook", "Twitter", "Instagram", "YouTube"],
        "known_campaigns": ["Élections US 2016", "Brexit amplification", "BLM manipulation", "COVID disinfo"],
        "signatures": ["Texte en russe dans métadonnées", "Création comptes en heures de bureau Moscou", "Orthographe non-native"],
    },
    "apt_ghostwriter": {
        "name": "Ghostwriter (UNC1151)",
        "country": "Belarus/Russia",
        "ttps": ["Hack & leak", "Falsification de déclarations officielles", "Usurpation identité personnalités politiques"],
        "platforms": ["Sites d'information compromis", "Facebook", "Twitter"],
        "known_campaigns": ["Désinformation OTAN en Pologne/Baltique", "Fausses déclarations militaires"],
        "signatures": ["Compromission sites gouvernementaux", "Thèmes anti-OTAN", "Cibles: Pologne, Lituanie, Lettonie"],
    },
    "apt_secondary_infektion": {
        "name": "Secondary Infektion",
        "country": "Russia",
        "ttps": ["Articles forgés", "Faux sites d'information", "Contenu multilingue"],
        "platforms": ["Reddit", "Imgur", "Medium", "Pastebin"],
        "known_campaigns": ["300+ campagnes documentées par EU DisinfoLab"],
        "signatures": ["Prose similaire entre articles", "Thèmes anti-Ukraine", "Multiples langues"],
    },
    "apt_dragonbridge": {
        "name": "Dragonbridge (BRONZE PRESIDENT)",
        "country": "China",
        "ttps": ["Amplification narrative pro-PCC", "Attaques contre dissidents", "Manipulation débat Hong Kong/Taïwan"],
        "platforms": ["YouTube", "Facebook", "Twitter", "TikTok"],
        "known_campaigns": ["COVID origin counter-narrative", "Xinjiang denial", "Taiwan propaganda"],
        "signatures": ["Simplified Chinese metadata", "Cross-platform synchronized posting", "Identical content in multiple languages"],
    },
    "apt_io_north_korea": {
        "name": "DPRK IO Operations",
        "country": "North Korea",
        "ttps": ["Crypto scam via LinkedIn", "Romance scam (pig butchering)", "Fake IT workers", "Crypto theft via social engineering"],
        "platforms": ["LinkedIn", "GitHub", "Telegram"],
        "known_campaigns": ["Lazarus crypto theft via social", "IT worker infiltration"],
        "signatures": ["Faux profils IT freelance", "Intérêt crypto/DeFi", "Demandes d'accès à des repos privés"],
    },
}

_ATTRIBUTION_INDICATORS = {
    "linguistic": {
        "name": "Indicateurs linguistiques",
        "signals": [
            "Erreurs grammaticales caractéristiques de L1 spécifique",
            "Calques syntaxiques (structures phrases de langue maternelle)",
            "Vocabulaire inhabituel pour la langue cible",
            "Traductions mécaniques (terminologie culturelle absente)",
            "Turns of phrase uniques à une région linguistique",
        ],
        "tools": ["LIWC", "JGAAP (authorship attribution)", "LangDetect", "Multilingual BERT"],
    },
    "temporal": {
        "name": "Indicateurs temporels",
        "signals": [
            "Heures de posting corrélées avec timezone source",
            "Absence de posts pendant jours fériés nationaux",
            "Patterns de sommeil (gap nocturne) pointant vers timezone",
            "Burst d'activité lors d'événements dans pays source",
        ],
        "tools": ["Temporal analysis scripts", "Timezone inference"],
    },
    "infrastructure": {
        "name": "Indicateurs d'infrastructure",
        "signals": [
            "Chevauchement IP avec acteurs connus",
            "Certificats TLS partagés entre domaines",
            "Registrations de domaines similaires (même registrar, dates groupées)",
            "Patterns d'hébergement (ASN récurrents)",
            "DNS passif — résolution historique",
        ],
        "tools": ["PassiveDNS", "Shodan", "DomainTools", "RiskIQ"],
    },
    "behavioral": {
        "name": "Indicateurs comportementaux",
        "signals": [
            "Séquence d'actions identique entre comptes",
            "Réponse coordonnée en minutes à un événement",
            "Mêmes fautes de frappe/corrections dans des comptes différents",
            "Network graph — clusters artificiels d'interactions",
        ],
        "tools": ["Graph analysis (Gephi, Neo4j)", "Bot Sentinel", "Stanford Internet Observatory"],
    },
    "content": {
        "name": "Indicateurs de contenu",
        "signals": [
            "Narratifs alignés avec intérêts stratégiques connus",
            "Amplification sélective de contenus d'organes étatiques",
            "Thèmes récurrents documentés dans rapports gouvernementaux",
            "Réutilisation de formulations entre campagnes historiques",
        ],
        "tools": ["ThreatConnect", "Recorded Future", "Graphika", "DFRLab"],
    },
}

_COUNTERINTEL_FRAMEWORKS = {
    "need_to_know": {
        "name": "Need-to-Know (compartimentage)",
        "desc": "Information partagée uniquement avec ceux qui en ont besoin opérationnel",
        "implementation": ["Classification par niveaux", "Canaux séparés par projet", "Audit des accès"],
    },
    "canary_traps": {
        "name": "Canary Traps (pièges à taupes)",
        "desc": "Version légèrement différente de l'information donnée à chaque suspect",
        "technique": "Si version A fuit → taupe A; si version B fuit → taupe B",
        "digital_impl": ["Documents watermarkés stéganographiquement", "URLs uniques par destinataire", "Timestamps différents par copie"],
    },
    "zero_trust_comms": {
        "name": "Zero Trust Communications",
        "desc": "Aucune communication non chiffrée — assumption de compromission permanente",
        "tools": ["Signal", "Matrix E2EE", "Briar (mesh)", "PGP pour email"],
    },
    "deception_operations": {
        "name": "Opérations de déception (contre-ingérence active)",
        "desc": "Injection délibérée de fausses informations pour tester la loyauté ou piéger",
        "principle": "Double agent — fournir des infos vraies pour établir la confiance, puis de fausses",
        "risk": "Peut compromettre des opérations légitimes si mal géré",
    },
    "personnel_security": {
        "name": "Sécurité du personnel (PERSEC)",
        "desc": "Réduction de la surface d'attaque via le personnel",
        "checks": ["Background checks", "Security clearance", "MICE assessment", "Regular polygraph (pour certains contextes)"],
    },
}


class IOAttributionService:

    def list_known_actors(self) -> Dict:
        return {k: {"name": v["name"], "country": v["country"],
                    "platforms": v["platforms"]}
                for k, v in _KNOWN_IO_ACTORS.items()}

    def get_actor_detail(self, actor: str) -> Dict:
        return _KNOWN_IO_ACTORS.get(actor, {"error": "actor_not_found"})

    def list_attribution_indicators(self) -> Dict:
        return {k: {"name": v["name"], "signal_count": len(v["signals"]), "tools": v["tools"]}
                for k, v in _ATTRIBUTION_INDICATORS.items()}

    def list_counterintel_frameworks(self) -> Dict:
        return {k: {"name": v["name"], "desc": v["desc"]}
                for k, v in _COUNTERINTEL_FRAMEWORKS.items()}

    def analyze_io_campaign(
        self,
        campaign_indicators: Dict,
        platforms: List[str],
        narratives: List[str],
        temporal_pattern: Optional[str] = None,
    ) -> Dict:
        analysis_id = str(uuid.uuid4())

        candidate_actors = []
        for actor_id, actor in _KNOWN_IO_ACTORS.items():
            score = 0
            matches = []

            platform_overlap = len(set(platforms) & set(actor["platforms"]))
            if platform_overlap:
                score += platform_overlap * 15
                matches.append(f"Plateformes: {platform_overlap} en commun")

            for narrative in narratives:
                for tactic in actor["ttps"]:
                    if any(word in narrative.lower() for word in tactic.lower().split()):
                        score += 20
                        matches.append(f"TTP: {tactic}")
                        break

            if score > 0:
                candidate_actors.append({
                    "actor":      actor_id,
                    "name":       actor["name"],
                    "country":    actor["country"],
                    "confidence": min(0.95, score / 100),
                    "matches":    matches[:3],
                })

        candidate_actors.sort(key=lambda x: -x["confidence"])

        attribution_level = "HIGH" if candidate_actors and candidate_actors[0]["confidence"] > 0.7 else \
                            ("MEDIUM" if candidate_actors and candidate_actors[0]["confidence"] > 0.4 else "LOW")

        result = {
            "analysis_id":       analysis_id,
            "analyzed_at":       datetime.utcnow().isoformat(),
            "platforms":         platforms,
            "narratives":        narratives,
            "temporal_pattern":  temporal_pattern,
            "candidate_actors":  candidate_actors[:3],
            "attribution_level": attribution_level,
            "indicators_found":  list(campaign_indicators.keys()),
            "recommendation":    "Corroborer avec données techniques (IP/domaines) pour hausse de confiance",
            "simulated":         True,
        }
        _ANALYSES[analysis_id] = result
        return result

    def canary_trap_setup(
        self,
        document_name: str,
        suspects: List[str],
        variation_type: str = "timestamp",
    ) -> Dict:
        versions = []
        for i, suspect in enumerate(suspects):
            if variation_type == "timestamp":
                variation = f"Créé le {2024 + i % 3}-{(i % 12 + 1):02d}-{(i % 28 + 1):02d} à {(9 + i % 8):02d}:{(i * 7 % 60):02d}"
            elif variation_type == "word_swap":
                words = ["confidentiel","secret","sensible","restreint"]
                variation = f"Classification: {words[i % len(words)]}"
            else:
                variation = f"ID: {uuid.uuid4().hex[:8].upper()}"

            versions.append({
                "suspect":    suspect,
                "version_id": f"v{i+1}_{uuid.uuid4().hex[:6]}",
                "variation":  variation,
                "watermark":  f"CANARY_{suspect.upper()[:4]}_{uuid.uuid4().hex[:4]}",
            })

        return {
            "document":          document_name,
            "variation_type":    variation_type,
            "versions_created":  len(versions),
            "versions":          versions,
            "detection_method":  "Si le document fuite, identifier via version_id/watermark l'origine de la fuite",
            "operational_note":  "Ne pas révéler l'existence du piège aux suspects",
            "simulated":         True,
        }

    def opsec_counterintel_check(
        self,
        org_name: str,
        frameworks_applied: Optional[List[str]] = None,
    ) -> Dict:
        applied = frameworks_applied or ["need_to_know"]
        missing = [k for k in _COUNTERINTEL_FRAMEWORKS if k not in applied]
        score   = len(applied) / len(_COUNTERINTEL_FRAMEWORKS)
        return {
            "organization":        org_name,
            "frameworks_applied":  applied,
            "frameworks_missing":  missing,
            "counterintel_score":  round(score, 2),
            "risk_level":          "LOW" if score > 0.7 else ("MEDIUM" if score > 0.4 else "HIGH"),
            "top_recommendation":  _COUNTERINTEL_FRAMEWORKS.get(missing[0], {}).get("name","N/A") if missing else "Maintenir les pratiques actuelles",
            "simulated":           True,
        }

    def get_analysis(self, analysis_id: str) -> Dict:
        return _ANALYSES.get(analysis_id, {"error": "not_found"})
