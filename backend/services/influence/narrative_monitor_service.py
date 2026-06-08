"""
Narrative Monitoring & Counter-Narrative — Bloc 9 Guerre de l'Information
Surveillance des narratifs émergents, détection de campagnes coordonnées,
fact-checking automatisé, contre-narratifs, signalement de contenu.
Usage défensif — protection et résilience informationnelle.
"""
from __future__ import annotations

import logging
import random
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

_MONITORS: Dict[str, Dict] = {}
_ALERTS:   Dict[str, Dict] = {}
_OUTPUT = Path("./data/influence/narrative")
_OUTPUT.mkdir(parents=True, exist_ok=True)

_NARRATIVE_CATEGORIES = {
    "health_disinfo": {
        "name": "Désinformation santé",
        "keywords": ["vaccin","5G","big pharma","remède","virus fabriqué","plandémie"],
        "risk": "HIGH",
        "velocity": "VERY_HIGH",
        "impact": "Hésitation vaccinale, comportements à risque",
    },
    "electoral_disinfo": {
        "name": "Désinformation électorale",
        "keywords": ["fraude","votes volés","élection truquée","urnes","résultats falsifiés"],
        "risk": "CRITICAL",
        "velocity": "HIGH",
        "impact": "Erosion de la confiance démocratique, violence potentielle",
    },
    "military_disinfo": {
        "name": "Désinformation militaire/géopolitique",
        "keywords": ["attaque false flag","OTAN","biolabs","armes chimiques","provocations"],
        "risk": "CRITICAL",
        "velocity": "HIGH",
        "impact": "Escalade de tensions, recrutement, démoralisation",
    },
    "financial_disinfo": {
        "name": "Désinformation financière",
        "keywords": ["crash","banque en faillite","bitcoin moon","pump","rug pull"],
        "risk": "HIGH",
        "velocity": "VERY_HIGH",
        "impact": "Manipulation de marchés, fraude crypto",
    },
    "identity_disinfo": {
        "name": "Désinformation identitaire",
        "keywords": ["invasion","remplacisme","grand remplacement","islamisation","identité nationale"],
        "risk": "HIGH",
        "velocity": "MEDIUM",
        "impact": "Radicalisation, violence à l'encontre de minorités",
    },
    "climate_disinfo": {
        "name": "Désinformation climatique",
        "keywords": ["hoax climatique","réchauffement faux","CO2 bénéfique","agenda globale","scientifiques payés"],
        "risk": "MEDIUM",
        "velocity": "MEDIUM",
        "impact": "Inaction climatique, méfiance envers la science",
    },
}

_FACT_CHECK_ORGS = {
    "AFP_Factuel":      {"url": "factuel.afp.com",     "lang": "fr", "speciality": "general"},
    "LeDecodeur":       {"url": "lemonde.fr/decodeurs","lang": "fr", "speciality": "politics"},
    "Snopes":           {"url": "snopes.com",          "lang": "en", "speciality": "general"},
    "PolitiFact":       {"url": "politifact.com",      "lang": "en", "speciality": "politics"},
    "FullFact":         {"url": "fullfact.org",        "lang": "en", "speciality": "general"},
    "EUvsDisinfo":      {"url": "euvsdisinfo.eu",      "lang": "multi","speciality": "eu_russia"},
    "DFRLab":           {"url": "digitalsherlocks.org","lang": "en", "speciality": "io_attribution"},
    "BellingCat":       {"url": "bellingcat.com",      "lang": "en", "speciality": "osint_geoint"},
}

_COUNTER_NARRATIVE_STRATEGIES = {
    "prebunking": {
        "name": "Prebunking (inoculation)",
        "desc": "Exposer la technique de manipulation AVANT qu'elle soit utilisée",
        "effectiveness": 0.78,
        "timing": "PROACTIVE",
        "example": "Avertir: 'Des comptes vont bientôt prétendre que...'",
    },
    "debunking": {
        "name": "Debunking (réfutation)",
        "desc": "Corriger une désinformation après sa diffusion",
        "effectiveness": 0.55,
        "timing": "REACTIVE",
        "pitfall": "Risque de backfire effect — renforcer la croyance en répétant le mensonge",
        "best_practice": "Fact sandwich: vrai-faux-vrai",
    },
    "narrative_bridge": {
        "name": "Pont narratif",
        "desc": "Reconnaître la préoccupation légitime derrière la désinformation",
        "effectiveness": 0.70,
        "timing": "REACTIVE",
        "example": "La méfiance envers les institutions est compréhensible. Voilà pourquoi les preuves montrent que...",
    },
    "trusted_voices": {
        "name": "Voix de confiance",
        "desc": "Utiliser des messagers ayant la confiance de l'audience cible",
        "effectiveness": 0.82,
        "timing": "BOTH",
        "examples": ["Médecins pour vax", "Anciens militaires contre disinfo", "Leaders religieux locaux"],
    },
    "systemic_reporting": {
        "name": "Signalement systématique",
        "desc": "Alerter les plateformes, régulateurs, journalistes sur les campagnes détectées",
        "effectiveness": 0.65,
        "timing": "REACTIVE",
        "channels": ["Signalement plateforme", "DSA (EU)", "ARCOM (FR)", "Médias mainstream"],
    },
    "media_literacy_campaign": {
        "name": "Campagne d'éducation aux médias",
        "desc": "Formation de masse aux techniques de manipulation",
        "effectiveness": 0.68,
        "timing": "PROACTIVE",
        "tools": ["Go Viral", "Bad News", "Inoculation games"],
    },
}

_MONITORING_SOURCES = {
    "social_media": ["Twitter/X API", "CrowdTangle", "Facebook Ad Library", "TikTok Research API"],
    "web_monitoring": ["GDELT Project", "Common Crawl", "NewsAPI", "MediaCloud"],
    "darkweb_forums": ["Telegram Monitor", "4chan/8kun crawlers", "VK monitoring"],
    "official_channels": ["Government APIs", "Press release feeds", "Fact-check RSS feeds"],
    "academic_tools": ["Stanford Internet Observatory", "Harvard Shorenstein Center"],
}


class NarrativeMonitorService:

    def list_narrative_categories(self) -> Dict:
        return {k: {"name": v["name"], "risk": v["risk"], "velocity": v["velocity"]}
                for k, v in _NARRATIVE_CATEGORIES.items()}

    def list_fact_check_orgs(self) -> Dict:
        return _FACT_CHECK_ORGS

    def list_counter_strategies(self) -> Dict:
        return {k: {"name": v["name"], "effectiveness": v["effectiveness"], "timing": v["timing"]}
                for k, v in _COUNTER_NARRATIVE_STRATEGIES.items()}

    def list_monitoring_sources(self) -> Dict:
        return _MONITORING_SOURCES

    def start_monitoring(
        self,
        keywords: List[str],
        categories: Optional[List[str]] = None,
        platforms: Optional[List[str]] = None,
        alert_threshold: int = 100,
    ) -> Dict:
        monitor_id = str(uuid.uuid4())
        cats = categories or list(_NARRATIVE_CATEGORIES.keys())[:3]

        monitor = {
            "monitor_id":      monitor_id,
            "keywords":        keywords,
            "categories":      cats,
            "platforms":       platforms or ["twitter_x","telegram","facebook"],
            "alert_threshold": alert_threshold,
            "status":          "active",
            "created_at":      datetime.utcnow().isoformat(),
            "simulated_stats": {
                "mentions_24h":      random.randint(50, 5000),
                "trending_score":    round(random.uniform(0.1, 0.9), 2),
                "accounts_involved": random.randint(10, 500),
                "bot_estimate_pct":  round(random.uniform(5, 40), 1),
                "top_platform":      random.choice(platforms or ["twitter_x","telegram"]),
            },
            "simulated":       True,
        }
        _MONITORS[monitor_id] = monitor
        return monitor

    def detect_coordinated_behavior(
        self,
        keywords: List[str],
        time_window_hours: int = 24,
    ) -> Dict:
        alert_id = str(uuid.uuid4())

        signals = []
        cib_score = 0.0

        posting_variance = random.uniform(0.01, 0.15)
        if posting_variance < 0.05:
            signals.append({"signal": "Variance temporelle très faible", "severity": "HIGH",
                            "value": posting_variance, "threshold": 0.05})
            cib_score += 0.3

        similarity = random.uniform(0.4, 0.98)
        if similarity > 0.7:
            signals.append({"signal": "Similarité de contenu élevée entre comptes", "severity": "HIGH",
                            "value": similarity, "threshold": 0.7})
            cib_score += 0.3

        new_accounts_pct = random.uniform(5, 60)
        if new_accounts_pct > 30:
            signals.append({"signal": f"{new_accounts_pct:.0f}% des comptes créés récemment", "severity": "MEDIUM",
                            "value": new_accounts_pct})
            cib_score += 0.2

        network_density = random.uniform(0.1, 0.9)
        if network_density > 0.6:
            signals.append({"signal": "Densité réseau artificielle (clustering)", "severity": "HIGH",
                            "value": network_density})
            cib_score += 0.2

        verdict = "COORDINATED_INAUTHENTIC" if cib_score > 0.6 else \
                  ("SUSPICIOUS" if cib_score > 0.3 else "ORGANIC")

        alert = {
            "alert_id":       alert_id,
            "keywords":       keywords,
            "time_window_hours": time_window_hours,
            "signals":        signals,
            "cib_score":      round(cib_score, 2),
            "verdict":        verdict,
            "accounts_flagged": random.randint(5, 200) if cib_score > 0.3 else 0,
            "recommended_actions": [
                "Signaler aux équipes trust & safety des plateformes" if verdict != "ORGANIC" else "Continuer surveillance",
                "Activer contre-narratif préventif" if cib_score > 0.5 else "Monitoring renforcé",
            ],
            "detected_at":    datetime.utcnow().isoformat(),
            "simulated":      True,
        }
        _ALERTS[alert_id] = alert
        return alert

    def generate_counter_narrative(
        self,
        false_claim: str,
        strategy: str = "debunking",
        target_audience: str = "general",
        evidence_links: Optional[List[str]] = None,
    ) -> Dict:
        strat = _COUNTER_NARRATIVE_STRATEGIES.get(strategy, _COUNTER_NARRATIVE_STRATEGIES["debunking"])

        if strategy == "prebunking":
            message = f"⚠️ Alerte: Des messages vont prétendre que «{false_claim[:80]}». Voici pourquoi c'est une technique de manipulation et non un fait établi."
        elif strategy == "fact_sandwich":
            message = f"✅ FAIT: [Insérer la vérité]. ❌ FAUX: Certains affirment «{false_claim[:60]}». ✅ RAPPEL: [Répéter la vérité avec source]."
        elif strategy == "trusted_voices":
            message = f"Des experts reconnus dans le domaine confirment que «{false_claim[:60]}» est inexact. Voici pourquoi [source crédible]."
        else:
            message = f"Cette affirmation — «{false_claim[:60]}» — est inexacte. Les preuves disponibles montrent [fait + source]."

        pitfalls = [strat.get("pitfall","")] if strat.get("pitfall") else []

        return {
            "false_claim":       false_claim,
            "strategy":          strategy,
            "strategy_name":     strat["name"],
            "target_audience":   target_audience,
            "counter_message":   message,
            "effectiveness":     strat["effectiveness"],
            "timing":            strat["timing"],
            "pitfalls":          pitfalls,
            "evidence_links":    evidence_links or ["https://factuel.afp.com", "https://euvsdisinfo.eu"],
            "fact_check_orgs":   list(_FACT_CHECK_ORGS.keys())[:3],
            "distribution_channels": ["Owned media", "Trusted voices network", "Paid promotion si budget"],
            "simulated":         True,
        }

    def get_monitor(self, monitor_id: str) -> Dict:
        return _MONITORS.get(monitor_id, {"error": "not_found"})

    def list_monitors(self) -> Dict:
        return {"monitors": [{"monitor_id": k, "keywords": v["keywords"], "status": v["status"]}
                              for k, v in _MONITORS.items()]}

    def get_alert(self, alert_id: str) -> Dict:
        return _ALERTS.get(alert_id, {"error": "not_found"})
