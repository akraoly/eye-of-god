"""Automation Stratégique Routes — Bloc 7 Supra-Étatiques."""
from __future__ import annotations
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

from services.automation.attack_planner_service  import AttackPlannerService
from services.automation.campaign_manager_service import CampaignManagerService
from services.automation.anti_forensics_service   import AntiForensicsService
from services.automation.payload_builder_service  import PayloadBuilderService
from services.automation.opsec_service            import OpsecService

router = APIRouter()
_plan  = AttackPlannerService()
_camp  = CampaignManagerService()
_af    = AntiForensicsService()
_pay   = PayloadBuilderService()
_ops   = OpsecService()


def _auth(confirmed: bool, action: str):
    if not confirmed:
        raise HTTPException(403, f"authorization_confirmed=true requis pour: {action}")


class AuthReq(BaseModel):
    authorization_confirmed: bool = False


# ── ATTACK PLANNER ─────────────────────────────────────────────────────────────

class AttackPlanReq(AuthReq):
    target_profile:   str  = "corporate_windows"
    objective:        str  = "intelligence_gathering"
    operator_skill:   str  = "expert"
    time_budget_days: int  = 90
    stealth_priority: str  = "high"


@router.get("/planner/profiles")
async def plan_profiles():
    return _plan.list_target_profiles()

@router.get("/planner/objectives")
async def plan_objectives():
    return _plan.list_objectives()

@router.get("/planner/kill-chain")
async def plan_kill_chain():
    return _plan.list_kill_chain()

@router.post("/planner/generate")
async def plan_generate(req: AttackPlanReq):
    _auth(req.authorization_confirmed, "attack_plan_generate")
    return _plan.generate_attack_plan(
        req.target_profile, req.objective, req.operator_skill,
        req.time_budget_days, req.stealth_priority
    )

@router.get("/planner/plans")
async def plan_list():
    return _plan.list_plans()

@router.get("/planner/plan/{plan_id}")
async def plan_get(plan_id: str):
    return _plan.get_plan(plan_id)

@router.get("/planner/graph/{plan_id}")
async def plan_graph(plan_id: str):
    return _plan.build_attack_graph(plan_id)

@router.get("/planner/detection-risk/{plan_id}")
async def plan_detection_risk(plan_id: str):
    return _plan.assess_detection_risk(plan_id)


# ── CAMPAIGN MANAGER ───────────────────────────────────────────────────────────

class CampaignCreateReq(AuthReq):
    name:           str         = "Operation BlackSun"
    operation_type: str         = "apt_espionage"
    targets:        List[Dict]  = [{"name": "Target Corp", "sector": "energy"}]
    operator:       str         = "operator_1"
    start_date:     Optional[str] = None
    phases:         Optional[List[str]] = None

class CampaignStatusReq(AuthReq):
    status: str = "active"

class CampaignPhaseReq(AuthReq):
    phase_name:   str = "reconnaissance"
    progress_pct: int = 100

class CampaignHostReq(AuthReq):
    hostname:     str = "WORKSTATION-001"
    access_level: str = "user"


@router.get("/campaign/operation-types")
async def camp_op_types():
    return _camp.list_operation_types()

@router.get("/campaign/asset-types")
async def camp_asset_types():
    return _camp.list_asset_types()

@router.post("/campaign/create")
async def camp_create(req: CampaignCreateReq):
    _auth(req.authorization_confirmed, "campaign_create")
    return _camp.create_campaign(
        req.name, req.operation_type, req.targets, req.operator, req.start_date, req.phases
    )

@router.get("/campaign/list")
async def camp_list():
    return _camp.list_campaigns()

@router.get("/campaign/{campaign_id}")
async def camp_get(campaign_id: str):
    return _camp.get_campaign(campaign_id)

@router.post("/campaign/{campaign_id}/status")
async def camp_status(campaign_id: str, req: CampaignStatusReq):
    _auth(req.authorization_confirmed, "campaign_status_update")
    return _camp.update_campaign_status(campaign_id, req.status)

@router.post("/campaign/{campaign_id}/advance-phase")
async def camp_phase(campaign_id: str, req: CampaignPhaseReq):
    _auth(req.authorization_confirmed, "campaign_advance_phase")
    return _camp.advance_phase(campaign_id, req.phase_name, req.progress_pct)

@router.post("/campaign/{campaign_id}/add-host")
async def camp_host(campaign_id: str, req: CampaignHostReq):
    _auth(req.authorization_confirmed, "campaign_add_host")
    return _camp.add_compromised_host(campaign_id, req.hostname, req.access_level)

@router.get("/campaign/{campaign_id}/report")
async def camp_report(campaign_id: str):
    return _camp.generate_campaign_report(campaign_id)


# ── ANTI-FORENSICS ─────────────────────────────────────────────────────────────

class LogClearReq(AuthReq):
    os_type:  str       = "linux"
    targets:  List[str] = ["bash_history","auth_log"]
    dry_run:  bool      = True

class TimestompReq(AuthReq):
    target_path:    str  = "/tmp/test_file"
    technique:      str  = "mace_clone"
    reference_file: Optional[str] = None
    custom_date:    Optional[str] = None

class MemoryEvasionReq(AuthReq):
    techniques: List[str] = ["dll_unhooking","beacon_sleep_obfuscation","syscall_direct"]

class SecureDeleteReq(AuthReq):
    files:  List[str] = ["/tmp/stager","/tmp/beacon"]
    method: str       = "random_overwrite"

class FullCleanupReq(AuthReq):
    os_type:  str = "linux"
    scenario: str = "post_exfil"


@router.get("/antiforensics/log-targets")
async def af_log_targets(os: str = "linux"):
    return _af.list_log_targets(os)

@router.get("/antiforensics/timestomp-techniques")
async def af_timestomp_list():
    return _af.list_timestomp_techniques()

@router.get("/antiforensics/memory-evasion-list")
async def af_memory_list():
    return _af.list_memory_evasion()

@router.get("/antiforensics/secure-delete-methods")
async def af_delete_methods():
    return _af.list_secure_delete()

@router.post("/antiforensics/clear-logs")
async def af_clear(req: LogClearReq):
    _auth(req.authorization_confirmed, "antiforensics_clear_logs")
    return _af.clear_logs(req.os_type, req.targets, req.dry_run)

@router.post("/antiforensics/timestomp")
async def af_timestomp(req: TimestompReq):
    _auth(req.authorization_confirmed, "antiforensics_timestomp")
    return _af.timestomp_file(req.target_path, req.technique, req.reference_file, req.custom_date)

@router.post("/antiforensics/memory-evasion")
async def af_memory(req: MemoryEvasionReq):
    _auth(req.authorization_confirmed, "antiforensics_memory")
    return _af.memory_evasion_plan(req.techniques)

@router.post("/antiforensics/secure-delete")
async def af_delete(req: SecureDeleteReq):
    _auth(req.authorization_confirmed, "antiforensics_delete")
    return _af.secure_delete_plan(req.files, req.method)

@router.post("/antiforensics/full-cleanup")
async def af_full_cleanup(req: FullCleanupReq):
    _auth(req.authorization_confirmed, "antiforensics_full_cleanup")
    return _af.full_cleanup_plan(req.os_type, req.scenario)


# ── PAYLOAD BUILDER ────────────────────────────────────────────────────────────

class PayloadGenReq(AuthReq):
    payload_type:  str            = "staged_shellcode"
    lhost:         str            = "192.168.1.100"
    lport:         int            = 443
    lang:          str            = "csharp"
    obfuscation:   Optional[List[str]] = None
    c2_profile:    Optional[str]  = None
    target_os:     str            = "windows"

class PolyRebuildReq(AuthReq):
    pass

class StagerChainReq(AuthReq):
    lhost:  str = "192.168.1.100"
    lport:  int = 443
    stages: int = 3


@router.get("/payload/types")
async def pay_types():
    return _pay.list_payload_types()

@router.get("/payload/obfuscation")
async def pay_obfuscation():
    return _pay.list_obfuscation_layers()

@router.get("/payload/c2-profiles")
async def pay_c2_profiles():
    return _pay.list_c2_profiles()

@router.get("/payload/lolbins")
async def pay_lolbins():
    return _pay.list_lolbins()

@router.post("/payload/generate")
async def pay_generate(req: PayloadGenReq):
    _auth(req.authorization_confirmed, "payload_generate")
    return _pay.generate_payload(
        req.payload_type, req.lhost, req.lport, req.lang,
        req.obfuscation, req.c2_profile, req.target_os
    )

@router.get("/payload/list")
async def pay_list():
    return _pay.list_payloads()

@router.get("/payload/{payload_id}")
async def pay_get(payload_id: str):
    return _pay.get_payload(payload_id)

@router.post("/payload/{payload_id}/rebuild")
async def pay_rebuild(payload_id: str, req: PolyRebuildReq):
    _auth(req.authorization_confirmed, "payload_rebuild")
    return _pay.polymorphic_rebuild(payload_id)

@router.post("/payload/stager-chain")
async def pay_stager(req: StagerChainReq):
    _auth(req.authorization_confirmed, "payload_stager_chain")
    return _pay.generate_stager_chain(req.lhost, req.lport, req.stages)


# ── OPSEC ──────────────────────────────────────────────────────────────────────

class OpsecAssessReq(AuthReq):
    operation_name: str             = "Operation Alpha"
    checks_passed:  Dict[str, List[str]] = {}

class OpsecQuickReq(AuthReq):
    operation_name: str = "Quick Op"

class OpsecAttrReq(AuthReq):
    techniques:     List[str] = ["false_flag","living_off_the_land"]
    operation_type: str       = "apt_espionage"

class OpsecRotationReq(AuthReq):
    strategy:               str       = "phase_based"
    current_assets:         List[Dict] = []
    campaign_duration_days: int       = 90


@router.get("/opsec/categories")
async def opsec_cats():
    return _ops.list_categories()

@router.get("/opsec/attribution-techniques")
async def opsec_attr_list():
    return _ops.list_attribution_techniques()

@router.get("/opsec/rotation-strategies")
async def opsec_rotation_list():
    return _ops.list_rotation_strategies()

@router.post("/opsec/assess")
async def opsec_assess(req: OpsecAssessReq):
    _auth(req.authorization_confirmed, "opsec_assess")
    return _ops.assess_opsec(req.operation_name, req.checks_passed)

@router.post("/opsec/quick-assess")
async def opsec_quick(req: OpsecQuickReq):
    _auth(req.authorization_confirmed, "opsec_quick_assess")
    return _ops.quick_assess(req.operation_name)

@router.post("/opsec/attribution")
async def opsec_attr(req: OpsecAttrReq):
    _auth(req.authorization_confirmed, "opsec_attribution")
    return _ops.plan_attribution_reduction(req.techniques, req.operation_type)

@router.post("/opsec/rotation-plan")
async def opsec_rotation(req: OpsecRotationReq):
    _auth(req.authorization_confirmed, "opsec_rotation")
    return _ops.generate_rotation_plan(req.strategy, req.current_assets, req.campaign_duration_days)

@router.get("/opsec/assessment/{assessment_id}")
async def opsec_get(assessment_id: str):
    return _ops.get_assessment(assessment_id)
