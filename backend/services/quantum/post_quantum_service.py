"""
Post-Quantum Cryptography (PQC) — Bloc 8 Quantum & Cryptographie
Algorithmes NIST PQC finalisés (CRYSTALS-Kyber, CRYSTALS-Dilithium, SPHINCS+, FALCON),
évaluation de migration, hybride classique+PQC, audit de surface cryptographique.
"""
from __future__ import annotations

import logging
import random
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

_OUTPUT = Path("./data/quantum/pqc")
_OUTPUT.mkdir(parents=True, exist_ok=True)

_PQC_ALGORITHMS = {
    "kyber_512": {
        "name": "CRYSTALS-Kyber 512",
        "nist_standard": "FIPS 203 (ML-KEM)",
        "type": "KEM",
        "security_level": 1,
        "quantum_security_bits": 128,
        "classical_security_bits": 128,
        "public_key_bytes": 800,
        "ciphertext_bytes": 768,
        "secret_key_bytes": 1632,
        "keygen_ops": 167000,
        "encaps_ops": 134000,
        "decaps_ops": 128000,
        "assumption": "Module-LWE (Learning With Errors)",
        "status": "NIST_STANDARD",
        "use_case": "Key encapsulation, TLS handshake replacement",
    },
    "kyber_768": {
        "name": "CRYSTALS-Kyber 768",
        "nist_standard": "FIPS 203 (ML-KEM)",
        "type": "KEM",
        "security_level": 3,
        "quantum_security_bits": 184,
        "classical_security_bits": 184,
        "public_key_bytes": 1184,
        "ciphertext_bytes": 1088,
        "secret_key_bytes": 2400,
        "keygen_ops": 112000,
        "encaps_ops": 97000,
        "decaps_ops": 93000,
        "assumption": "Module-LWE",
        "status": "NIST_STANDARD",
        "use_case": "Recommended for most applications",
    },
    "kyber_1024": {
        "name": "CRYSTALS-Kyber 1024",
        "nist_standard": "FIPS 203 (ML-KEM)",
        "type": "KEM",
        "security_level": 5,
        "quantum_security_bits": 257,
        "classical_security_bits": 257,
        "public_key_bytes": 1568,
        "ciphertext_bytes": 1568,
        "secret_key_bytes": 3168,
        "keygen_ops": 70000,
        "encaps_ops": 62000,
        "decaps_ops": 60000,
        "assumption": "Module-LWE",
        "status": "NIST_STANDARD",
        "use_case": "High-security applications, government/military",
    },
    "dilithium_2": {
        "name": "CRYSTALS-Dilithium 2",
        "nist_standard": "FIPS 204 (ML-DSA)",
        "type": "Signature",
        "security_level": 2,
        "quantum_security_bits": 128,
        "classical_security_bits": 128,
        "public_key_bytes": 1312,
        "signature_bytes": 2420,
        "secret_key_bytes": 2528,
        "keygen_ops": 120000,
        "sign_ops": 44000,
        "verify_ops": 100000,
        "assumption": "Module-LWE + Module-SIS",
        "status": "NIST_STANDARD",
    },
    "dilithium_3": {
        "name": "CRYSTALS-Dilithium 3",
        "nist_standard": "FIPS 204 (ML-DSA)",
        "type": "Signature",
        "security_level": 3,
        "quantum_security_bits": 184,
        "classical_security_bits": 184,
        "public_key_bytes": 1952,
        "signature_bytes": 3293,
        "secret_key_bytes": 4000,
        "assumption": "Module-LWE + Module-SIS",
        "status": "NIST_STANDARD",
    },
    "dilithium_5": {
        "name": "CRYSTALS-Dilithium 5",
        "nist_standard": "FIPS 204 (ML-DSA)",
        "type": "Signature",
        "security_level": 5,
        "quantum_security_bits": 257,
        "classical_security_bits": 257,
        "public_key_bytes": 2592,
        "signature_bytes": 4595,
        "secret_key_bytes": 4864,
        "assumption": "Module-LWE + Module-SIS",
        "status": "NIST_STANDARD",
    },
    "sphincs_sha2_128s": {
        "name": "SPHINCS+ SHA2-128s",
        "nist_standard": "FIPS 205 (SLH-DSA)",
        "type": "Signature",
        "security_level": 1,
        "quantum_security_bits": 128,
        "classical_security_bits": 128,
        "public_key_bytes": 32,
        "signature_bytes": 7856,
        "secret_key_bytes": 64,
        "assumption": "Hash function security (stateless)",
        "status": "NIST_STANDARD",
        "advantage": "Minimal assumptions — based only on hash security",
    },
    "falcon_512": {
        "name": "FALCON-512",
        "nist_standard": "FIPS 206 (FN-DSA)",
        "type": "Signature",
        "security_level": 1,
        "quantum_security_bits": 128,
        "classical_security_bits": 128,
        "public_key_bytes": 897,
        "signature_bytes": 666,
        "secret_key_bytes": 1281,
        "assumption": "NTRU lattice",
        "status": "NIST_STANDARD",
        "advantage": "Smallest signatures among NIST PQC finalists",
    },
    "falcon_1024": {
        "name": "FALCON-1024",
        "nist_standard": "FIPS 206 (FN-DSA)",
        "type": "Signature",
        "security_level": 5,
        "quantum_security_bits": 257,
        "public_key_bytes": 1793,
        "signature_bytes": 1280,
        "secret_key_bytes": 2305,
        "assumption": "NTRU lattice",
        "status": "NIST_STANDARD",
    },
    "classic_mceliece": {
        "name": "Classic McEliece 348864",
        "nist_standard": "Alternate (very large keys)",
        "type": "KEM",
        "security_level": 1,
        "quantum_security_bits": 128,
        "public_key_bytes": 261120,
        "ciphertext_bytes": 96,
        "advantage": "Most conservative — 50+ year security analysis",
        "disadvantage": "Impractically large public keys",
        "status": "NIST_ALTERNATE",
    },
    "bike": {
        "name": "BIKE Level 1",
        "nist_standard": "Alternate",
        "type": "KEM",
        "security_level": 1,
        "quantum_security_bits": 128,
        "public_key_bytes": 1541,
        "ciphertext_bytes": 1573,
        "assumption": "QC-MDPC codes",
        "status": "NIST_ALTERNATE",
    },
    "hqc": {
        "name": "HQC Level 1",
        "nist_standard": "Alternate",
        "type": "KEM",
        "security_level": 1,
        "quantum_security_bits": 128,
        "public_key_bytes": 2249,
        "ciphertext_bytes": 4481,
        "assumption": "QC codes (syndrome decoding)",
        "status": "NIST_ALTERNATE",
    },
}

_HYBRID_SCHEMES = {
    "kyber_x25519": {
        "name": "Kyber-768 + X25519",
        "type": "Hybrid KEM",
        "classical": "X25519 (ECDH)",
        "pqc": "Kyber-768",
        "total_overhead_bytes": 1184 + 32,
        "security": "Classical if PQC broken, Quantum-safe if classical broken",
        "used_in": ["TLS 1.3 (IETF draft)", "Signal Protocol hybrid", "Chrome/Firefox experiment"],
        "recommendation": "RECOMMENDED — provides backward compatibility",
    },
    "dilithium_ecdsa": {
        "name": "Dilithium-3 + ECDSA-P256",
        "type": "Hybrid Signature",
        "classical": "ECDSA P-256",
        "pqc": "Dilithium-3",
        "security": "Valid if BOTH fail simultaneously",
        "used_in": ["Code signing transition", "Certificate authorities"],
    },
    "kyber_rsa": {
        "name": "Kyber-768 + RSA-2048",
        "type": "Hybrid KEM",
        "classical": "RSA-2048",
        "pqc": "Kyber-768",
        "overhead": "Large but compatible with existing PKI",
        "used_in": ["Legacy infrastructure migration"],
    },
}

_MIGRATION_PRIORITIES = {
    "critical": {
        "label": "Critique — migrer immédiatement",
        "examples": ["TLS long-lived sessions", "VPN key exchange", "Code signing certificates", "Root CA"],
        "deadline": "2027",
        "algorithms_to_replace": ["RSA-2048", "ECDH-P256", "ECDSA-P256"],
        "replace_with": ["Kyber-768", "Dilithium-3", "Falcon-512"],
    },
    "high": {
        "label": "Élevée — migrer avant Q-Day",
        "examples": ["Email encryption (S/MIME, PGP)", "Disk encryption keys", "SSH host keys"],
        "deadline": "2030",
        "algorithms_to_replace": ["RSA-4096", "ECDH-P384", "DSA"],
        "replace_with": ["Kyber-1024", "Dilithium-5", "SPHINCS+"],
    },
    "medium": {
        "label": "Moyenne — planifier migration",
        "examples": ["Short-lived tokens", "HTTPS certificates (<1 year)", "Session keys"],
        "deadline": "2033",
        "algorithms_to_replace": ["DH-2048", "EC-secp256k1"],
        "replace_with": ["Kyber-768", "Dilithium-3"],
    },
    "low": {
        "label": "Faible — surveiller évolutions",
        "examples": ["AES-256", "ChaCha20-Poly1305", "SHA-512", "BLAKE3"],
        "deadline": "Pas urgent",
        "note": "Algorithmes symétriques résistants à Grover avec taille clé ≥256 bits",
    },
}


class PostQuantumService:

    def list_algorithms(self, algo_type: Optional[str] = None) -> Dict:
        if algo_type:
            return {k: v for k, v in _PQC_ALGORITHMS.items() if v["type"].lower() == algo_type.lower()}
        return {k: {"name": v["name"], "type": v["type"], "security_level": v["security_level"],
                    "status": v["status"], "quantum_security_bits": v["quantum_security_bits"]}
                for k, v in _PQC_ALGORITHMS.items()}

    def get_algorithm_detail(self, algorithm: str) -> Dict:
        return _PQC_ALGORITHMS.get(algorithm, {"error": f"Algorithme '{algorithm}' non trouvé"})

    def list_hybrid_schemes(self) -> Dict:
        return _HYBRID_SCHEMES

    def get_migration_roadmap(self) -> Dict:
        return {
            "priorities": _MIGRATION_PRIORITIES,
            "nist_standards": {
                "FIPS_203": "ML-KEM (Kyber) — KEM standard",
                "FIPS_204": "ML-DSA (Dilithium) — Signature standard",
                "FIPS_205": "SLH-DSA (SPHINCS+) — Stateless hash signature",
                "FIPS_206": "FN-DSA (Falcon) — Fast lattice signature",
            },
            "key_dates": {
                "2024": "NIST FIPS 203/204/205 finalisés",
                "2025": "NIST FIPS 206 (Falcon) finalisé",
                "2026": "Dépréciation RSA/ECC dans nouvelles applications (NSA CNSA 2.0)",
                "2030": "Fin de support RSA/ECC dans systèmes gouvernementaux US",
                "2033": "Q-Day consensus estimate",
            },
        }

    def audit_crypto_surface(self, components: List[Dict]) -> Dict:
        audit_id = str(uuid.uuid4())
        results  = []
        critical = 0
        high     = 0

        for comp in components:
            name     = comp.get("name", "Unknown")
            algo     = comp.get("algorithm", "RSA-2048")
            protocol = comp.get("protocol", "TLS")
            exposed  = comp.get("internet_exposed", False)

            # Évaluation du risque
            if any(x in algo.upper() for x in ["MD5","SHA1","DES","RC4","RSA-512","RSA-1024"]):
                risk = "CRITICAL"
                critical += 1
                action = "REMPLACER IMMÉDIATEMENT"
            elif any(x in algo.upper() for x in ["RSA-2048","ECDH-P256","DH-2048"]):
                risk = "HIGH"
                high += 1
                action = "Migrer vers PQC avant 2030"
            elif any(x in algo.upper() for x in ["RSA-4096","ECDH-P384","AES-128"]):
                risk = "MEDIUM"
                action = "Planifier migration PQC (horizon 2033)"
            else:
                risk = "LOW"
                action = "Surveiller évolutions NIST"

            if exposed and risk in ["HIGH","CRITICAL"]:
                risk = "CRITICAL"
                critical += 1
                action = f"CRITIQUE — exposé Internet — {action}"

            results.append({
                "component": name,
                "algorithm": algo,
                "protocol":  protocol,
                "exposed":   exposed,
                "risk":      risk,
                "action":    action,
                "pqc_replacement": self._suggest_pqc(algo),
            })

        return {
            "audit_id":       audit_id,
            "audited_at":     datetime.utcnow().isoformat(),
            "components":     len(components),
            "critical":       critical,
            "high":           high,
            "results":        results,
            "overall_posture": "CRITICAL" if critical > 0 else ("HIGH" if high > 0 else "MEDIUM"),
            "simulated":      True,
        }

    def generate_migration_plan(
        self,
        current_algo: str,
        target_algo: str,
        system_name: str,
        timeline_months: int = 18,
    ) -> Dict:
        pqc_info = _PQC_ALGORITHMS.get(target_algo)
        if not pqc_info:
            return {"error": f"Algorithme PQC '{target_algo}' inconnu"}

        phases = [
            {"month": 1,                "phase": "Évaluation", "tasks": [
                "Inventaire complet des usages cryptographiques",
                "Test de performance PQC en environnement de dev",
                f"Validation compatibilité {target_algo}",
            ]},
            {"month": 3,                "phase": "Pilote Hybride", "tasks": [
                f"Déploiement mode hybride {current_algo} + {target_algo}",
                "Tests d'interopérabilité",
                "Monitoring performance",
            ]},
            {"month": 6,                "phase": "Migration Progressive", "tasks": [
                "Rollout 10% du trafic vers PQC",
                "Rotation des clés critiques",
                "Formation équipes",
            ]},
            {"month": timeline_months,  "phase": "Migration Complète", "tasks": [
                f"100% migration vers {target_algo}",
                f"Décommissionnement {current_algo}",
                "Audit final",
            ]},
        ]

        return {
            "system":           system_name,
            "from_algorithm":   current_algo,
            "to_algorithm":     target_algo,
            "pqc_algorithm":    pqc_info["name"],
            "security_level":   pqc_info["security_level"],
            "timeline_months":  timeline_months,
            "phases":           phases,
            "key_size_change": {
                "public_key_bytes": pqc_info.get("public_key_bytes", "N/A"),
                "note": "Les clés PQC sont plus grandes — prévoir adaptation stockage/protocole",
            },
            "hybrid_transition_recommended": True,
            "simulated": True,
        }

    def _suggest_pqc(self, algo: str) -> str:
        a = algo.upper()
        if "RSA" in a or "DH" in a:    return "kyber_768 (KEM) + dilithium_3 (signature)"
        if "ECDH" in a or "ECDSA" in a: return "kyber_768 (KEM) + falcon_512 (signature)"
        if "AES-128" in a:              return "aes_256 (doubler la taille de clé)"
        if "MD5" in a or "SHA1" in a:   return "sha3_256 ou blake3"
        return "Consulter NIST FIPS 203/204/205"
