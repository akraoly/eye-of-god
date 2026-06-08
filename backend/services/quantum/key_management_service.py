"""
Key Management & Secure Comms — Bloc 8 Quantum & Cryptographie
Génération de clés sécurisées, gestion PKI, QKD (Quantum Key Distribution) simulation,
analyse de protocoles (Signal, OTR, Matrix), Perfect Forward Secrecy, HSM simulation.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import os
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

_KEYS: Dict[str, Dict] = {}
_OUTPUT = Path("./data/quantum/keys")
_OUTPUT.mkdir(parents=True, exist_ok=True)

_KEY_ALGORITHMS = {
    "aes_256": {
        "name": "AES-256",
        "type": "Symmetric",
        "key_bits": 256,
        "quantum_safe": True,
        "use_cases": ["Encryption at rest", "Symmetric encryption", "File encryption"],
        "generate_fn": lambda: os.urandom(32),
    },
    "aes_128": {
        "name": "AES-128",
        "type": "Symmetric",
        "key_bits": 128,
        "quantum_safe": False,
        "quantum_effective_bits": 64,
        "note": "Grover réduit à 64-bit — insuffisant pour gouvernement/militaire",
        "generate_fn": lambda: os.urandom(16),
    },
    "chacha20": {
        "name": "ChaCha20-Poly1305",
        "type": "Symmetric AEAD",
        "key_bits": 256,
        "quantum_safe": True,
        "use_cases": ["Mobile TLS", "Encrypted tunnels", "Disk encryption"],
        "generate_fn": lambda: os.urandom(32),
    },
    "ed25519": {
        "name": "Ed25519",
        "type": "Signature (classical)",
        "key_bits": 255,
        "quantum_safe": False,
        "note": "Shor's algorithm cassera Ed25519 — prévoir migration vers Dilithium",
        "generate_fn": lambda: os.urandom(32),
    },
    "x25519": {
        "name": "X25519 (ECDH)",
        "type": "Key Exchange (classical)",
        "key_bits": 255,
        "quantum_safe": False,
        "note": "Migrer vers Kyber-768 pour quantum safety",
        "generate_fn": lambda: os.urandom(32),
    },
    "kyber_768_sim": {
        "name": "Kyber-768 (FIPS 203)",
        "type": "KEM (Post-Quantum)",
        "key_bits": 1536,
        "quantum_safe": True,
        "public_key_bytes": 1184,
        "generate_fn": lambda: os.urandom(148),  # secret key seed sim
    },
    "dilithium_3_sim": {
        "name": "Dilithium-3 (FIPS 204)",
        "type": "Signature (Post-Quantum)",
        "key_bits": 2048,
        "quantum_safe": True,
        "public_key_bytes": 1952,
        "generate_fn": lambda: os.urandom(32),
    },
}

_QKD_PROTOCOLS = {
    "bb84": {
        "name": "BB84 (Bennett-Brassard 1984)",
        "type": "Prepare-and-Measure",
        "qubits_basis": ["rectilinear (+)", "diagonal (×)"],
        "security": "Information-theoretic security — unconditional",
        "key_rate_bps": 1000,
        "max_distance_km": 100,
        "error_threshold_pct": 11,
        "hardware": ["ID Quantique Clavis3", "Toshiba QKD system"],
        "deployed": ["Japan Quantum Network", "China Micius satellite", "OpenQKD Europe"],
    },
    "e91": {
        "name": "E91 (Ekert 1991)",
        "type": "Entanglement-based",
        "security": "Bell inequality violation — detects eavesdropping",
        "key_rate_bps": 500,
        "max_distance_km": 200,
        "hardware": ["Specialized entangled photon sources"],
    },
    "b92": {
        "name": "B92",
        "type": "Prepare-and-Measure (2 states)",
        "security": "Simplified BB84 — less efficient",
        "key_rate_bps": 800,
        "max_distance_km": 60,
    },
    "sarg04": {
        "name": "SARG04",
        "type": "Prepare-and-Measure",
        "security": "More robust against PNS (photon-number-splitting) attacks",
        "key_rate_bps": 900,
        "max_distance_km": 120,
    },
    "cv_qkd": {
        "name": "CV-QKD (Continuous Variable)",
        "type": "Continuous Variable",
        "security": "Gaussian modulation — compatible with telecom infrastructure",
        "key_rate_bps": 10000,
        "max_distance_km": 80,
        "advantage": "Compatible avec fibres télécom existantes",
        "hardware": ["ID Quantique CV-QKD", "Custom homodyne detection"],
    },
}

_SECURE_PROTOCOLS = {
    "signal_protocol": {
        "name": "Signal Protocol (Double Ratchet + X3DH)",
        "used_by": ["Signal", "WhatsApp", "Facebook Messenger (secret)", "Matrix"],
        "key_exchange": "X3DH (Extended Triple Diffie-Hellman) — pre-keys",
        "forward_secrecy": "Double Ratchet — new key every message",
        "break_in_security": "Full — compromise at time T doesn't reveal past/future",
        "quantum_weakness": "X25519/Ed25519 broken by Shor — post-quantum variant needed",
        "pqc_variant": "PQXDH (Signal, 2023) — Kyber-1024 added for key exchange",
    },
    "matrix_megolm": {
        "name": "Matrix Megolm / MLS",
        "used_by": ["Element", "Matrix.org"],
        "key_exchange": "Olm (Signal-like) + Megolm (group ratchet)",
        "forward_secrecy": "Partial — Megolm re-keyed periodically",
        "mls_upgrade": "MLS (RFC 9420) — scalable group key agreement with PCS",
    },
    "tls_13": {
        "name": "TLS 1.3",
        "key_exchange": "ECDHE (X25519, P-256, P-384)",
        "cipher_suites": ["TLS_AES_128_GCM_SHA256", "TLS_AES_256_GCM_SHA384", "TLS_CHACHA20_POLY1305_SHA256"],
        "forward_secrecy": "Mandatory — 0-RTT breaks FS (resumption)",
        "quantum_weakness": "ECDHE broken by Shor — hybrid Kyber+X25519 being standardized (IETF draft)",
        "pqc_extension": "draft-ietf-tls-hybrid-design — Kyber768+X25519 in production (Chrome/Firefox)",
    },
    "ike_v2": {
        "name": "IKEv2 (IPsec)",
        "key_exchange": "DH groups (currently migrating to PQC)",
        "pqc_support": "RFC 9242 — KEM in IKEv2",
        "quantum_weakness": "DH key exchange — use PQC KEM groups",
    },
    "ssh": {
        "name": "SSH (OpenSSH)",
        "key_exchange": ["curve25519-sha256", "diffie-hellman-group14-sha256"],
        "host_keys": ["Ed25519", "ECDSA", "RSA-4096"],
        "quantum_weakness": "Key exchange + host key authentication",
        "pqc_extension": "OpenSSH 9.0+ — sntrup761x25519-sha512 hybrid (Kyber-like)",
    },
}

_HSM_OPERATIONS = {
    "key_generation": {
        "desc": "Génération de clés dans le HSM (never extractable)",
        "algorithms": ["RSA-4096", "ECDSA-P384", "AES-256", "Ed25519"],
        "pqc_support": ["Kyber-768", "Dilithium-3"],
        "fips_level": "FIPS 140-3 Level 3/4",
    },
    "key_wrapping": {
        "desc": "Chiffrement/déchiffrement de clés pour export sécurisé",
        "standard": "AES Key Wrap (RFC 3394)",
    },
    "signing": {
        "desc": "Opération de signature cryptographique",
        "max_ops_per_sec": 10000,
    },
    "attestation": {
        "desc": "Attestation de l'intégrité du HSM",
        "mechanism": "Certificate chain vers clé racine HSM",
    },
}


class KeyManagementService:

    def list_key_algorithms(self) -> Dict:
        return {k: {"name": v["name"], "type": v["type"], "key_bits": v["key_bits"],
                    "quantum_safe": v["quantum_safe"]}
                for k, v in _KEY_ALGORITHMS.items()}

    def list_qkd_protocols(self) -> Dict:
        return {k: {"name": v["name"], "type": v["type"], "max_distance_km": v["max_distance_km"],
                    "key_rate_bps": v.get("key_rate_bps","N/A")}
                for k, v in _QKD_PROTOCOLS.items()}

    def get_qkd_detail(self, protocol: str) -> Dict:
        return _QKD_PROTOCOLS.get(protocol, {"error": "protocol_not_found"})

    def list_secure_protocols(self) -> Dict:
        return {k: {"name": v["name"], "forward_secrecy": v.get("forward_secrecy","N/A"),
                    "quantum_weakness": v.get("quantum_weakness","N/A")}
                for k, v in _SECURE_PROTOCOLS.items()}

    def list_hsm_operations(self) -> Dict:
        return _HSM_OPERATIONS

    def generate_key(
        self,
        algorithm: str,
        label: str = "",
        exportable: bool = False,
        hsm_protected: bool = True,
    ) -> Dict:
        algo_info = _KEY_ALGORITHMS.get(algorithm)
        if not algo_info:
            return {"error": f"Algorithme '{algorithm}' inconnu"}

        key_id   = str(uuid.uuid4())
        key_mat  = algo_info["generate_fn"]()
        key_hex  = key_mat.hex()
        key_hash = hashlib.sha256(key_mat).hexdigest()

        entry = {
            "key_id":        key_id,
            "algorithm":     algorithm,
            "algorithm_name": algo_info["name"],
            "type":          algo_info["type"],
            "key_bits":      algo_info["key_bits"],
            "quantum_safe":  algo_info["quantum_safe"],
            "label":         label or f"{algorithm}_{key_id[:8]}",
            "created_at":    datetime.utcnow().isoformat(),
            "hsm_protected": hsm_protected,
            "exportable":    exportable,
            "key_material":  key_hex if exportable else "[PROTECTED — non extractible]",
            "key_fingerprint": key_hash[:16],
            "validity_days": 365,
            "expires_at":    (datetime.utcnow() + timedelta(days=365)).date().isoformat(),
            "simulated":     True,
        }
        _KEYS[key_id] = entry
        return entry

    def simulate_qkd_session(
        self,
        protocol: str = "bb84",
        distance_km: float = 50.0,
        target_key_bits: int = 256,
    ) -> Dict:
        proto = _QKD_PROTOCOLS.get(protocol, _QKD_PROTOCOLS["bb84"])
        session_id = str(uuid.uuid4())

        if distance_km > proto["max_distance_km"]:
            return {"error": f"Distance {distance_km}km dépasse max ({proto['max_distance_km']}km) pour {protocol}"}

        # Taux d'erreur augmente avec la distance
        qber = round(0.02 + (distance_km / proto["max_distance_km"]) * 0.07, 3)
        eavesdrop_detected = qber > proto.get("error_threshold_pct", 11) / 100

        # Efficacité selon taux d'erreur (sifting + error correction)
        sifted_fraction = 0.5
        corrected_fraction = max(0, 1 - 1.2 * qber)
        privacy_amplif = 0.7
        key_rate = proto.get("key_rate_bps", 1000) * corrected_fraction

        steps = [
            {"step": 1, "name": "Quantum channel setup",       "status": "OK"},
            {"step": 2, "name": f"Sending {target_key_bits*10} qubits", "status": "OK"},
            {"step": 3, "name": "Basis reconciliation (public channel)", "status": "OK"},
            {"step": 4, "name": f"Sifting ({int(sifted_fraction*100)}% kept)", "status": "OK"},
            {"step": 5, "name": f"QBER estimation: {qber:.1%}", "status": "WARNING" if qber > 0.05 else "OK"},
            {"step": 6, "name": "Error correction (Cascade/LDPC)", "status": "OK"},
            {"step": 7, "name": "Privacy amplification (hashing)", "status": "OK"},
            {"step": 8, "name": "Secret key available",        "status": "OK" if not eavesdrop_detected else "ABORT"},
        ]

        if eavesdrop_detected:
            return {
                "session_id":          session_id,
                "protocol":            proto["name"],
                "distance_km":         distance_km,
                "qber":                qber,
                "eavesdrop_detected":  True,
                "steps":               steps,
                "result":              "ABORTED — eavesdrop detected (QBER too high)",
                "security_property":   "Information-theoretic security guaranteed — session aborted safely",
                "simulated":           True,
            }

        final_key_bits = int(target_key_bits * corrected_fraction * privacy_amplif)
        final_key = os.urandom(final_key_bits // 8).hex()

        return {
            "session_id":         session_id,
            "protocol":           proto["name"],
            "distance_km":        distance_km,
            "qber":               qber,
            "eavesdrop_detected": False,
            "steps":              steps,
            "qubits_sent":        target_key_bits * 10,
            "sifted_bits":        int(target_key_bits * sifted_fraction * 10),
            "final_key_bits":     final_key_bits,
            "final_key_hex":      final_key,
            "key_rate_bps":       round(key_rate, 1),
            "security":           "Information-theoretic — unconditionally secure",
            "simulated":          True,
        }

    def list_keys(self) -> Dict:
        return {"keys": [
            {"key_id": k, "label": v["label"], "algorithm": v["algorithm"],
             "quantum_safe": v["quantum_safe"], "expires_at": v["expires_at"]}
            for k, v in _KEYS.items()
        ]}

    def get_key(self, key_id: str) -> Dict:
        return _KEYS.get(key_id, {"error": "key_not_found"})

    def derive_key(
        self,
        master_key_hex: str,
        context: str,
        output_bits: int = 256,
    ) -> Dict:
        try:
            master = bytes.fromhex(master_key_hex)
        except ValueError:
            master = master_key_hex.encode()

        derived = hmac.new(master, context.encode(), hashlib.sha256).digest()
        if output_bits > 256:
            derived += hmac.new(master, context.encode() + b"\x01", hashlib.sha256).digest()
        derived = derived[:output_bits // 8]

        return {
            "algorithm":    "HKDF-SHA256",
            "context":      context,
            "output_bits":  output_bits,
            "derived_key":  derived.hex(),
            "fingerprint":  hashlib.sha256(derived).hexdigest()[:16],
            "simulated":    True,
        }

    def analyze_pfs(self, protocol: str) -> Dict:
        info = _SECURE_PROTOCOLS.get(protocol, {})
        pfs  = info.get("forward_secrecy", "Unknown")
        has_pfs = pfs not in ["None", "Unknown"] and "no" not in pfs.lower()
        return {
            "protocol":       protocol,
            "protocol_name":  info.get("name", protocol),
            "has_pfs":        has_pfs,
            "pfs_description": pfs,
            "quantum_weakness": info.get("quantum_weakness", "N/A"),
            "pqc_variant":    info.get("pqc_variant", info.get("pqc_extension", "Not yet available")),
            "recommendation": "Migrer vers variante PQC hybride" if not has_pfs or "x25519" in pfs.lower() else "PFS présent — migrer vers hybride Kyber",
            "simulated":      True,
        }
