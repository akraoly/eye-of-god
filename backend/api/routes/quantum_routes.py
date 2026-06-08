"""Quantum & Cryptographie Routes — Bloc 8 Supra-Étatiques."""
from __future__ import annotations
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

from services.quantum.quantum_attack_service  import QuantumAttackService
from services.quantum.post_quantum_service    import PostQuantumService
from services.quantum.crypto_attack_service   import CryptoAttackService
from services.quantum.crypto_impl_service     import CryptoImplService
from services.quantum.key_management_service  import KeyManagementService

router = APIRouter()
_qa  = QuantumAttackService()
_pq  = PostQuantumService()
_ca  = CryptoAttackService()
_ci  = CryptoImplService()
_km  = KeyManagementService()


def _auth(confirmed: bool, action: str):
    if not confirmed:
        raise HTTPException(403, f"authorization_confirmed=true requis pour: {action}")


class AuthReq(BaseModel):
    authorization_confirmed: bool = False


# ── QUANTUM ATTACKS ────────────────────────────────────────────────────────────

class ShorReq(AuthReq):
    algorithm:        str = "RSA"
    key_size:         int = 2048
    qubits_available: int = 10000

class GroverReq(AuthReq):
    algorithm:        str = "AES_128"
    key_size:         int = 128
    qubits_available: int = 5000

class HarvestReq(AuthReq):
    targets: List[Dict] = [{"algorithm": "RSA", "key_size": 2048, "data_type": "financial", "retention_years": 10}]


@router.get("/quantum/algorithms")
async def qa_algorithms():
    return _qa.list_algorithms()

@router.get("/quantum/rsa-analysis")
async def qa_rsa():
    return _qa.list_rsa_analysis()

@router.get("/quantum/ecc-analysis")
async def qa_ecc():
    return _qa.list_ecc_analysis()

@router.get("/quantum/symmetric-analysis")
async def qa_sym():
    return _qa.list_symmetric_analysis()

@router.get("/quantum/hash-analysis")
async def qa_hash():
    return _qa.list_hash_analysis()

@router.get("/quantum/qday-estimates")
async def qa_qday():
    return _qa.get_qday_estimates()

@router.post("/quantum/simulate-shor")
async def qa_shor(req: ShorReq):
    _auth(req.authorization_confirmed, "quantum_shor")
    return _qa.simulate_shor(req.algorithm, req.key_size, req.qubits_available)

@router.post("/quantum/simulate-grover")
async def qa_grover(req: GroverReq):
    _auth(req.authorization_confirmed, "quantum_grover")
    return _qa.simulate_grover(req.algorithm, req.key_size, req.qubits_available)

@router.post("/quantum/harvest-now-decrypt-later")
async def qa_harvest(req: HarvestReq):
    _auth(req.authorization_confirmed, "harvest_now_decrypt_later")
    return _qa.harvest_now_decrypt_later(req.targets)

@router.get("/quantum/job/{job_id}")
async def qa_job(job_id: str):
    return _qa.get_job(job_id)


# ── POST-QUANTUM CRYPTOGRAPHY ─────────────────────────────────────────────────

class PQCAuditReq(AuthReq):
    components: List[Dict] = [
        {"name": "TLS API Gateway", "algorithm": "ECDH-P256", "protocol": "TLS 1.2", "internet_exposed": True},
        {"name": "Email S/MIME", "algorithm": "RSA-2048", "protocol": "S/MIME", "internet_exposed": False},
    ]

class PQCMigrateReq(AuthReq):
    current_algo:    str = "RSA-2048"
    target_algo:     str = "kyber_768"
    system_name:     str = "TLS Key Exchange"
    timeline_months: int = 18


@router.get("/pqc/algorithms")
async def pqc_algos(type: Optional[str] = None):
    return _pq.list_algorithms(type)

@router.get("/pqc/algorithm/{algorithm}")
async def pqc_algo_detail(algorithm: str):
    return _pq.get_algorithm_detail(algorithm)

@router.get("/pqc/hybrid-schemes")
async def pqc_hybrid():
    return _pq.list_hybrid_schemes()

@router.get("/pqc/migration-roadmap")
async def pqc_roadmap():
    return _pq.get_migration_roadmap()

@router.post("/pqc/audit-surface")
async def pqc_audit(req: PQCAuditReq):
    _auth(req.authorization_confirmed, "pqc_audit")
    return _pq.audit_crypto_surface(req.components)

@router.post("/pqc/migration-plan")
async def pqc_migrate(req: PQCMigrateReq):
    _auth(req.authorization_confirmed, "pqc_migration_plan")
    return _pq.generate_migration_plan(req.current_algo, req.target_algo, req.system_name, req.timeline_months)


# ── CLASSICAL CRYPTO ATTACKS ──────────────────────────────────────────────────

class PaddingOracleReq(AuthReq):
    variant:               str           = "cbc_padding_oracle"
    target_ciphertext_hex: Optional[str] = None
    block_size:            int           = 16

class TLSAnalyzeReq(AuthReq):
    cipher_suites: List[str] = ["TLS_RSA_WITH_AES_128_CBC_SHA", "TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384"]
    tls_versions:  List[str] = ["TLSv1.0", "TLSv1.2", "TLSv1.3"]

class GCMNonceReq(AuthReq):
    key_hex:   Optional[str] = None
    nonce_hex: Optional[str] = None


@router.get("/crypto-attacks/tls-attacks")
async def ca_tls_list():
    return _ca.list_tls_attacks()

@router.get("/crypto-attacks/tls-attack/{name}")
async def ca_tls_detail(name: str):
    return _ca.get_tls_attack_detail(name)

@router.get("/crypto-attacks/hash-attacks")
async def ca_hash():
    return _ca.list_hash_attacks()

@router.get("/crypto-attacks/padding-oracles")
async def ca_padding_list():
    return _ca.list_padding_oracle_variants()

@router.get("/crypto-attacks/aes-attacks")
async def ca_aes():
    return _ca.list_aes_attacks()

@router.post("/crypto-attacks/simulate-padding-oracle")
async def ca_padding(req: PaddingOracleReq):
    _auth(req.authorization_confirmed, "crypto_padding_oracle")
    return _ca.simulate_padding_oracle(req.variant, req.target_ciphertext_hex, req.block_size)

@router.post("/crypto-attacks/simulate-md5-collision")
async def ca_md5(req: AuthReq):
    _auth(req.authorization_confirmed, "crypto_md5_collision")
    return _ca.simulate_md5_collision()

@router.post("/crypto-attacks/simulate-gcm-nonce-reuse")
async def ca_gcm(req: GCMNonceReq):
    _auth(req.authorization_confirmed, "crypto_gcm_nonce_reuse")
    return _ca.simulate_aes_gcm_nonce_reuse(req.key_hex, req.nonce_hex)

@router.post("/crypto-attacks/analyze-tls-config")
async def ca_tls_analyze(req: TLSAnalyzeReq):
    _auth(req.authorization_confirmed, "crypto_tls_analyze")
    return _ca.analyze_tls_config(req.cipher_suites, req.tls_versions)

@router.get("/crypto-attacks/session/{session_id}")
async def ca_session(session_id: str):
    return _ca.get_session(session_id)


# ── CRYPTO IMPLEMENTATION ATTACKS ─────────────────────────────────────────────

class TimingOracleReq(AuthReq):
    attack_type: str = "hmac_timing"
    samples:     int = 10000

class CodeAnalyzeReq(AuthReq):
    code_snippet: str = 'key = b"hardcoded_secret"\nimport hashlib\nh = hashlib.md5(password.encode()).hexdigest()'
    language:     str = "python"


@router.get("/crypto-impl/timing-attacks")
async def ci_timing_list():
    return _ci.list_timing_attacks()

@router.get("/crypto-impl/timing-attack/{attack}")
async def ci_timing_detail(attack: str):
    return _ci.get_timing_attack_detail(attack)

@router.get("/crypto-impl/fault-attacks")
async def ci_fault():
    return _ci.list_fault_attacks()

@router.get("/crypto-impl/nonce-attacks")
async def ci_nonce():
    return _ci.list_nonce_attacks()

@router.get("/crypto-impl/cold-boot")
async def ci_cold_boot():
    return _ci.get_cold_boot_info()

@router.post("/crypto-impl/simulate-ecdsa-nonce-reuse")
async def ci_ecdsa(req: AuthReq):
    _auth(req.authorization_confirmed, "crypto_ecdsa_nonce")
    return _ci.simulate_ecdsa_nonce_reuse()

@router.post("/crypto-impl/simulate-timing-oracle")
async def ci_timing(req: TimingOracleReq):
    _auth(req.authorization_confirmed, "crypto_timing_oracle")
    return _ci.simulate_timing_oracle(req.attack_type, req.samples)

@router.post("/crypto-impl/analyze-code")
async def ci_analyze(req: CodeAnalyzeReq):
    _auth(req.authorization_confirmed, "crypto_code_analyze")
    return _ci.analyze_crypto_implementation(req.code_snippet, req.language)


# ── KEY MANAGEMENT & SECURE COMMS ─────────────────────────────────────────────

class KeyGenReq(AuthReq):
    algorithm:     str  = "kyber_768_sim"
    label:         str  = ""
    exportable:    bool = False
    hsm_protected: bool = True

class QKDSessionReq(AuthReq):
    protocol:        str   = "bb84"
    distance_km:     float = 50.0
    target_key_bits: int   = 256

class KeyDeriveReq(AuthReq):
    master_key_hex: str = ""
    context:        str = "encryption"
    output_bits:    int = 256


@router.get("/keymanager/algorithms")
async def km_algos():
    return _km.list_key_algorithms()

@router.get("/keymanager/qkd-protocols")
async def km_qkd_list():
    return _km.list_qkd_protocols()

@router.get("/keymanager/qkd/{protocol}")
async def km_qkd_detail(protocol: str):
    return _km.get_qkd_detail(protocol)

@router.get("/keymanager/secure-protocols")
async def km_protocols():
    return _km.list_secure_protocols()

@router.get("/keymanager/hsm-operations")
async def km_hsm():
    return _km.list_hsm_operations()

@router.post("/keymanager/generate")
async def km_generate(req: KeyGenReq):
    _auth(req.authorization_confirmed, "key_generate")
    return _km.generate_key(req.algorithm, req.label, req.exportable, req.hsm_protected)

@router.get("/keymanager/list")
async def km_list():
    return _km.list_keys()

@router.get("/keymanager/key/{key_id}")
async def km_get(key_id: str):
    return _km.get_key(key_id)

@router.post("/keymanager/qkd-session")
async def km_qkd(req: QKDSessionReq):
    _auth(req.authorization_confirmed, "qkd_session")
    return _km.simulate_qkd_session(req.protocol, req.distance_km, req.target_key_bits)

@router.post("/keymanager/derive")
async def km_derive(req: KeyDeriveReq):
    _auth(req.authorization_confirmed, "key_derive")
    return _km.derive_key(req.master_key_hex, req.context, req.output_bits)

@router.get("/keymanager/pfs/{protocol}")
async def km_pfs(protocol: str):
    return _km.analyze_pfs(protocol)
