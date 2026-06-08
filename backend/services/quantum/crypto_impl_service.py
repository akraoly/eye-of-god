"""
Crypto Implementation Attacks — Bloc 8 Quantum & Cryptographie
Timing side-channel, attaque ECDSA k-reuse (nonce Sony PS3), fault injection,
cold boot attack, DPA/SPA sur implémentations matérielles.
"""
from __future__ import annotations

import hashlib
import logging
import os
import random
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

_RESULTS: Dict[str, Dict] = {}
_OUTPUT = Path("./data/quantum/impl_attacks")
_OUTPUT.mkdir(parents=True, exist_ok=True)

_TIMING_ATTACKS = {
    "rsa_timing": {
        "name": "Timing Attack on RSA (Kocher 1996)",
        "target": "RSA private key exponentiation",
        "technique": "Mesure du temps de déchiffrement — corrélation avec bits de la clé privée",
        "samples_needed": "~1 million de mesures",
        "precision_required_ns": 1,
        "mitigation": ["Montgomery ladder", "Constant-time modexp", "Blinding (RSA + randomized exponent)"],
        "real_attacks": ["OpenSSL < 0.9.7 (2003)", "Various smart card implementations"],
    },
    "ecdsa_timing": {
        "name": "Timing Attack on ECDSA scalar multiplication",
        "target": "ECDSA private key via point multiplication timing",
        "samples_needed": "~300 traces",
        "mitigation": ["Constant-time point multiplication", "wNAF with constant-time", "Random projective coordinates"],
    },
    "aes_cache_timing": {
        "name": "Cache Timing Attack on AES (Bernstein 2005)",
        "target": "AES S-box table lookups → cache miss patterns → key recovery",
        "variants": ["Bernstein's L3 cache attack", "Brumley & Boneh (OpenSSL AES)", "Cross-VM attacks"],
        "samples_needed": "~2^23 AES operations",
        "mitigation": ["AES-NI hardware instruction (constant-time)", "Software constant-time AES (bitsliced)"],
        "real_attacks": ["OpenSSL AES vulnerability (2005)", "Flush+Reload variant"],
    },
    "hmac_timing": {
        "name": "Timing Attack on HMAC comparison",
        "target": "String comparison early exit leaks length of match",
        "technique": "Measure response time differences for wrong vs. correct MAC byte-by-byte",
        "samples_per_byte": 1000,
        "mitigation": ["hmac.compare_digest() in Python", "crypto.timingSafeEqual() in Node.js", "Constant-time comparison"],
        "real_attacks": ["Keyczar library (2009)", "Various web API frameworks"],
    },
    "lattice_timing": {
        "name": "Lattice Attack via Biased Nonces (ECDSA/DSA)",
        "target": "ECDSA private key from many signatures with slightly biased k",
        "technique": "Even 1-2 bits of nonce leakage → HNP (Hidden Number Problem) → LLL lattice reduction",
        "samples_needed": "~200 signatures for 1-bit bias, ~50 for 4-bit bias",
        "tool": "latticehacks, ecdsa-nonce-analysis",
        "real_attacks": ["PS3 ECDSA hack (fixed k)", "Bitcoin nonce bias attacks"],
    },
}

_FAULT_ATTACKS = {
    "differential_fault_analysis": {
        "name": "Differential Fault Analysis (DFA) on AES",
        "technique": "Injecter une faute avant le dernier round d'AES — comparer output correct vs. faulted",
        "faults_needed": 2,
        "key_bits_recovered": 128,
        "fault_methods": ["Voltage glitching", "EM pulse injection", "Laser fault injection", "Clock glitching"],
        "real_attacks": ["AES DFA by Tunstall et al.", "Multiple smart card attacks"],
        "mitigation": ["Double computation + compare", "Fault detection sensors", "Infective computation"],
    },
    "rsa_dfa": {
        "name": "RSA CRT Fault Attack (Bellcore)",
        "technique": "Faute pendant CRT computation → GCD(faulty_sig, N) révèle un facteur de N",
        "faults_needed": 1,
        "consequence": "Private key entièrement récupéré avec 1 seule faute!",
        "real_attacks": ["OpenCard smart card", "Multiple HSM attacks"],
        "mitigation": ["Vérification de signature avant renvoi", "Bellcore countermeasure check"],
    },
    "clock_glitching": {
        "name": "Clock Glitching",
        "technique": "Spike dans le signal d'horloge → processeur saute une instruction",
        "targets": ["Secure boot bypass", "PIN verification skip", "Crypto key extraction"],
        "hardware": ["ChipWhisperer", "Glitchy Glitcher", "Custom FPGA"],
        "real_attacks": ["ESP32 secure boot bypass", "Various embedded secure elements"],
        "mitigation": ["Glitch detection circuits", "Redundant computation", "Power filtering"],
    },
    "voltage_glitching": {
        "name": "Voltage Glitching (VCC glitch)",
        "technique": "Chute de tension momentanée → état indéfini du CPU",
        "targets": ["Same as clock glitching + memory corruption"],
        "hardware": ["ChipWhisperer-Lite", "Custom crowbar circuit"],
        "mitigation": ["Voltage detector circuits", "Supply voltage filtering", "Secure MCU with glitch detection"],
    },
}

_NONCE_ATTACKS = {
    "ps3_fixed_k": {
        "name": "PS3 ECDSA Fixed Nonce Attack (fail0verflow 2010)",
        "description": "Sony utilisait k constant pour toutes les signatures ECDSA sur PS3",
        "key_recovery": "Avec deux messages m1, m2 signés avec le même k: privkey = (H(m1)-H(m2)) * (s1-s2)^-1 mod n",
        "equations": [
            "s1 = k^-1 * (H(m1) + privkey * r) mod n",
            "s2 = k^-1 * (H(m2) + privkey * r) mod n",
            "s1 - s2 = k^-1 * (H(m1) - H(m2)) mod n",
            "k = (H(m1) - H(m2)) * (s1-s2)^-1 mod n",
            "privkey = (s1*k - H(m1)) * r^-1 mod n",
        ],
        "impact": "Clé privée ECDSA récupérée → PS3 homebrew / piratage",
        "lesson": "Nonce k DOIT être aléatoire ou déterministe (RFC 6979) — JAMAIS constant",
        "mitigation": "RFC 6979 deterministic ECDSA (k dérivé via HMAC-DRBG)",
    },
    "bitcoin_nonce_reuse": {
        "name": "Bitcoin Wallet Nonce Reuse",
        "description": "Bugs dans certains wallets Bitcoin réutilisaient k entre transactions",
        "real_attacks": ["Android SecureRandom bug (2013) — ~50 BTC volés"],
        "impact": "Clé privée Bitcoin récupérée → fonds volés",
        "mitigation": "RFC 6979, CSPRNG de qualité, audit code crypto",
    },
}

_COLD_BOOT = {
    "technique": "Cold Boot Attack (Halderman 2008)",
    "target": "RAM contents including AES/RSA keys in memory",
    "method": [
        "Couper l'alimentation puis redémarrer sur USB live system",
        "Ou refroidir la RAM (azote liquide) pour prolonger rétention des données",
        "Lire le contenu de la RAM avec dd / custom tools",
        "Utiliser aeskeyfind/rsakeyfind pour localiser les clés en mémoire",
    ],
    "retention_time": {
        "room_temp_20C":   "~3 seconds",
        "cold_0C":         "~60 seconds",
        "liquid_nitrogen": "~1 hour",
    },
    "tools": ["aeskeyfind", "rsakeyfind", "cryptkeeper", "msramdump"],
    "real_attacks": ["FDE bypass (BitLocker, FileVault, dm-crypt)", "RAM forensics"],
    "mitigation": ["Full power-off (not sleep/hibernate)", "Memory encryption (AMD SME/SEV)", "TPM-backed key storage"],
}


class CryptoImplService:

    def list_timing_attacks(self) -> Dict:
        return {k: {"name": v["name"], "samples_needed": v.get("samples_needed","N/A")}
                for k, v in _TIMING_ATTACKS.items()}

    def get_timing_attack_detail(self, attack: str) -> Dict:
        return _TIMING_ATTACKS.get(attack, {"error": "not_found"})

    def list_fault_attacks(self) -> Dict:
        return {k: {"name": v["name"], "faults_needed": v.get("faults_needed","N/A")}
                for k, v in _FAULT_ATTACKS.items()}

    def list_nonce_attacks(self) -> Dict:
        return _NONCE_ATTACKS

    def get_cold_boot_info(self) -> Dict:
        return _COLD_BOOT

    def simulate_ecdsa_nonce_reuse(
        self,
        signatures: Optional[List[Dict]] = None,
    ) -> Dict:
        """Simule la récupération de clé privée ECDSA par réutilisation de nonce."""
        result_id = str(uuid.uuid4())

        k_fixed = int.from_bytes(os.urandom(32), 'big')
        privkey = int.from_bytes(os.urandom(32), 'big')
        curve_order_approx = 2**256 - 2**32 - 2**9 - 2**8 - 2**7 - 2**6 - 2**4 - 1

        m1 = os.urandom(32)
        m2 = os.urandom(32)
        h1 = int.from_bytes(hashlib.sha256(m1).digest(), 'big')
        h2 = int.from_bytes(hashlib.sha256(m2).digest(), 'big')

        r  = random.randint(1, curve_order_approx)
        s1 = random.randint(1, curve_order_approx)
        s2 = random.randint(1, curve_order_approx)

        result = {
            "result_id":       result_id,
            "attack":          "ECDSA Nonce Reuse (same k for two signatures)",
            "vulnerability":   "k réutilisé entre deux signatures → private key recoverable",
            "message1_hash":   hex(h1)[:20] + "...",
            "message2_hash":   hex(h2)[:20] + "...",
            "signature1":      {"r": hex(r)[:20]+"...", "s": hex(s1)[:20]+"..."},
            "signature2":      {"r": hex(r)[:20]+"...", "s": hex(s2)[:20]+"..."},
            "recovery_steps":  _NONCE_ATTACKS["ps3_fixed_k"]["equations"],
            "recovered_k":     hex(k_fixed)[:20] + "... (simulated)",
            "recovered_privkey": hex(privkey)[:20] + "... (simulated)",
            "key_compromised": True,
            "mitigation":      "RFC 6979 deterministic nonce generation",
            "simulated":       True,
        }
        _RESULTS[result_id] = result
        return result

    def simulate_timing_oracle(
        self,
        attack_type: str,
        samples: int = 10000,
    ) -> Dict:
        result_id = str(uuid.uuid4())
        attack    = _TIMING_ATTACKS.get(attack_type, _TIMING_ATTACKS["hmac_timing"])

        # Simulation des mesures de timing
        measurements = []
        recovered_bits = []
        for bit_pos in range(min(8, samples // 1000)):
            correct_time = random.gauss(1000, 50)
            wrong_time   = random.gauss(980, 50)
            bit_value    = 1 if correct_time > wrong_time else 0
            measurements.append({
                "bit_position": bit_pos,
                "time_correct_ns": round(correct_time, 2),
                "time_wrong_ns":   round(wrong_time, 2),
                "bit_recovered":   bit_value,
            })
            recovered_bits.append(str(bit_value))

        return {
            "result_id":        result_id,
            "attack_type":      attack_type,
            "attack_name":      attack["name"],
            "samples_measured": samples,
            "bits_recovered":   len(recovered_bits),
            "recovered_key_bits": "0b" + "".join(recovered_bits),
            "measurements_sample": measurements[:3],
            "timing_delta_avg_ns": round(random.uniform(5, 50), 2),
            "success":          True,
            "mitigation":       attack["mitigation"],
            "simulated":        True,
        }

    def analyze_crypto_implementation(self, code_snippet: str, language: str = "python") -> Dict:
        issues = []
        score  = 100

        checks = {
            "hardcoded_key":   any(x in code_snippet.lower() for x in ["key = b\"", "key = '", "secret = \"", "password = \"123"]),
            "ecb_mode":        "ecb" in code_snippet.lower() or "mode.ECB" in code_snippet,
            "weak_random":     any(x in code_snippet for x in ["random.random()", "random.randint", "Math.random", "rand()"]),
            "md5_usage":       "md5" in code_snippet.lower() and "hmac" not in code_snippet.lower(),
            "sha1_usage":      "sha1" in code_snippet.lower() and "hmac" not in code_snippet.lower(),
            "string_compare":  any(x in code_snippet for x in ["== expected", "!= mac", "== token"]),
            "no_salt":         "hash" in code_snippet.lower() and "salt" not in code_snippet.lower() and "password" in code_snippet.lower(),
            "rc4_usage":       "rc4" in code_snippet.lower() or "arcfour" in code_snippet.lower(),
            "des_usage":       "des" in code_snippet.lower() and "3des" not in code_snippet.lower(),
            "fixed_iv":        any(x in code_snippet for x in ["iv = b\"\\x00", "iv = bytes(16)"]),
        }

        if checks["hardcoded_key"]:
            issues.append({"severity": "CRITICAL", "issue": "Clé hardcodée dans le code", "cwe": "CWE-321"})
            score -= 30
        if checks["ecb_mode"]:
            issues.append({"severity": "CRITICAL", "issue": "Mode ECB utilisé (pas de sécurité sémantique)", "cwe": "CWE-327"})
            score -= 25
        if checks["rc4_usage"]:
            issues.append({"severity": "CRITICAL", "issue": "RC4 utilisé (stream cipher cassé)", "cwe": "CWE-327"})
            score -= 25
        if checks["des_usage"]:
            issues.append({"severity": "CRITICAL", "issue": "DES utilisé (56-bit, cassé)", "cwe": "CWE-327"})
            score -= 20
        if checks["weak_random"]:
            issues.append({"severity": "HIGH", "issue": "PRNG non cryptographique pour usage crypto", "cwe": "CWE-338"})
            score -= 20
        if checks["md5_usage"]:
            issues.append({"severity": "HIGH", "issue": "MD5 pour hachage cryptographique (collision triviale)", "cwe": "CWE-327"})
            score -= 15
        if checks["sha1_usage"]:
            issues.append({"severity": "HIGH", "issue": "SHA1 pour hachage (SHAttered — collision en 2017)", "cwe": "CWE-327"})
            score -= 10
        if checks["string_compare"]:
            issues.append({"severity": "HIGH", "issue": "Comparaison MAC/token non constant-time (timing oracle)", "cwe": "CWE-208"})
            score -= 15
        if checks["no_salt"]:
            issues.append({"severity": "HIGH", "issue": "Hash de mot de passe sans sel (rainbow table)", "cwe": "CWE-916"})
            score -= 15
        if checks["fixed_iv"]:
            issues.append({"severity": "MEDIUM", "issue": "IV/nonce fixe ou nul détecté", "cwe": "CWE-329"})
            score -= 10

        grade = "A" if score >= 85 else ("B" if score >= 70 else ("C" if score >= 50 else ("D" if score >= 30 else "F")))

        return {
            "language":  language,
            "score":     max(0, score),
            "grade":     grade,
            "issues":    issues,
            "count":     len(issues),
            "critical":  len([i for i in issues if i["severity"] == "CRITICAL"]),
            "simulated": True,
        }

    def get_result(self, result_id: str) -> Dict:
        return _RESULTS.get(result_id, {"error": "not_found"})
