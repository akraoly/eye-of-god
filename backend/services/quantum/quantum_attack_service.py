"""
Quantum Cryptanalysis — Bloc 8 Quantum & Cryptographie
Algorithme de Shor (factorisation RSA/ECC), algorithme de Grover (bruteforce symétrique),
recuit quantique (annealers), estimation Q-Day.
Simulation mathématique — aucune infrastructure quantique réelle requise.
"""
from __future__ import annotations

import logging
import math
import random
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

_JOBS: Dict[str, Dict] = {}
_OUTPUT = Path("./data/quantum/attacks")
_OUTPUT.mkdir(parents=True, exist_ok=True)

# ── Paramètres Shor ────────────────────────────────────────────────────────────
_RSA_KEY_SIZES = {
    512:   {"qubits_needed": 1024,  "classical_years": 0.001,   "quantum_seconds": 0.5,    "status": "BROKEN"},
    1024:  {"qubits_needed": 2048,  "classical_years": 300,     "quantum_seconds": 5,      "status": "BROKEN"},
    2048:  {"qubits_needed": 4096,  "classical_years": 1e13,    "quantum_seconds": 20,     "status": "VULNERABLE_FUTURE"},
    3072:  {"qubits_needed": 6144,  "classical_years": 1e17,    "quantum_seconds": 45,     "status": "VULNERABLE_FUTURE"},
    4096:  {"qubits_needed": 8192,  "classical_years": 1e23,    "quantum_seconds": 90,     "status": "VULNERABLE_FUTURE"},
    7680:  {"qubits_needed": 15360, "classical_years": 1e36,    "quantum_seconds": 300,    "status": "SAFE_NEAR_TERM"},
    15360: {"qubits_needed": 30720, "classical_years": float('inf'), "quantum_seconds": 900, "status": "SAFE_NEAR_TERM"},
}

_ECC_KEY_SIZES = {
    160:  {"qubits_needed": 1000,  "classical_years": 10,      "quantum_seconds": 2,      "status": "BROKEN"},
    224:  {"qubits_needed": 1500,  "classical_years": 1e4,     "quantum_seconds": 4,      "status": "BROKEN"},
    256:  {"qubits_needed": 2330,  "classical_years": 1e9,     "quantum_seconds": 8,      "status": "VULNERABLE_FUTURE"},
    384:  {"qubits_needed": 3484,  "classical_years": 1e17,    "quantum_seconds": 18,     "status": "VULNERABLE_FUTURE"},
    521:  {"qubits_needed": 4719,  "classical_years": 1e32,    "quantum_seconds": 35,     "status": "VULNERABLE_FUTURE"},
}

# ── Grover — affaiblissement symétrique ────────────────────────────────────────
_SYMMETRIC_KEYS = {
    "DES_56":    {"bits": 56,  "classical_ops": 2**56,  "grover_ops": 2**28,  "status": "BROKEN_NOW"},
    "3DES_112":  {"bits": 112, "classical_ops": 2**112, "grover_ops": 2**56,  "status": "BROKEN_QUANTUM"},
    "AES_128":   {"bits": 128, "classical_ops": 2**128, "grover_ops": 2**64,  "status": "WEAKENED_SECURE"},
    "AES_192":   {"bits": 192, "classical_ops": 2**192, "grover_ops": 2**96,  "status": "SECURE_QUANTUM"},
    "AES_256":   {"bits": 256, "classical_ops": 2**256, "grover_ops": 2**128, "status": "QUANTUM_SAFE"},
    "ChaCha20":  {"bits": 256, "classical_ops": 2**256, "grover_ops": 2**128, "status": "QUANTUM_SAFE"},
}

_HASH_ALGORITHMS = {
    "MD5":      {"bits": 128, "collision_ops_classical": 2**64,  "collision_ops_grover": 2**43,  "status": "BROKEN_CLASSICAL"},
    "SHA1":     {"bits": 160, "collision_ops_classical": 2**63,  "collision_ops_grover": 2**53,  "status": "BROKEN_CLASSICAL"},
    "SHA256":   {"bits": 256, "collision_ops_classical": 2**128, "collision_ops_grover": 2**85,  "status": "SECURE_QUANTUM"},
    "SHA3_256": {"bits": 256, "collision_ops_classical": 2**128, "collision_ops_grover": 2**85,  "status": "QUANTUM_SAFE"},
    "SHA512":   {"bits": 512, "collision_ops_classical": 2**256, "collision_ops_grover": 2**170, "status": "QUANTUM_SAFE"},
    "BLAKE3":   {"bits": 256, "collision_ops_classical": 2**128, "collision_ops_grover": 2**85,  "status": "QUANTUM_SAFE"},
}

# ── Timeline Q-Day ─────────────────────────────────────────────────────────────
_QDAY_ESTIMATES = {
    "optimistic":  {"year": 2029, "qubits_fault_tolerant": 4000,   "source": "Google Quantum AI roadmap"},
    "consensus":   {"year": 2033, "qubits_fault_tolerant": 10000,  "source": "NIST/NSA assessment"},
    "pessimistic": {"year": 2040, "qubits_fault_tolerant": 100000, "source": "IBM quantum roadmap"},
    "never_classical": {"year": None, "note": "Decoherence/error correction unsolved — classical crypto survives"},
}

# ── Algorithmes quantiques ─────────────────────────────────────────────────────
_QUANTUM_ALGORITHMS = {
    "shor": {
        "name": "Algorithme de Shor",
        "year": 1994,
        "complexity_classical": "O(exp(n^(1/3)))",
        "complexity_quantum": "O(n^3 log n)",
        "targets": ["RSA", "DH (FFDH)", "ECDH", "ECDSA", "DSA", "ElGamal"],
        "speedup": "Exponentiel",
        "requires": "Fault-tolerant universal quantum computer",
        "real_record": "15 = 3×5 factored on 7 qubits (2001), 21 on 10 qubits",
    },
    "grover": {
        "name": "Algorithme de Grover",
        "year": 1996,
        "complexity_classical": "O(N)",
        "complexity_quantum": "O(√N)",
        "targets": ["Symmetric encryption (AES/3DES)", "Hash preimage", "Hash collision (BHT variant)"],
        "speedup": "Quadratique",
        "requires": "NISQ-era + fault tolerant",
        "impact": "Effective key length halved — AES-128 → 64-bit security",
    },
    "simon": {
        "name": "Algorithme de Simon",
        "year": 1994,
        "targets": ["CBC-MAC", "GHASH (GCM)", "Some stream ciphers"],
        "speedup": "Exponentiel sur problèmes spécifiques",
        "note": "Attaque théorique sur constructions Even-Mansour",
    },
    "bernstein_vazirani": {
        "name": "Bernstein-Vazirani",
        "year": 1993,
        "targets": ["Clés secrètes dans constructions linéaires"],
        "speedup": "Polynomial → O(1)",
        "note": "Cassé des primitives custom basées sur masques linéaires",
    },
    "quantum_annealing": {
        "name": "Quantum Annealing (D-Wave style)",
        "targets": ["Optimisation NP-hard", "Factorisation petits nombres", "Problèmes de graphe"],
        "hardware": "D-Wave Advantage (5000+ qubits)",
        "limitation": "Pas de speedup prouvé sur cryptographie classique",
        "use_case": "Side-channel key recovery par optimisation",
    },
}


class QuantumAttackService:

    def list_algorithms(self) -> Dict:
        return {k: {"name": v["name"], "targets": v["targets"], "speedup": v.get("speedup", "N/A")}
                for k, v in _QUANTUM_ALGORITHMS.items()}

    def list_rsa_analysis(self) -> Dict:
        return {str(k): v for k, v in _RSA_KEY_SIZES.items()}

    def list_ecc_analysis(self) -> Dict:
        return {str(k): v for k, v in _ECC_KEY_SIZES.items()}

    def list_symmetric_analysis(self) -> Dict:
        return _SYMMETRIC_KEYS

    def list_hash_analysis(self) -> Dict:
        return _HASH_ALGORITHMS

    def get_qday_estimates(self) -> Dict:
        return {
            "estimates":   _QDAY_ESTIMATES,
            "current_year": 2026,
            "current_best_qubits": 1121,
            "current_best_machine": "IBM Condor (2023)",
            "error_rate_target": 0.001,
            "current_error_rate": 0.005,
            "recommendation": "Migrer vers PQC maintenant — les données chiffrées aujourd'hui peuvent être déchiffrées après Q-Day (harvest now, decrypt later)",
        }

    def simulate_shor(
        self,
        algorithm: str,
        key_size: int,
        qubits_available: int = 10000,
    ) -> Dict:
        job_id = str(uuid.uuid4())

        if algorithm.upper() in ["RSA", "DH", "FFDH"]:
            entry = _RSA_KEY_SIZES.get(key_size, _RSA_KEY_SIZES[2048])
            target_type = "asymmetric_rsa"
        elif algorithm.upper() in ["ECC", "ECDH", "ECDSA"]:
            entry = _ECC_KEY_SIZES.get(key_size, _ECC_KEY_SIZES[256])
            target_type = "asymmetric_ecc"
        else:
            entry = _RSA_KEY_SIZES.get(2048)
            target_type = "asymmetric_rsa"

        qubits_needed    = entry["qubits_needed"]
        feasible_now     = qubits_available >= qubits_needed
        quantum_time_s   = entry["quantum_seconds"]
        classical_years  = entry["classical_years"]

        # Simulation des étapes de l'algorithme de Shor
        steps = [
            {"step": 1, "name": "Quantum Fourier Transform",
             "desc": f"QFT sur {qubits_needed} qubits pour trouver la période r",
             "duration_ns": random.randint(100, 1000)},
            {"step": 2, "name": "Period Finding",
             "desc": f"Trouver r tel que a^r ≡ 1 (mod N) pour N={2**key_size if key_size < 64 else 'N_large'}",
             "duration_ns": random.randint(500, 5000)},
            {"step": 3, "name": "Classical Post-Processing",
             "desc": "GCD(a^(r/2)±1, N) pour extraire les facteurs premiers",
             "duration_ns": random.randint(1, 10)},
        ]

        p = random.randint(2**(key_size//2-1), 2**(key_size//2))
        q_val = random.randint(2**(key_size//2-1), 2**(key_size//2))

        result = {
            "job_id":          job_id,
            "algorithm":       f"Shor — {algorithm.upper()} {key_size}-bit",
            "target_type":     target_type,
            "key_size":        key_size,
            "qubits_needed":   qubits_needed,
            "qubits_available": qubits_available,
            "feasible_today":  feasible_now,
            "classical_time_years": classical_years,
            "quantum_time_seconds": quantum_time_s if feasible_now else None,
            "vulnerability_status": entry["status"],
            "steps":           steps,
            "simulated_output": {
                "message":     "Simulation — facteurs extraits",
                "p_factor":    hex(p),
                "q_factor":    hex(q_val),
                "n_modulus":   hex(p * q_val),
                "private_key_recovered": feasible_now,
            } if feasible_now else {
                "message": f"Pas assez de qubits — nécessite {qubits_needed}, disponible {qubits_available}",
                "private_key_recovered": False,
            },
            "simulated": True,
        }
        _JOBS[job_id] = result
        return result

    def simulate_grover(
        self,
        algorithm: str,
        key_size: int,
        qubits_available: int = 5000,
    ) -> Dict:
        job_id  = str(uuid.uuid4())
        sym_key = _SYMMETRIC_KEYS.get(algorithm.upper(), _SYMMETRIC_KEYS["AES_128"])
        bits    = sym_key["bits"]

        # Grover réduit de moitié la sécurité effective en bits
        effective_security = bits // 2
        oracle_calls       = int(math.sqrt(2**bits))
        qubits_grover      = bits + 1

        result = {
            "job_id":                  job_id,
            "algorithm":               f"Grover — {algorithm.upper()}",
            "key_size_bits":           bits,
            "effective_quantum_security": effective_security,
            "oracle_calls_needed":     f"2^{bits//2} ≈ {oracle_calls:.2e}",
            "qubits_needed":           qubits_grover,
            "qubits_available":        qubits_available,
            "feasible":                qubits_available >= qubits_grover,
            "verdict":                 sym_key["status"],
            "recommendation":          (
                "Doubler la taille de clé symétrique pour maintenir le niveau de sécurité"
                if effective_security < 128
                else "Niveau de sécurité post-quantique suffisant"
            ),
            "classical_ops":           f"2^{bits}",
            "quantum_ops":             f"2^{bits//2}",
            "speedup_factor":          f"2^{bits//2}×",
            "simulated":               True,
        }
        _JOBS[job_id] = result
        return result

    def harvest_now_decrypt_later(self, targets: List[Dict]) -> Dict:
        analyzed = []
        for t in targets:
            algo      = t.get("algorithm", "RSA")
            key_size  = t.get("key_size", 2048)
            data_type = t.get("data_type", "generic")
            retention_years = t.get("retention_years", 10)

            if algo.upper() in ["RSA", "DH"]:
                entry = _RSA_KEY_SIZES.get(key_size, _RSA_KEY_SIZES[2048])
            else:
                entry = _ECC_KEY_SIZES.get(key_size, _ECC_KEY_SIZES[256])

            qday_consensus = 2033
            years_to_qday  = max(0, qday_consensus - 2026)
            at_risk        = retention_years > years_to_qday

            analyzed.append({
                "algorithm":        f"{algo}-{key_size}",
                "data_type":        data_type,
                "retention_years":  retention_years,
                "years_to_qday":    years_to_qday,
                "at_risk":          at_risk,
                "risk_level":       "CRITICAL" if at_risk and data_type in ["classified","health","financial"] else ("HIGH" if at_risk else "LOW"),
                "action":           "MIGRER IMMÉDIATEMENT vers PQC" if at_risk else "Planifier migration PQC d'ici 2030",
            })

        critical = [a for a in analyzed if a["risk_level"] == "CRITICAL"]
        return {
            "analysis_date": datetime.utcnow().isoformat(),
            "qday_consensus": 2033,
            "targets_analyzed": len(analyzed),
            "at_risk": len([a for a in analyzed if a["at_risk"]]),
            "critical": len(critical),
            "targets": analyzed,
            "recommendation": f"{len(critical)} cibles critiques à migrer immédiatement vers PQC",
            "simulated": True,
        }

    def get_job(self, job_id: str) -> Dict:
        return _JOBS.get(job_id, {"error": "job_not_found"})
