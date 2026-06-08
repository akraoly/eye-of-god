"""
Classical Crypto Attacks — Bloc 8 Quantum & Cryptographie
Padding oracle, BEAST/POODLE/CRIME/BREACH, hash collision (MD5/SHA1),
RSA common modulus / PKCS#1v1.5 Bleichenbacher, CBC bit-flip, Forbidden Attack (GCM nonce reuse).
Simulation — aucun serveur réel attaqué.
"""
from __future__ import annotations

import hashlib
import logging
import os
import random
import struct
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

_SESSIONS: Dict[str, Dict] = {}
_OUTPUT = Path("./data/quantum/crypto_attacks")
_OUTPUT.mkdir(parents=True, exist_ok=True)

_TLS_ATTACKS = {
    "BEAST": {
        "cve": "CVE-2011-3389",
        "affected": ["TLS 1.0 with CBC ciphers"],
        "mitigation": "TLS 1.1+, AEAD ciphers, 1/n-1 record splitting",
        "severity": "HIGH",
        "technique": "Chosen plaintext attack exploiting predictable CBC IV",
        "practical": True,
    },
    "POODLE": {
        "cve": "CVE-2014-3566",
        "affected": ["SSLv3", "TLS with SSLv3 fallback"],
        "mitigation": "Disable SSLv3 entirely, TLS_FALLBACK_SCSV",
        "severity": "HIGH",
        "technique": "Padding oracle on SSLv3 CBC",
        "practical": True,
    },
    "CRIME": {
        "cve": "CVE-2012-4929",
        "affected": ["TLS compression (DEFLATE)", "SPDY"],
        "mitigation": "Disable TLS compression",
        "severity": "HIGH",
        "technique": "Compression oracle — infer secrets from compressed ciphertext size",
        "practical": True,
    },
    "BREACH": {
        "cve": "CVE-2013-3587",
        "affected": ["HTTP compression (gzip/deflate)"],
        "mitigation": "Disable HTTP compression, CSRF tokens, secret masking",
        "severity": "MEDIUM",
        "technique": "HTTP-level compression oracle (attacker controls request, observes size)",
        "practical": True,
    },
    "HEARTBLEED": {
        "cve": "CVE-2014-0160",
        "affected": ["OpenSSL 1.0.1 – 1.0.1f"],
        "mitigation": "Patch OpenSSL, revoke/reissue certificates",
        "severity": "CRITICAL",
        "technique": "Buffer over-read in TLS heartbeat — leaks 64KB server memory",
        "practical": True,
        "data_leaked": "Private keys, session tokens, passwords",
    },
    "DROWN": {
        "cve": "CVE-2016-0800",
        "affected": ["Servers supporting SSLv2 with shared key"],
        "mitigation": "Disable SSLv2 on all servers sharing private key",
        "severity": "HIGH",
        "technique": "Cross-protocol attack: decrypt TLS using SSLv2 oracle",
        "practical": True,
    },
    "ROBOT": {
        "cve": "CVE-2017-13099",
        "affected": ["RSA PKCS#1v1.5 key exchange (many TLS implementations)"],
        "mitigation": "Use OAEP padding, disable RSA key exchange",
        "severity": "HIGH",
        "technique": "Bleichenbacher 1998 — RSA padding oracle via timing/error differences",
        "practical": True,
    },
    "lucky13": {
        "cve": "CVE-2013-0169",
        "affected": ["TLS CBC with MAC-then-encrypt"],
        "mitigation": "AEAD ciphers (GCM, ChaCha20-Poly1305)",
        "severity": "MEDIUM",
        "technique": "Timing side-channel on MAC verification in TLS CBC",
        "practical": True,
    },
    "logjam": {
        "cve": "CVE-2015-4000",
        "affected": ["DHE_EXPORT cipher suites", "DH < 1024-bit"],
        "mitigation": "Minimum DH 2048-bit, remove EXPORT ciphers",
        "severity": "HIGH",
        "technique": "Downgrade to DHE_EXPORT + precomputed discrete log",
        "practical": True,
    },
    "freak": {
        "cve": "CVE-2015-0204",
        "affected": ["RSA_EXPORT cipher suites"],
        "mitigation": "Remove EXPORT cipher suites",
        "severity": "HIGH",
        "technique": "Downgrade to 512-bit RSA export key",
        "practical": True,
    },
    "sloth": {
        "cve": "CVE-2015-7575",
        "affected": ["MD5 in TLS 1.2 signatures", "TLS_RSA_WITH_RC4_128_MD5"],
        "mitigation": "Disable MD5 in TLS signature algorithms",
        "severity": "MEDIUM",
        "technique": "Transcript collision via MD5 prefix collision",
        "practical": False,
    },
}

_HASH_ATTACKS = {
    "md5_collision": {
        "name": "MD5 Chosen-Prefix Collision",
        "year": 2004,
        "researchers": "Wang, Yu",
        "complexity": "2^24 (seconds on modern CPU)",
        "real_attacks": ["Flame malware (forged Windows update cert)", "X.509 cert collision (2008)"],
        "tool": "hashclash, md5collgen",
        "status": "COMPLETELY_BROKEN",
    },
    "sha1_collision": {
        "name": "SHA1 SHAttered Collision",
        "year": 2017,
        "researchers": "CWI/Google",
        "complexity": "2^63.1 SHA1 compressions",
        "cost_usd": 110000,
        "real_attacks": ["SHAttered (two PDF files same SHA1)", "SHA-mbles chosen-prefix 2020"],
        "tool": "sha1collider",
        "status": "BROKEN",
    },
    "length_extension": {
        "name": "Hash Length Extension (MD5/SHA1/SHA256)",
        "technique": "Appendre des données sans connaître le secret initial",
        "affected": ["HMAC-like constructions with H(secret||message)", "API signatures naïves"],
        "tool": "hashpump, hash_extender",
        "mitigation": "HMAC (nested construction), SHA3 (sponge construction immune)",
        "status": "PRACTICAL",
    },
    "rainbow_table": {
        "name": "Rainbow Table Attack",
        "targets": ["Unsalted MD5/SHA1/NTLM password hashes"],
        "precomputed_size": "Up to TB-scale for MD5/SHA1",
        "success_rate": "99% for passwords < 8 chars from common charset",
        "tool": "hashcat (mode 0), rainbow crack",
        "mitigation": "Bcrypt/scrypt/argon2 with salt",
        "status": "PRACTICAL",
    },
}

_PADDING_ORACLE_VARIANTS = {
    "cbc_padding_oracle": {
        "name": "CBC Padding Oracle (Vaudenay 2002)",
        "affected": ["Any system using CBC+PKCS#7 with padding error disclosure"],
        "queries_needed": "~8×block_size per decrypted block (128 for AES-128-CBC)",
        "tool": "PadBuster, padbuster.py",
        "real_attacks": ["ASP.NET ViewState", "Symantec SSL VPN", "Apache XML-RPC"],
        "mitigation": "Authenticate-then-encrypt (AES-GCM), constant-time padding check",
    },
    "bleichenbacher": {
        "name": "Bleichenbacher RSA PKCS#1v1.5 Oracle (1998)",
        "affected": ["TLS RSA key exchange", "Any RSA-PKCS1v1.5 decryption with error"],
        "queries_needed": "~2^17 to ~2^23 queries",
        "tool": "ROBOT exploit, TLS-Attacker",
        "real_attacks": ["DROWN", "ROBOT (2017) — F5, Citrix, OpenSSL"],
        "mitigation": "RSA-OAEP, disable RSA key exchange in TLS, use (EC)DHE",
    },
    "manger": {
        "name": "Manger's Attack on OAEP (2001)",
        "affected": ["RSA-OAEP with certain error oracle"],
        "queries_needed": "~2^17",
        "mitigation": "Constant-time decryption, no differential error handling",
    },
}

_AES_ATTACKS = {
    "aes_gcm_nonce_reuse": {
        "name": "GCM Nonce Reuse (Forbidden Attack)",
        "severity": "CRITICAL",
        "condition": "Same (key, nonce) used twice",
        "consequence": "Full authentication key H recovered, both plaintexts XOR-recoverable",
        "tool": "forbidden_attack.py",
        "real_attacks": ["Juniper ScreenOS", "Some TLS 1.3 implementations"],
        "mitigation": "Nonce derived from counter + HKDF, never reuse nonce",
    },
    "cbc_bit_flip": {
        "name": "CBC Bit-Flip Attack",
        "severity": "HIGH",
        "condition": "Predictable plaintext structure, no MAC",
        "consequence": "Controlled modification of next ciphertext block",
        "technique": "Modify ciphertext byte C[i] → C[i] XOR old_plain XOR new_plain",
        "mitigation": "Authenticate ciphertext (AES-GCM or HMAC-then-encrypt)",
    },
    "ecb_mode": {
        "name": "ECB Mode Deterministic Encryption",
        "severity": "HIGH",
        "condition": "ECB mode used (each block encrypted independently)",
        "consequence": "Identical plaintext blocks produce identical ciphertext — patterns visible",
        "example": "ECB Penguin — Linux logo recognizable after encryption",
        "mitigation": "Never use ECB mode outside key wrapping (AES-KW)",
    },
    "related_key": {
        "name": "Related-Key Attacks on AES",
        "severity": "MEDIUM",
        "condition": "Attacker can query with related keys",
        "affected": ["AES-192 (12 related-key distinguishers)", "AES-256 (theoretical)"],
        "mitigation": "Key derivation — never use related keys directly",
    },
}


class CryptoAttackService:

    def list_tls_attacks(self) -> Dict:
        return {k: {"severity": v["severity"], "cve": v.get("cve","N/A"), "practical": v.get("practical",False)}
                for k, v in _TLS_ATTACKS.items()}

    def get_tls_attack_detail(self, attack_name: str) -> Dict:
        return _TLS_ATTACKS.get(attack_name, {"error": f"Attaque '{attack_name}' inconnue"})

    def list_hash_attacks(self) -> Dict:
        return {k: {"name": v["name"], "status": v.get("status","UNKNOWN")} for k, v in _HASH_ATTACKS.items()}

    def list_padding_oracle_variants(self) -> Dict:
        return _PADDING_ORACLE_VARIANTS

    def list_aes_attacks(self) -> Dict:
        return {k: {"name": v["name"], "severity": v["severity"]} for k, v in _AES_ATTACKS.items()}

    def simulate_padding_oracle(
        self,
        variant: str,
        target_ciphertext_hex: Optional[str] = None,
        block_size: int = 16,
    ) -> Dict:
        session_id = str(uuid.uuid4())
        v = _PADDING_ORACLE_VARIANTS.get(variant, _PADDING_ORACLE_VARIANTS["cbc_padding_oracle"])

        queries_per_block = block_size * 256
        simulated_plaintext = os.urandom(block_size).hex()

        steps = [
            {"step": 1, "desc": "Identifier le bloc ciphertext cible (Cn-1, Cn)"},
            {"step": 2, "desc": f"Bruteforcer le dernier byte: 256 requêtes → trouver I tel que P(decrypt(C')[n]==0x01)"},
            {"step": 3, "desc": "Calculer le byte plaintext: P[n] = I XOR 0x01 XOR Cn-1[n]"},
            {"step": 4, "desc": "Répéter pour tous les bytes du bloc (padding 0x02, 0x03, ...)"},
            {"step": 5, "desc": f"Total: ~{queries_per_block} requêtes pour 1 bloc de {block_size} bytes"},
        ]

        result = {
            "session_id":       session_id,
            "variant":          variant,
            "attack_name":      v["name"],
            "block_size":       block_size,
            "queries_per_block": queries_per_block,
            "steps":            steps,
            "simulated_decrypted_block": simulated_plaintext,
            "target_ciphertext": target_ciphertext_hex or os.urandom(32).hex(),
            "attack_successful": True,
            "queries_sent":     random.randint(1500, queries_per_block),
            "mitigation":       v["mitigation"],
            "simulated":        True,
        }
        _SESSIONS[session_id] = result
        return result

    def simulate_md5_collision(self) -> Dict:
        session_id = str(uuid.uuid4())
        m1 = os.urandom(128)
        m2 = bytearray(m1)
        m2[64] ^= 0x80
        m2 = bytes(m2)
        h1 = hashlib.md5(m1).hexdigest()
        h2 = hashlib.md5(m1).hexdigest()

        return {
            "session_id":      session_id,
            "attack":          "MD5 Chosen-Prefix Collision (simulation)",
            "message1_hex":    m1.hex()[:64] + "...",
            "message2_hex":    m2.hex()[:64] + "...",
            "hash1":           h1,
            "hash2":           h2,
            "collision":       h1 == h2,
            "real_time_ns":    random.randint(100000, 500000),
            "note":            "Simulation simplifiée — vraie collision nécessite hashclash (minutes sur CPU moderne)",
            "real_tool":       "https://github.com/cr-marcstevens/hashclash",
            "simulated":       True,
        }

    def simulate_aes_gcm_nonce_reuse(
        self,
        key_hex: Optional[str] = None,
        nonce_hex: Optional[str] = None,
    ) -> Dict:
        session_id = str(uuid.uuid4())
        key   = bytes.fromhex(key_hex)   if key_hex   else os.urandom(16)
        nonce = bytes.fromhex(nonce_hex) if nonce_hex else os.urandom(12)

        p1 = b"CONFIDENTIAL: SECRET_PLAN_A"
        p2 = b"CONFIDENTIAL: SECRET_PLAN_B"
        p1_xor_p2 = bytes(a ^ b for a, b in zip(p1, p2[:len(p1)]))

        h_key_sim = os.urandom(16).hex()

        return {
            "session_id":       session_id,
            "attack":           "GCM Nonce Reuse (Forbidden Attack)",
            "nonce_reused":     nonce.hex(),
            "plaintext1_len":   len(p1),
            "plaintext2_len":   len(p2),
            "xor_plaintexts":   p1_xor_p2.hex(),
            "auth_key_h_recovered": h_key_sim,
            "consequence": [
                "Clé d'authentification H = GHASH key = AES_K(0) récupérée",
                "Les deux plaintexts sont XOR-recoverable si l'un est connu",
                "Tous les futurs ciphertexts sous cette clé peuvent être forgés",
            ],
            "severity":         "CRITICAL",
            "mitigation":       "Jamais réutiliser un nonce — utiliser un compteur 96-bit ou nonce aléatoire 256-bit (XChaCha20)",
            "simulated":        True,
        }

    def analyze_tls_config(self, cipher_suites: List[str], tls_versions: List[str]) -> Dict:
        findings = []
        score    = 100

        if "SSLv3" in tls_versions or "SSLv2" in tls_versions:
            findings.append({"severity": "CRITICAL", "issue": "SSLv2/SSLv3 activé", "cve": "CVE-2014-3566 (POODLE)"})
            score -= 30
        if "TLSv1.0" in tls_versions:
            findings.append({"severity": "HIGH", "issue": "TLS 1.0 activé", "cve": "CVE-2011-3389 (BEAST)"})
            score -= 15
        if "TLSv1.1" in tls_versions:
            findings.append({"severity": "MEDIUM", "issue": "TLS 1.1 activé (déprécié)"})
            score -= 10

        for cs in cipher_suites:
            if "RC4" in cs:
                findings.append({"severity": "CRITICAL", "issue": f"RC4 dans {cs} — stream cipher cassé"})
                score -= 20
            if "EXPORT" in cs or "EXP" in cs:
                findings.append({"severity": "CRITICAL", "issue": f"Cipher EXPORT dans {cs}", "cve": "CVE-2015-0204 (FREAK)"})
                score -= 20
            if "NULL" in cs:
                findings.append({"severity": "CRITICAL", "issue": f"Cipher NULL (pas de chiffrement!) dans {cs}"})
                score -= 30
            if "DES" in cs and "3DES" not in cs:
                findings.append({"severity": "CRITICAL", "issue": f"DES dans {cs} — 56-bit cassé"})
                score -= 20
            if "MD5" in cs:
                findings.append({"severity": "HIGH", "issue": f"HMAC-MD5 dans {cs}"})
                score -= 10
            if "RSA" in cs and "DHE" not in cs and "ECDHE" not in cs:
                findings.append({"severity": "HIGH", "issue": f"RSA key exchange (no PFS) dans {cs}", "cve": "CVE-2017-13099 (ROBOT)"})
                score -= 10
            if "CBC" in cs and "ECDHE" not in cs:
                findings.append({"severity": "MEDIUM", "issue": f"CBC sans ECDHE dans {cs}"})
                score -= 5

        grade = "A+" if score >= 95 else ("A" if score >= 85 else ("B" if score >= 70 else ("C" if score >= 50 else ("D" if score >= 30 else "F"))))

        return {
            "cipher_suites_analyzed": len(cipher_suites),
            "tls_versions":           tls_versions,
            "score":                  max(0, score),
            "grade":                  grade,
            "findings":               findings,
            "findings_count":         len(findings),
            "recommendations": [
                "TLS 1.3 uniquement + TLS 1.2 pour compatibilité",
                "ECDHE + AESGCM ou ChaCha20-Poly1305 uniquement",
                "Certificats RSA-4096 ou ECDSA-P384",
                "HSTS + certificate pinning",
            ],
            "simulated": True,
        }

    def get_session(self, session_id: str) -> Dict:
        return _SESSIONS.get(session_id, {"error": "session_not_found"})
