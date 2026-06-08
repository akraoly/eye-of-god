"""
PSYOP & Guerre Cognitive — Bloc 9 Guerre de l'Information
Opérations psychologiques, profilage comportemental, exploitation des biais cognitifs,
gestion de la perception, frameworks PSYOP militaires.
Usage défensif/recherche — comprendre pour protéger.
"""
from __future__ import annotations

import logging
import random
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

_PROFILES: Dict[str, Dict] = {}
_OUTPUT = Path("./data/influence/psyop")
_OUTPUT.mkdir(parents=True, exist_ok=True)

_COGNITIVE_BIASES = {
    "confirmation_bias": {
        "name": "Biais de confirmation",
        "desc": "Tendance à rechercher les informations qui confirment ses croyances préexistantes",
        "exploitation": "Présenter l'information dans un cadre cohérent avec les croyances cibles",
        "antidote": "Pensée critique, exposition délibérée aux points de vue opposés",
        "effectiveness": 0.92,
    },
    "availability_heuristic": {
        "name": "Heuristique de disponibilité",
        "desc": "Surestimation de la probabilité d'événements facilement mémorisables",
        "exploitation": "Saturation médiatique pour rendre un risque omniprésent dans l'esprit",
        "antidote": "Analyse statistique réelle, mise en perspective",
        "effectiveness": 0.85,
    },
    "authority_bias": {
        "name": "Biais d'autorité",
        "desc": "Tendance à faire confiance aux figures d'autorité",
        "exploitation": "Faux experts, usurpation d'identité d'institutions, credentials forgés",
        "antidote": "Vérification indépendante des sources, questionnement systématique",
        "effectiveness": 0.88,
    },
    "social_proof": {
        "name": "Preuve sociale",
        "desc": "Adopter les comportements/croyances du groupe",
        "exploitation": "Fake consensus (likes/RT amplifiés), témoignages coordonnés",
        "antidote": "Analyse indépendante, méfiance envers les consensus soudains",
        "effectiveness": 0.90,
    },
    "ingroup_bias": {
        "name": "Biais d'endogroupe",
        "desc": "Favoritisme envers son propre groupe",
        "exploitation": "Appels à l'identité de groupe, création d'un ennemi commun",
        "antidote": "Empathie interculturelle, exposition à la diversité",
        "effectiveness": 0.87,
    },
    "fear_uncertainty_doubt": {
        "name": "FUD (Fear, Uncertainty, Doubt)",
        "desc": "Manipulation par la peur et l'incertitude pour paralyser la prise de décision",
        "exploitation": "Diffusion de menaces ambiguës, chiffres alarmants non vérifiables",
        "antidote": "Analyse du risque factuelle, sources primaires",
        "effectiveness": 0.83,
    },
    "sunk_cost_fallacy": {
        "name": "Biais des coûts irrécupérables",
        "desc": "Continuer un cours d'action à cause des investissements passés",
        "exploitation": "Escalade d'engagement — inciter à investir davantage dans une direction",
        "antidote": "Évaluation prospective uniquement, ignorer les coûts passés",
        "effectiveness": 0.78,
    },
    "dunning_kruger": {
        "name": "Effet Dunning-Kruger",
        "desc": "Les incompétents surestiment leurs capacités",
        "exploitation": "Cibles dans des domaines où elles se croient expertes mais ne le sont pas",
        "antidote": "Humilité épistémique, consultation d'experts reconnus",
        "effectiveness": 0.75,
    },
    "backfire_effect": {
        "name": "Effet de retour de flamme",
        "desc": "Les croyances se renforcent quand elles sont contredites",
        "exploitation": "Attaquer frontalement une croyance pour la renforcer",
        "antidote": "Inoculation — introduire les contre-arguments progressivement",
        "effectiveness": 0.70,
    },
    "anchoring": {
        "name": "Biais d'ancrage",
        "desc": "Dépendance excessive à la première information reçue",
        "exploitation": "Introduire un cadre narratif extrême pour déplacer le centre du débat",
        "antidote": "Délibération consciente, recherche multi-sources avant conclusion",
        "effectiveness": 0.88,
    },
}

_PSYOP_FRAMEWORKS = {
    "JIPOE": {
        "name": "Joint Intelligence Preparation of the Operational Environment",
        "origin": "US Military",
        "steps": [
            "Define the operational environment",
            "Describe environmental effects on operations",
            "Evaluate the threat/adversary",
            "Determine threat courses of action",
        ],
        "use_case": "Analyse préliminaire avant opération IO",
    },
    "SMICE": {
        "name": "SMICE Framework (Sex, Money, Ideology, Coercion, Ego)",
        "origin": "Intelligence tradecraft",
        "motivators": {
            "Sex/Honeypot": "Exploitation des désirs et vulnérabilités romantiques",
            "Money":        "Corruption, chantage financier",
            "Ideology":     "Manipulation par les convictions politiques/religieuses",
            "Coercion":     "Menaces, pression, contrainte",
            "Ego":          "Flattery, manipulation de l'amour propre",
        },
        "use_case": "Identification des leviers de manipulation d'une cible spécifique",
    },
    "SCAME": {
        "name": "SCAME (Source, Content, Audience, Media, Effect)",
        "origin": "NATO PSYOP doctrine",
        "phases": [
            "Source: Qui émet le message?",
            "Content: Quel est le message?",
            "Audience: À qui s'adresse-t-il?",
            "Media: Via quel canal?",
            "Effect: Quel effet recherché?",
        ],
        "use_case": "Analyse et conception d'un message IO",
    },
    "IOTA": {
        "name": "IOTA (Influence Operations Targeting Architecture)",
        "origin": "Modern IO doctrine",
        "layers": [
            "Identify susceptible audiences",
            "Observe current beliefs and narratives",
            "Target with tailored messaging",
            "Assess impact and adjust",
        ],
        "use_case": "Ciblage précis dans une campagne d'influence",
    },
    "4D_doctrine": {
        "name": "4D Doctrine (Dismiss, Distort, Distract, Dismay)",
        "origin": "Russian IO doctrine analysis (EU DisinfoLab)",
        "tactics": {
            "Dismiss":  "Nier les faits, délégitimer les sources",
            "Distort":  "Déformer la réalité, contexte trompeur",
            "Distract": "Inonder de contre-narratifs pour disperser l'attention",
            "Dismay":   "Créer la confusion et le désespoir",
        },
        "use_case": "Analyse défensive des tactiques adversariales",
    },
}

_TARGET_SEGMENTS = {
    "high_information_consumer": {
        "name": "Consommateur d'info élevé",
        "characteristics": ["Lit plusieurs sources", "Partage beaucoup", "Influençable par autorité"],
        "best_approach": ["authority_bias", "confirmation_bias"],
        "platforms": ["Twitter", "LinkedIn", "Reddit"],
    },
    "casual_news_follower": {
        "name": "Suiveur casual",
        "characteristics": ["Sources limitées", "Partage émotionnel", "Sensible à la preuve sociale"],
        "best_approach": ["social_proof", "availability_heuristic", "fear_uncertainty_doubt"],
        "platforms": ["Facebook", "WhatsApp", "TikTok"],
    },
    "conspiracy_prone": {
        "name": "Enclin aux théories du complot",
        "characteristics": ["Méfiance institutionnelle", "Pattern-matching excessif"],
        "best_approach": ["confirmation_bias", "ingroup_bias"],
        "platforms": ["Telegram", "YouTube", "Forums"],
    },
    "professional_expert": {
        "name": "Professionnel/Expert",
        "characteristics": ["Vocabulaire technique", "Réseau d'influence limité", "Crédibilité élevée"],
        "best_approach": ["ego", "authority_bias", "sunk_cost_fallacy"],
        "platforms": ["LinkedIn", "Twitter académique", "Email"],
    },
    "politically_polarized": {
        "name": "Fortement polarisé",
        "characteristics": ["Vision binaire", "Rejet de l'opposition", "Forte appartenance de groupe"],
        "best_approach": ["ingroup_bias", "confirmation_bias", "backfire_effect"],
        "platforms": ["Twitter", "Facebook groupes", "Telegram"],
    },
}

_IO_COUNTERMEASURES = {
    "prebunking": {
        "name": "Prebunking (Inoculation informationnelle)",
        "desc": "Exposer les audiences aux techniques de manipulation avant qu'elles soient utilisées",
        "effectiveness": 0.75,
        "examples": ["Jeux sérieux Go Viral (Cambridge)", "Formation médias dans les écoles"],
    },
    "media_literacy": {
        "name": "Éducation aux médias",
        "desc": "Formation au fact-checking, identification des biais, pensée critique",
        "effectiveness": 0.65,
        "tools": ["InVID", "Snopes", "AFP Fact Check", "FactCheck.org"],
    },
    "technical_detection": {
        "name": "Détection technique (CIB)",
        "desc": "Systèmes automatisés de détection des comportements inauthentiques coordonnés",
        "tools": ["Stanford Internet Observatory", "DFRLab", "Bot Sentinel"],
        "signals": ["Volume posting", "Network analysis", "Metadata clustering"],
        "effectiveness": 0.70,
    },
    "narrative_monitoring": {
        "name": "Surveillance narrative",
        "desc": "Monitoring en temps réel des narratifs émergents potentiellement problématiques",
        "tools": ["GDELT", "Brandwatch", "Meltwater", "CrowdTangle"],
        "effectiveness": 0.80,
    },
    "attribution_research": {
        "name": "Recherche d'attribution",
        "desc": "Identifier les acteurs derrière les campagnes d'influence",
        "methods": ["Network graph analysis", "Language fingerprinting", "Infrastructure tracking"],
        "effectiveness": 0.60,
    },
}


class PsyopService:

    def list_cognitive_biases(self) -> Dict:
        return {k: {"name": v["name"], "effectiveness": v["effectiveness"]}
                for k, v in _COGNITIVE_BIASES.items()}

    def get_bias_detail(self, bias: str) -> Dict:
        return _COGNITIVE_BIASES.get(bias, {"error": "bias_not_found"})

    def list_psyop_frameworks(self) -> Dict:
        return {k: {"name": v["name"], "origin": v.get("origin",""), "use_case": v["use_case"]}
                for k, v in _PSYOP_FRAMEWORKS.items()}

    def list_target_segments(self) -> Dict:
        return {k: {"name": v["name"], "platforms": v["platforms"]}
                for k, v in _TARGET_SEGMENTS.items()}

    def list_countermeasures(self) -> Dict:
        return {k: {"name": v["name"], "effectiveness": v["effectiveness"]}
                for k, v in _IO_COUNTERMEASURES.items()}

    def profile_target_segment(
        self,
        segment: str,
        context: str = "",
        vulnerabilities: Optional[List[str]] = None,
    ) -> Dict:
        profile_id = str(uuid.uuid4())
        seg = _TARGET_SEGMENTS.get(segment, _TARGET_SEGMENTS["casual_news_follower"])

        biases_targeted = []
        for b in seg["best_approach"]:
            bias = _COGNITIVE_BIASES.get(b, {})
            biases_targeted.append({
                "bias":        b,
                "name":        bias.get("name",""),
                "exploitation":bias.get("exploitation",""),
                "effectiveness":bias.get("effectiveness",0.5),
            })

        messaging_recommendations = self._gen_messaging(segment, biases_targeted)

        profile = {
            "profile_id":              profile_id,
            "segment":                 segment,
            "segment_name":            seg["name"],
            "context":                 context,
            "characteristics":         seg["characteristics"],
            "targeted_platforms":      seg["platforms"],
            "biases_exploitable":      biases_targeted,
            "messaging_recommendations": messaging_recommendations,
            "vulnerability_score":     round(sum(b["effectiveness"] for b in biases_targeted) / max(1,len(biases_targeted)), 2),
            "countermeasures":         list(_IO_COUNTERMEASURES.keys())[:2],
            "created_at":              datetime.utcnow().isoformat(),
            "simulated":               True,
            "note":                    "Profil défensif — usage red team IO uniquement",
        }
        _PROFILES[profile_id] = profile
        return profile

    def design_psyop_message(
        self,
        framework: str,
        target_segment: str,
        objective: str,
        core_narrative: str,
        biases_to_exploit: Optional[List[str]] = None,
    ) -> Dict:
        fw  = _PSYOP_FRAMEWORKS.get(framework, _PSYOP_FRAMEWORKS["SCAME"])
        seg = _TARGET_SEGMENTS.get(target_segment, _TARGET_SEGMENTS["casual_news_follower"])
        biases = biases_to_exploit or seg["best_approach"]

        message_variants = [
            {
                "variant":   "Émotionnel (peur/urgence)",
                "tone":      "alarmiste",
                "hook":      f"⚠️ Ce que {target_segment.replace('_',' ')} ne sait pas encore...",
                "cta":       "Partager maintenant avant la censure",
                "bias":      "fear_uncertainty_doubt",
            },
            {
                "variant":   "Autorité (expert)",
                "tone":      "factuel/autoritaire",
                "hook":      f"Selon les experts, {core_narrative[:50]}...",
                "cta":       "Lire l'analyse complète",
                "bias":      "authority_bias",
            },
            {
                "variant":   "Social (groupe)",
                "tone":      "communautaire",
                "hook":      f"Des milliers de {target_segment.replace('_',' ')} ont déjà compris que...",
                "cta":       "Rejoignez le mouvement",
                "bias":      "social_proof",
            },
        ]

        return {
            "framework":         framework,
            "framework_name":    fw["name"],
            "target_segment":    target_segment,
            "objective":         objective,
            "core_narrative":    core_narrative,
            "biases_exploited":  biases,
            "message_variants":  message_variants,
            "recommended_channels": seg["platforms"],
            "estimated_effectiveness": round(random.uniform(0.55, 0.90), 2),
            "ethical_note":      "Usage défensif uniquement — comprendre pour construire la résilience",
            "simulated":         True,
        }

    def assess_io_resilience(self, organization: str, checks: Optional[List[str]] = None) -> Dict:
        default_checks = list(_IO_COUNTERMEASURES.keys())
        applied = checks or default_checks[:3]
        score = sum(_IO_COUNTERMEASURES.get(c, {}).get("effectiveness", 0.5) for c in applied) / max(1, len(applied))
        level = "RESILIENT" if score > 0.75 else ("MODERATE" if score > 0.50 else "VULNERABLE")
        return {
            "organization":     organization,
            "countermeasures_applied": applied,
            "resilience_score": round(score, 2),
            "resilience_level": level,
            "recommendations":  [c for c in default_checks if c not in applied][:3],
            "simulated":        True,
        }

    def get_profile(self, profile_id: str) -> Dict:
        return _PROFILES.get(profile_id, {"error": "not_found"})

    def _gen_messaging(self, segment: str, biases: List[Dict]) -> List[str]:
        recs = [
            "Adapter le registre lexical au niveau d'expertise de l'audience cible",
            "Utiliser des ancrages émotionnels avant les arguments rationnels",
            f"Diffuser via {'Facebook/WhatsApp' if 'casual' in segment else 'Twitter/LinkedIn'} en priorité",
        ]
        if biases:
            recs.append(f"Exploiter en priorité: {biases[0].get('name','')}")
        return recs
