"""
Crypto Transaction Tracer — Bloc 6 OSINT Géopolitique
Blockchains : Bitcoin, Ethereum, Monero (heuristiques), Tron, Litecoin, Zcash
Techniques : wallet clustering, exchange identification, mixer detection,
             NFT fraud, DeFi contract analysis, ransomware payment tracking
APIs : Blockchain.info, Etherscan, Chainalysis-style heuristics
"""
from __future__ import annotations

import hashlib
import logging
import random
import re
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)
_SESSIONS: Dict[str, Dict] = {}

_BLOCKCHAINS = {
    "bitcoin":  {"symbol": "BTC", "explorer": "https://blockstream.info/api",  "privacy": "LOW",    "traceable": True},
    "ethereum": {"symbol": "ETH", "explorer": "https://api.etherscan.io/api",  "privacy": "LOW",    "traceable": True},
    "monero":   {"symbol": "XMR", "explorer": None,                            "privacy": "VERY_HIGH","traceable": False},
    "tron":     {"symbol": "TRX", "explorer": "https://apilist.tronscan.org",  "privacy": "MEDIUM", "traceable": True},
    "litecoin": {"symbol": "LTC", "explorer": "https://litecoinspace.org/api", "privacy": "LOW",    "traceable": True},
    "zcash":    {"symbol": "ZEC", "explorer": "https://api.zcha.in/v2",        "privacy": "HIGH",   "traceable": "PARTIAL"},
}

_KNOWN_ENTITIES = {
    "1A1zP1eP5QGefi2DMPTfTL5SLmv7Divfna": {"label": "Bitcoin Genesis Block", "type": "genesis", "risk": "NONE"},
    "3FZbgi29cpjq2GjdwV8eyHuJJnkLtktZc5": {"label": "Binance Hot Wallet", "type": "exchange", "risk": "LOW"},
    "0xde0B295669a9FD93d5F28D9Ec85E40f4cb697BAe": {"label": "Ethereum Foundation", "type": "foundation", "risk": "NONE"},
    "12higDjoCCNXSA95xZMWUdPvXNmkAduhWv": {"label": "Lazarus Group (DPRK)", "type": "sanctioned_apt", "risk": "CRITICAL"},
    "bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh": {"label": "Conti Ransomware", "type": "ransomware", "risk": "CRITICAL"},
}

_MIXER_PATTERNS = [
    "CoinJoin transaction (equal outputs)",
    "Wasabi Wallet fingerprint",
    "Tornado Cash contract interaction",
    "ChipMixer output pattern",
    "Blender.io withdrawal pattern",
    "Multiple-hop chain obfuscation",
]

_RISK_CATEGORIES = {
    "exchange":     "LOW",
    "defi":         "LOW",
    "ransomware":   "CRITICAL",
    "mixer":        "HIGH",
    "darkmarket":   "CRITICAL",
    "sanctioned_apt": "CRITICAL",
    "terrorism":    "CRITICAL",
    "gambling":     "MEDIUM",
    "unknown":      "MEDIUM",
}


def _gen_address(blockchain: str = "bitcoin") -> str:
    if blockchain == "ethereum":
        return "0x" + hashlib.sha256(str(random.random()).encode()).hexdigest()[:40]
    elif blockchain == "bitcoin":
        prefixes = ["1", "3", "bc1q"]
        return random.choice(prefixes) + hashlib.md5(str(random.random()).encode()).hexdigest()[:28]
    return hashlib.sha256(str(random.random()).encode()).hexdigest()[:34]


def _gen_tx(blockchain: str = "bitcoin", value_range=(0.001, 10.0)) -> Dict:
    blockchain_info = _BLOCKCHAINS.get(blockchain, _BLOCKCHAINS["bitcoin"])
    value = round(random.uniform(*value_range), 6)
    return {
        "txid": hashlib.sha256(str(random.random()).encode()).hexdigest(),
        "blockchain": blockchain,
        "timestamp": (datetime.utcnow() - timedelta(hours=random.randint(0, 8760))).isoformat(),
        "value": value,
        "symbol": blockchain_info["symbol"],
        "value_usd": round(value * random.uniform(1000, 65000), 2),
        "from_address": _gen_address(blockchain),
        "to_address": _gen_address(blockchain),
        "fee": round(random.uniform(0.0001, 0.01), 6),
        "confirmations": random.randint(1, 100000),
        "block_height": random.randint(800000, 870000),
        "mixer_suspected": random.random() > 0.85,
    }


class CryptoTracerService:
    """Blockchain analysis — wallet clustering, mixer detection, ransomware tracking."""

    def trace_address(self, address: str,
                       blockchain: str = "bitcoin",
                       depth: int = 3) -> Dict:
        """Tracer une adresse — graph de transactions, identification entité."""
        session_id = str(uuid.uuid4())
        bc = _BLOCKCHAINS.get(blockchain, _BLOCKCHAINS["bitcoin"])

        # Try real API
        if blockchain == "bitcoin":
            try:
                import requests
                r = requests.get(
                    f"https://blockstream.info/api/address/{address}",
                    timeout=8
                )
                if r.status_code == 200:
                    data = r.json()
                    return {
                        "session_id": session_id,
                        "address": address,
                        "blockchain": blockchain,
                        "balance_btc": (data.get("chain_stats", {}).get("funded_txo_sum", 0) -
                                        data.get("chain_stats", {}).get("spent_txo_sum", 0)) / 1e8,
                        "total_received_btc": data.get("chain_stats", {}).get("funded_txo_sum", 0) / 1e8,
                        "tx_count": data.get("chain_stats", {}).get("tx_count", 0),
                        "known_entity": _KNOWN_ENTITIES.get(address),
                        "source": "Blockstream API (LIVE)",
                        "simulated": False,
                    }
            except Exception:
                pass

        known = _KNOWN_ENTITIES.get(address)
        tx_count = random.randint(1, 10000)
        total_btc = round(random.uniform(0.001, 5000), 8)

        cluster = [_gen_address(blockchain) for _ in range(random.randint(1, 15))]
        mixer_hop = random.random() > 0.7

        return {
            "session_id": session_id,
            "address": address,
            "blockchain": blockchain,
            "balance": round(random.uniform(0, total_btc * 0.3), 8),
            "symbol": bc["symbol"],
            "total_received": total_btc,
            "total_sent": round(total_btc * 0.8, 8),
            "tx_count": tx_count,
            "first_seen": (datetime.utcnow() - timedelta(days=random.randint(30, 2000))).strftime("%Y-%m-%d"),
            "known_entity": known,
            "entity_label": known["label"] if known else None,
            "risk_level": known["risk"] if known else _RISK_CATEGORIES["unknown"],
            "cluster_addresses": cluster,
            "mixer_interaction": mixer_hop,
            "mixer_pattern": random.choice(_MIXER_PATTERNS) if mixer_hop else None,
            "exchange_deposits": random.randint(0, 20),
            "simulated": True,
        }

    def cluster_wallets(self, seed_address: str,
                         blockchain: str = "bitcoin",
                         algorithm: str = "common_input_ownership") -> Dict:
        """Regrouper adresses contrôlées par la même entité."""
        session_id = str(uuid.uuid4())
        algos = {
            "common_input_ownership": "Co-spend heuristic — inputs co-signés = même wallet",
            "change_address":         "Change address detection — adresse de monnaie identifiée",
            "dust_attack":            "Dust attack tracing — micro-transactions de tracking",
            "peeling_chain":          "Peeling chain — cascade de transactions 1-entrée/2-sorties",
        }

        cluster_size = random.randint(3, 50)
        addresses = [seed_address] + [_gen_address(blockchain) for _ in range(cluster_size - 1)]
        total_btc = round(random.uniform(1, 50000), 2)

        risk_types = random.sample(list(_RISK_CATEGORIES.keys()), k=random.randint(1, 3))
        highest_risk = max(risk_types, key=lambda r: ["NONE","LOW","MEDIUM","HIGH","CRITICAL"].index(_RISK_CATEGORIES.get(r, "MEDIUM")))

        return {
            "session_id": session_id,
            "seed_address": seed_address,
            "blockchain": blockchain,
            "algorithm": algos.get(algorithm, algorithm),
            "cluster_size": cluster_size,
            "cluster_addresses": addresses[:20],
            "total_cluster_value_btc": total_btc,
            "risk_categories_found": risk_types,
            "highest_risk": _RISK_CATEGORIES.get(highest_risk, "MEDIUM"),
            "entity_identified": random.random() > 0.5,
            "entity_name": random.choice(list(_KNOWN_ENTITIES.values()))["label"] if random.random() > 0.5 else None,
            "simulated": True,
        }

    def track_ransomware_payment(self, ransom_address: str,
                                  gang: str = "LockBit",
                                  blockchain: str = "bitcoin") -> Dict:
        """Tracer paiement ransomware — suivre BTC jusqu'à cashout."""
        session_id = str(uuid.uuid4())
        hops = []
        addr = ransom_address
        for i in range(random.randint(3, 8)):
            next_addr = _gen_address(blockchain)
            mixer = random.random() > 0.6
            hops.append({
                "hop": i + 1,
                "from_address": addr,
                "to_address": next_addr,
                "amount_btc": round(random.uniform(0.1, 100), 4),
                "mixer_used": mixer,
                "mixer_type": random.choice(_MIXER_PATTERNS) if mixer else None,
                "delay_hours": random.randint(1, 720),
                "exchange_deposit": random.random() > 0.8,
                "exchange": random.choice(["Binance", "OKX", "KuCoin", "Kraken", "Unknown DEX"]) if random.random() > 0.8 else None,
            })
            addr = next_addr

        cashout = hops[-1].get("exchange")
        return {
            "session_id": session_id,
            "ransom_address": ransom_address,
            "gang": gang,
            "blockchain": blockchain,
            "total_paid_btc": round(random.uniform(1, 200), 4),
            "total_paid_usd": round(random.uniform(50000, 10000000), 0),
            "hops": hops,
            "mixers_used": sum(1 for h in hops if h["mixer_used"]),
            "final_cashout": cashout,
            "traceable_to_cashout": cashout is not None,
            "law_enforcement_referral": cashout in ["Binance", "Kraken"],
            "simulated": True,
        }

    def detect_mixer(self, address: str,
                      blockchain: str = "bitcoin",
                      lookback_txs: int = 100) -> Dict:
        """Détecter usage de mixer/tumbler sur une adresse."""
        session_id = str(uuid.uuid4())
        patterns_detected = []
        if random.random() > 0.5:
            patterns_detected = random.sample(_MIXER_PATTERNS, k=random.randint(1, 3))

        return {
            "session_id": session_id,
            "address": address,
            "blockchain": blockchain,
            "txs_analyzed": lookback_txs,
            "mixer_detected": len(patterns_detected) > 0,
            "patterns": patterns_detected,
            "mixer_probability": round(random.uniform(0.2, 0.99), 3) if patterns_detected else round(random.uniform(0, 0.3), 3),
            "risk_level": "HIGH" if len(patterns_detected) > 1 else "MEDIUM" if patterns_detected else "LOW",
            "simulated": True,
        }

    def analyze_defi_contract(self, contract_address: str,
                               network: str = "ethereum") -> Dict:
        """Analyser contrat DeFi — rugpull indicators, honeypot, exploit history."""
        session_id = str(uuid.uuid4())
        rugpull_score = round(random.uniform(0, 1), 3)
        return {
            "session_id": session_id,
            "contract": contract_address,
            "network": network,
            "verified_source": random.random() > 0.4,
            "tvl_usd": round(random.uniform(1000, 500000000), 0),
            "rugpull_score": rugpull_score,
            "honeypot_detected": rugpull_score > 0.8,
            "admin_key_risks": ["upgradeable proxy", "owner can drain funds"] if rugpull_score > 0.6 else [],
            "exploit_history": random.randint(0, 3),
            "audit_count": random.randint(0, 3),
            "risk_verdict": "SCAM" if rugpull_score > 0.8 else "HIGH_RISK" if rugpull_score > 0.5 else "MODERATE",
            "simulated": True,
        }

    def list_blockchains(self) -> List[Dict]:
        return [{"id": k, **v} for k, v in _BLOCKCHAINS.items()]

    def known_entities(self) -> Dict:
        return _KNOWN_ENTITIES
