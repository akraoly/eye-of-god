"""
Dark Web Intelligence — Bloc 6 OSINT Géopolitique
Sources : Tor .onion sites, I2P, Freenet, Paste sites (Pastebin/Ghostbin),
          Dark web markets, Telegram channels, IRC channels chiffrés
Capacités : threat monitoring, credential leaks, malware samples,
            forum threat actor tracking, ransomware gang tracking
"""
from __future__ import annotations

import hashlib
import logging
import random
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)
_SESSIONS: Dict[str, Dict] = {}
_OUTPUT = Path("./data/geoint/darkweb")

_KNOWN_MARKETS = [
    {"name": "RuTor",       "status": "ACTIVE",   "type": "carding/malware",    "language": "ru"},
    {"name": "BreachForums","status": "ACTIVE",   "type": "data_breach_market", "language": "en"},
    {"name": "XSS.is",      "status": "ACTIVE",   "type": "hacking_forum",      "language": "ru"},
    {"name": "Exploit.in",  "status": "ACTIVE",   "type": "exploit_market",     "language": "ru"},
    {"name": "RAMP",        "status": "ACTIVE",   "type": "ransomware_forum",   "language": "ru"},
    {"name": "Nulled",      "status": "ACTIVE",   "type": "cracking_forum",     "language": "en"},
    {"name": "Genesis",     "status": "SEIZED",   "type": "stealer_market",     "language": "en"},
    {"name": "AlphaBay",    "status": "SEIZED",   "type": "general_market",     "language": "en"},
    {"name": "Hydra",       "status": "SEIZED",   "type": "general_market",     "language": "ru"},
]

_RANSOMWARE_GANGS = {
    "LockBit":    {"status": "DISRUPTED_REBRANDED", "victims_count": 2000, "language": "ru/cn"},
    "BlackCat":   {"status": "DISRUPTED_REBRANDED", "victims_count": 500, "language": "ru"},
    "Cl0p":       {"status": "ACTIVE", "victims_count": 600, "language": "ru"},
    "RansomHub":  {"status": "ACTIVE", "victims_count": 300, "language": "ru"},
    "Play":       {"status": "ACTIVE", "victims_count": 400, "language": "ru"},
    "Akira":      {"status": "ACTIVE", "victims_count": 250, "language": "ru"},
    "DragonForce":{"status": "ACTIVE", "victims_count": 80, "language": "en/my"},
    "Qilin":      {"status": "ACTIVE", "victims_count": 150, "language": "ru/cn"},
}

_PASTE_TYPES = ["credentials", "database_dump", "source_code", "config_leak",
                "internal_docs", "crypto_keys", "pii_data", "gov_documents"]

_TOR_HIDDEN_SERVICES = [
    "facebookwkhpilnemxj7asber7gjnd46dsgb3ggn6g24nmjlx3hih3ad.onion",
    "duckduckgogg42xjoc72x3sjasowoarfbgcmvfimaftt6twagswzczad.onion",
    "nytimesn7cgmftshazwhfgzm37qxb44r64ytbb2dj3x62d2lljsciiyd.onion",
]

_THREAT_KEYWORDS = ["0day", "exploit", "ransomware", "corporate_data", "gov_leak",
                     "insider_threat", "aapt_tool", "C2_server", "botnet_sale"]


def _gen_paste() -> Dict:
    ptype = random.choice(_PASTE_TYPES)
    return {
        "paste_id": hashlib.md5(str(random.random()).encode()).hexdigest()[:10],
        "site": random.choice(["Pastebin", "Ghostbin", "0bin", "Privatebin", "rentry.co"]),
        "type": ptype,
        "posted": (datetime.utcnow() - timedelta(hours=random.randint(1, 720))).isoformat(),
        "size_kb": round(random.uniform(0.5, 500), 1),
        "keywords_found": random.sample(_THREAT_KEYWORDS, k=random.randint(1, 3)),
        "contains_emails": random.random() > 0.5,
        "contains_hashes": random.random() > 0.4,
        "author": "anonymous" if random.random() > 0.3 else f"user_{random.randint(1000,9999)}",
        "relevance_score": round(random.uniform(0.3, 0.99), 2),
    }


def _gen_forum_post() -> Dict:
    gang = random.choice(list(_RANSOMWARE_GANGS.keys()) + [None, None])
    return {
        "forum": random.choice([m["name"] for m in _KNOWN_MARKETS if m["status"] == "ACTIVE"]),
        "thread_id": str(random.randint(100000, 999999)),
        "author": f"th_{random.randint(1000,9999)}",
        "posted": (datetime.utcnow() - timedelta(hours=random.randint(1, 168))).isoformat(),
        "topic": random.choice([
            "New 0day for [PRODUCT] — auction",
            "Corporate data dump — [COMPANY]",
            "RaaS affiliate program recruitment",
            "Botnet 50k nodes — rent per hour",
            "Initial access broker — Fortune 500",
            "Fresh stealer logs — [COUNTRY]",
        ]),
        "ransomware_gang": gang,
        "price_btc": round(random.uniform(0.1, 50), 2) if random.random() > 0.5 else None,
        "views": random.randint(10, 5000),
        "replies": random.randint(0, 200),
        "threat_score": round(random.uniform(0.4, 0.99), 2),
    }


class DarkWebService:
    """Dark web monitoring — threat actors, leaks, ransomware gangs."""

    def monitor_keywords(self, keywords: List[str],
                          sources: Optional[List[str]] = None,
                          depth: str = "standard") -> Dict:
        """Monitorer dark web pour mots-clés / entités."""
        session_id = str(uuid.uuid4())
        sources = sources or ["paste_sites", "forums", "markets", "telegram"]

        results = {
            "paste_hits": [],
            "forum_hits": [],
            "market_hits": [],
            "telegram_hits": [],
        }

        for kw in keywords:
            # Pastes
            for _ in range(random.randint(0, 4)):
                p = _gen_paste()
                p["matched_keyword"] = kw
                results["paste_hits"].append(p)

            # Forums
            for _ in range(random.randint(0, 3)):
                post = _gen_forum_post()
                post["matched_keyword"] = kw
                results["forum_hits"].append(post)

        total_hits = sum(len(v) for v in results.values())
        return {
            "session_id": session_id,
            "keywords_monitored": keywords,
            "sources": sources,
            "total_hits": total_hits,
            "results": results,
            "high_priority": [h for h in results["forum_hits"] if h.get("threat_score", 0) > 0.85],
            "monitoring_timestamp": datetime.utcnow().isoformat(),
            "simulated": True,
        }

    def search_credential_leaks(self, email_or_domain: str) -> Dict:
        """Rechercher credentials d'une organisation dans dumps dark web."""
        session_id = str(uuid.uuid4())
        domain = email_or_domain.split("@")[-1]
        leaks = []
        num = random.randint(0, 8)
        for _ in range(num):
            breach_date = datetime.utcnow() - timedelta(days=random.randint(30, 1800))
            leaks.append({
                "breach_name": random.choice(["Collection#1", "RockYou2024", "LinkedIn2023",
                                               "Corporate Dump 2025", "SteamDB", "LastPass2022"]),
                "date": breach_date.strftime("%Y-%m"),
                "emails_found": random.randint(1, 500),
                "has_passwords": random.random() > 0.5,
                "password_format": random.choice(["plaintext", "md5", "bcrypt", "sha1", "unknown"]),
                "source": random.choice(["BreachForums", "RaidForums archive", "Pastebin", "Unknown"]),
                "sample": f"{random.choice(['john','admin','user','info'])}@{domain}:P@ss{random.randint(1000,9999)}",
            })
        return {
            "session_id": session_id,
            "target": email_or_domain,
            "domain": domain,
            "breach_count": num,
            "leaks": leaks,
            "risk_level": "CRITICAL" if num > 5 else "HIGH" if num > 2 else "LOW",
            "recommendations": ["Force password reset", "Enable MFA", "Monitor active sessions"] if num > 0 else [],
            "simulated": True,
        }

    def track_ransomware_gang(self, gang_name: str = "LockBit") -> Dict:
        """Suivre activités d'un groupe ransomware."""
        session_id = str(uuid.uuid4())
        info = _RANSOMWARE_GANGS.get(gang_name, {"status": "UNKNOWN", "victims_count": 0, "language": "unknown"})

        recent_victims = []
        for _ in range(random.randint(0, 8)):
            victim_date = datetime.utcnow() - timedelta(days=random.randint(0, 30))
            recent_victims.append({
                "company": f"{random.choice(['Acme','Global','Euro','Pacific','Nord'])} {random.choice(['Corp','Systems','Industries','Group','Ltd'])}",
                "country": random.choice(["USA", "UK", "Germany", "France", "Italy", "Spain", "Australia"]),
                "sector": random.choice(["Healthcare", "Finance", "Manufacturing", "Government", "Education"]),
                "revenue_est": f"${random.randint(10, 5000)}M",
                "data_gb_stolen": random.randint(10, 5000),
                "ransom_demanded_btc": round(random.uniform(10, 500), 2),
                "ransom_paid": random.random() > 0.7,
                "publish_deadline": (victim_date + timedelta(days=7)).strftime("%Y-%m-%d"),
                "date": victim_date.strftime("%Y-%m-%d"),
            })

        return {
            "session_id": session_id,
            "gang": gang_name,
            "status": info["status"],
            "total_known_victims": info["victims_count"],
            "language": info["language"],
            "recent_30d_victims": recent_victims,
            "leak_site_active": info["status"] == "ACTIVE",
            "ttps": random.sample(["T1486", "T1490", "T1041", "T1078", "T1566", "T1055"], k=4),
            "simulated": True,
        }

    def monitor_markets(self, search_terms: List[str] = None) -> Dict:
        """Surveiller marchés dark web pour produits/services offensifs."""
        session_id = str(uuid.uuid4())
        search_terms = search_terms or ["0day", "initial access", "stealer"]

        listings = []
        for term in search_terms:
            for _ in range(random.randint(0, 5)):
                listings.append({
                    "market": random.choice([m["name"] for m in _KNOWN_MARKETS if m["status"] == "ACTIVE"]),
                    "title": f"{term} — {random.choice(['premium', 'fresh', 'bulk', 'exclusive'])}",
                    "category": random.choice(["exploit", "access", "data", "tool", "service"]),
                    "price_usd": random.randint(50, 50000),
                    "seller_reputation": f"{random.randint(50, 500)} deals",
                    "posted": (datetime.utcnow() - timedelta(hours=random.randint(1, 720))).isoformat(),
                    "keywords_matched": [term],
                })

        return {
            "session_id": session_id,
            "search_terms": search_terms,
            "listings_found": len(listings),
            "listings": listings,
            "markets_active": [m for m in _KNOWN_MARKETS if m["status"] == "ACTIVE"],
            "simulated": True,
        }

    def onion_crawl(self, onion_url: str = "", depth: int = 2) -> Dict:
        """Crawler un service .onion — extraction liens et contenu."""
        session_id = str(uuid.uuid4())
        pages = []
        for i in range(random.randint(3, 15)):
            pages.append({
                "url": onion_url or f"{hashlib.md5(str(i).encode()).hexdigest()[:16]}.onion/{random.choice(['forum','market','paste','admin','login'])}",
                "title": random.choice(["Forum — Main", "Shop — Index", "Admin Panel", "Members Area", "Upload"]),
                "status_code": random.choice([200, 200, 200, 403, 404]),
                "links_found": random.randint(0, 50),
                "forms_found": random.randint(0, 5),
                "credentials_in_page": random.random() > 0.8,
                "technologies": random.sample(["PHP", "Python/Flask", "Apache", "Nginx", "MySQL"], k=random.randint(1, 3)),
            })
        return {
            "session_id": session_id,
            "seed_url": onion_url,
            "depth": depth,
            "pages_crawled": len(pages),
            "pages": pages,
            "credentials_found": sum(1 for p in pages if p["credentials_in_page"]),
            "simulated": True,
        }

    def list_ransomware_gangs(self) -> List[Dict]:
        return [{"name": k, **v} for k, v in _RANSOMWARE_GANGS.items()]

    def list_known_markets(self) -> List[Dict]:
        return _KNOWN_MARKETS
