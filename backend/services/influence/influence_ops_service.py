"""
Influence Ops — Bloc 9 Guerre de l'Information & Influence Stratégique
Comportement inauthentique coordonné (CIB), réseaux de bots, sockpuppets,
amplification de narratifs, manipulation de plateformes.
Simulation — usage légal (red team IO, contre-ingérence, recherche défensive).
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
_OUTPUT = Path("./data/influence/ops")
_OUTPUT.mkdir(parents=True, exist_ok=True)

_PLATFORMS = {
    "twitter_x":   {"name": "X (Twitter)",  "api_limit_per_day": 300, "bot_detection": "HIGH",   "reach_multiplier": 8.0},
    "facebook":    {"name": "Facebook",      "api_limit_per_day": 200, "bot_detection": "HIGH",   "reach_multiplier": 6.0},
    "instagram":   {"name": "Instagram",     "api_limit_per_day": 150, "bot_detection": "MEDIUM", "reach_multiplier": 5.0},
    "telegram":    {"name": "Telegram",      "api_limit_per_day": 1000,"bot_detection": "LOW",    "reach_multiplier": 4.0},
    "reddit":      {"name": "Reddit",        "api_limit_per_day": 100, "bot_detection": "MEDIUM", "reach_multiplier": 3.0},
    "linkedin":    {"name": "LinkedIn",      "api_limit_per_day": 80,  "bot_detection": "HIGH",   "reach_multiplier": 4.5},
    "tiktok":      {"name": "TikTok",        "api_limit_per_day": 200, "bot_detection": "MEDIUM", "reach_multiplier": 12.0},
    "youtube":     {"name": "YouTube",       "api_limit_per_day": 50,  "bot_detection": "MEDIUM", "reach_multiplier": 10.0},
    "whatsapp":    {"name": "WhatsApp",      "api_limit_per_day": 500, "bot_detection": "LOW",    "reach_multiplier": 3.0},
    "discord":     {"name": "Discord",       "api_limit_per_day": 2000,"bot_detection": "LOW",    "reach_multiplier": 2.5},
}

_SOCKPUPPET_PROFILES = {
    "authentic_citizen": {
        "name": "Citoyen authentique",
        "bio_template": "{name}, {age} ans, {city}. Passionné de {hobby}. Opinions personnelles.",
        "posting_frequency": "2-5 posts/day",
        "account_age_days": 730,
        "followers_range": [150, 800],
        "credibility": "HIGH",
        "detection_risk": "LOW",
        "setup_time_days": 90,
    },
    "journalist_blogger": {
        "name": "Journaliste/Blogueur",
        "bio_template": "{name} | Journaliste indépendant | {topic} | Contact: {email}",
        "posting_frequency": "5-10 posts/day",
        "account_age_days": 365,
        "followers_range": [500, 5000],
        "credibility": "VERY_HIGH",
        "detection_risk": "MEDIUM",
        "setup_time_days": 180,
    },
    "expert_analyst": {
        "name": "Expert / Analyste",
        "bio_template": "Former {institution} | {specialty} expert | Views my own",
        "posting_frequency": "3-7 posts/day",
        "account_age_days": 1000,
        "followers_range": [1000, 20000],
        "credibility": "VERY_HIGH",
        "detection_risk": "MEDIUM",
        "setup_time_days": 365,
    },
    "activist": {
        "name": "Activiste / Militant",
        "bio_template": "Fighting for {cause} | {location} | Retweet ≠ endorsement",
        "posting_frequency": "10-20 posts/day",
        "account_age_days": 180,
        "followers_range": [200, 3000],
        "credibility": "MEDIUM",
        "detection_risk": "MEDIUM",
        "setup_time_days": 30,
    },
    "bot_amplifier": {
        "name": "Bot amplificateur",
        "bio_template": "",
        "posting_frequency": "50-200 posts/day",
        "account_age_days": 30,
        "followers_range": [10, 100],
        "credibility": "LOW",
        "detection_risk": "VERY_HIGH",
        "setup_time_days": 1,
    },
}

_IO_TACTICS = {
    "narrative_seeding": {
        "name": "Semis de narratif",
        "desc": "Introduction organique d'un récit dans les conversations existantes",
        "effectiveness": 0.70,
        "detection_risk": "LOW",
        "time_to_spread_hours": 48,
    },
    "amplification_network": {
        "name": "Réseau d'amplification",
        "desc": "Coordination de comptes pour booster un contenu (likes/RT/shares en masse)",
        "effectiveness": 0.85,
        "detection_risk": "HIGH",
        "time_to_spread_hours": 6,
    },
    "astroturfing": {
        "name": "Astroturfing",
        "desc": "Simuler un mouvement populaire grassroots avec des comptes coordonnés",
        "effectiveness": 0.75,
        "detection_risk": "MEDIUM",
        "time_to_spread_hours": 24,
    },
    "hashtag_hijacking": {
        "name": "Détournement de hashtag",
        "desc": "Infiltrer un trending hashtag pour y injecter un narratif adversarial",
        "effectiveness": 0.65,
        "detection_risk": "HIGH",
        "time_to_spread_hours": 2,
    },
    "persona_laundering": {
        "name": "Blanchiment de persona",
        "desc": "Faire valider une fausse identité par des sources légitimes",
        "effectiveness": 0.90,
        "detection_risk": "LOW",
        "time_to_spread_hours": 720,
    },
    "information_flooding": {
        "name": "Inondation d'information",
        "desc": "Saturer l'espace informationnel pour noyer la vérité",
        "effectiveness": 0.60,
        "detection_risk": "VERY_HIGH",
        "time_to_spread_hours": 1,
    },
    "strategic_leaking": {
        "name": "Fuite stratégique",
        "desc": "Publication sélective d'informations vraies/tronquées pour influencer un récit",
        "effectiveness": 0.95,
        "detection_risk": "LOW",
        "time_to_spread_hours": 12,
    },
    "pig_butchering": {
        "name": "Pig butchering (romance scam IO)",
        "desc": "Relation de confiance longue durée → manipulation vers objectif final",
        "effectiveness": 0.92,
        "detection_risk": "VERY_LOW",
        "time_to_spread_hours": 2160,
    },
}

_DETECTION_INDICATORS = {
    "posting_patterns": ["Pics réguliers 24/7", "Volume anormalement élevé", "Horaires nocturnes incohérents"],
    "content_similarity": ["Textes quasi-identiques entre comptes", "Copy-paste avec légères variations", "Traductions automatiques visibles"],
    "network_analysis": ["Graphe de followers artificiel", "Follower/following ratio suspect", "Liens circulaires entre comptes"],
    "metadata": ["Création en lot (même jour)", "Même IP de création", "Device fingerprint identique"],
    "behavioral": ["Absence d'interaction organique", "Réponses hors-contexte", "Aucune discussion personnel"],
}


class InfluenceOpsService:

    def list_platforms(self) -> Dict:
        return {k: {"name": v["name"], "bot_detection": v["bot_detection"],
                    "reach_multiplier": v["reach_multiplier"]}
                for k, v in _PLATFORMS.items()}

    def list_sockpuppet_profiles(self) -> Dict:
        return {k: {"name": v["name"], "credibility": v["credibility"],
                    "detection_risk": v["detection_risk"], "setup_time_days": v["setup_time_days"]}
                for k, v in _SOCKPUPPET_PROFILES.items()}

    def list_tactics(self) -> Dict:
        return {k: {"name": v["name"], "effectiveness": v["effectiveness"],
                    "detection_risk": v["detection_risk"]}
                for k, v in _IO_TACTICS.items()}

    def list_detection_indicators(self) -> Dict:
        return _DETECTION_INDICATORS

    def design_campaign(
        self,
        name: str,
        objective: str,
        target_audience: str,
        platforms: List[str],
        tactics: List[str],
        budget_accounts: int = 50,
        duration_days: int = 30,
    ) -> Dict:
        cid = str(uuid.uuid4())

        plat_details = []
        total_potential_reach = 0
        for p in platforms:
            pi = _PLATFORMS.get(p, {})
            daily_posts = budget_accounts * pi.get("api_limit_per_day", 100) // budget_accounts
            reach = budget_accounts * pi.get("reach_multiplier", 3.0) * 100
            total_potential_reach += reach
            plat_details.append({
                "platform": p, "name": pi.get("name", p),
                "accounts_allocated": budget_accounts // len(platforms),
                "daily_posts": min(daily_posts, pi.get("api_limit_per_day", 100)),
                "estimated_daily_reach": int(reach),
                "detection_risk": pi.get("bot_detection","MEDIUM"),
            })

        tactic_details = []
        combined_effectiveness = 1.0
        for t in tactics:
            ti = _IO_TACTICS.get(t, {})
            tactic_details.append({"tactic": t, "name": ti.get("name",t), "effectiveness": ti.get("effectiveness",0.5)})
            combined_effectiveness *= ti.get("effectiveness", 0.5)
        combined_effectiveness = 1 - combined_effectiveness

        sockpuppet_mix = [
            {"type": "authentic_citizen", "count": int(budget_accounts * 0.4)},
            {"type": "expert_analyst",    "count": int(budget_accounts * 0.1)},
            {"type": "activist",          "count": int(budget_accounts * 0.2)},
            {"type": "bot_amplifier",     "count": int(budget_accounts * 0.3)},
        ]

        phases = [
            {"phase": 1, "name": "Infrastructure",  "days": "1-7",  "tasks": ["Création comptes", "Warm-up organique", "Contenu neutre pré-IO"]},
            {"phase": 2, "name": "Positionnement",  "days": "8-14", "tasks": ["Intégration dans communautés", "Gain crédibilité", "Réseau de followers"]},
            {"phase": 3, "name": "Activation",      "days": "15-21","tasks": ["Lancement tactiques principales", "Amplification coordonnée", "Semis narratif"]},
            {"phase": 4, "name": "Amplification",   "days": "22-30","tasks": ["Saturation", "Réponse aux contre-narratifs", "Évaluation impact"]},
        ]

        campaign = {
            "campaign_id":              cid,
            "name":                     name,
            "objective":                objective,
            "target_audience":          target_audience,
            "duration_days":            duration_days,
            "budget_accounts":          budget_accounts,
            "platforms":                plat_details,
            "tactics":                  tactic_details,
            "sockpuppet_mix":           sockpuppet_mix,
            "phases":                   phases,
            "total_potential_reach":    int(total_potential_reach),
            "combined_effectiveness":   round(combined_effectiveness, 2),
            "created_at":               datetime.utcnow().isoformat(),
            "simulated":                True,
            "note":                     "Usage défensif/red team IO — simulation uniquement",
        }
        _CAMPAIGNS[cid] = campaign
        return campaign

    def generate_sockpuppet_network(
        self,
        profile_type: str,
        count: int,
        language: str = "fr",
        country: str = "France",
    ) -> Dict:
        profile = _SOCKPUPPET_PROFILES.get(profile_type, _SOCKPUPPET_PROFILES["authentic_citizen"])
        accounts = []

        first_names_fr = ["Jean","Marie","Pierre","Sophie","Lucas","Emma","Thomas","Léa","Nicolas","Julie","Antoine","Claire","Paul","Chloé","Alexandre"]
        last_names_fr  = ["Martin","Bernard","Dubois","Thomas","Robert","Richard","Petit","Durand","Leroy","Moreau","Simon","Laurent","Lefebvre","Michel"]
        cities_fr      = ["Paris","Lyon","Marseille","Bordeaux","Toulouse","Nantes","Strasbourg","Lille","Montpellier","Nice"]
        hobbies        = ["randonnée","photographie","cuisine","lecture","cyclisme","jardinage","cinéma","musique","voyage","sport"]

        for i in range(min(count, 20)):
            fn = random.choice(first_names_fr)
            ln = random.choice(last_names_fr)
            city = random.choice(cities_fr)
            creation = (datetime.utcnow() - timedelta(days=profile["account_age_days"] + random.randint(-30,30))).date().isoformat()

            accounts.append({
                "id":          str(uuid.uuid4())[:8],
                "username":    f"{fn.lower()}{ln.lower()}{random.randint(10,99)}",
                "display_name": f"{fn} {ln}",
                "bio":         profile["bio_template"].format(
                    name=f"{fn} {ln}", age=random.randint(25,55), city=city,
                    hobby=random.choice(hobbies), topic="politique", email=f"{fn.lower()}@proton.me",
                    institution="Sciences Po", specialty="géopolitique", cause="libertés civiles",
                    location=city
                ),
                "created":     creation,
                "followers":   random.randint(*profile["followers_range"]),
                "profile_type": profile_type,
                "credibility":  profile["credibility"],
            })

        return {
            "profile_type":    profile_type,
            "language":        language,
            "country":         country,
            "count_generated": len(accounts),
            "accounts":        accounts,
            "setup_time_days": profile["setup_time_days"],
            "detection_risk":  profile["detection_risk"],
            "simulated":       True,
        }

    def get_campaign(self, campaign_id: str) -> Dict:
        return _CAMPAIGNS.get(campaign_id, {"error": "not_found"})

    def list_campaigns(self) -> Dict:
        return {"campaigns": [{"campaign_id": k, "name": v["name"], "objective": v["objective"]}
                               for k, v in _CAMPAIGNS.items()]}
