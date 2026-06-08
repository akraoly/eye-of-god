"""
Routes — Bloc 9 Influence Stratégique & Guerre de l'Information
Usage exclusivement légal — red team IO, contre-ingérence, recherche défensive.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, List, Optional

from services.influence.influence_ops_service import InfluenceOpsService
from services.influence.disinfo_service import DisinfoService
from services.influence.psyop_service import PsyopService
from services.influence.io_attribution_service import IOAttributionService
from services.influence.narrative_monitor_service import NarrativeMonitorService

router = APIRouter()

_io   = InfluenceOpsService()
_dis  = DisinfoService()
_psy  = PsyopService()
_attr = IOAttributionService()
_nm   = NarrativeMonitorService()


def _auth(confirmed: bool, action: str):
    if not confirmed:
        raise HTTPException(status_code=403, detail=f"authorization_confirmed requis pour: {action}")


# ─── Modèles Pydantic ─────────────────────────────────────────────────────────

class AuthBase(BaseModel):
    authorization_confirmed: bool = False

class DesignCampaignReq(AuthBase):
    name: str
    objective: str
    target_audience: str
    platforms: List[str] = ["twitter_x", "telegram"]
    tactics: List[str] = ["narrative_seeding", "amplification_network"]
    budget_accounts: int = 50
    duration_days: int = 30

class SockpuppetReq(AuthBase):
    profile_type: str = "authentic_citizen"
    count: int = 5
    language: str = "fr"
    country: str = "France"

class MetadataForgeReq(AuthBase):
    file_type: str = "image_exif"
    target_date: Optional[str] = None
    target_location: Optional[str] = None
    target_author: Optional[str] = None
    target_device: Optional[str] = None

class AuthenticityReq(AuthBase):
    metadata_json: str

class SyntheticDetectReq(BaseModel):
    content_type: str
    indicators: List[str]

class TargetProfileReq(AuthBase):
    segment: str
    context: str = ""
    vulnerabilities: Optional[List[str]] = None

class PsyopMessageReq(AuthBase):
    framework: str = "SCAME"
    target_segment: str = "casual_news_follower"
    objective: str
    core_narrative: str
    biases_to_exploit: Optional[List[str]] = None

class IOResilienceReq(BaseModel):
    organization: str
    checks: Optional[List[str]] = None

class IOCampaignAnalyzeReq(AuthBase):
    campaign_indicators: Dict = {}
    platforms: List[str]
    narratives: List[str]
    temporal_pattern: Optional[str] = None

class CanaryTrapReq(AuthBase):
    document_name: str
    suspects: List[str]
    variation_type: str = "timestamp"

class CounterIntelReq(BaseModel):
    org_name: str
    frameworks_applied: Optional[List[str]] = None

class MonitorStartReq(BaseModel):
    keywords: List[str]
    categories: Optional[List[str]] = None
    platforms: Optional[List[str]] = None
    alert_threshold: int = 100

class CIBDetectReq(BaseModel):
    keywords: List[str]
    time_window_hours: int = 24

class CounterNarrativeReq(AuthBase):
    false_claim: str
    strategy: str = "debunking"
    target_audience: str = "general"
    evidence_links: Optional[List[str]] = None


# ─── Influence Ops ─────────────────────────────────────────────────────────────

@router.get("/io-ops/platforms")
async def list_platforms():
    return _io.list_platforms()

@router.get("/io-ops/sockpuppet-profiles")
async def list_sockpuppet_profiles():
    return _io.list_sockpuppet_profiles()

@router.get("/io-ops/tactics")
async def list_io_tactics():
    return _io.list_tactics()

@router.get("/io-ops/detection-indicators")
async def list_detection_indicators():
    return _io.list_detection_indicators()

@router.post("/io-ops/design-campaign")
async def design_campaign(req: DesignCampaignReq):
    _auth(req.authorization_confirmed, "design_io_campaign")
    return _io.design_campaign(
        req.name, req.objective, req.target_audience,
        req.platforms, req.tactics, req.budget_accounts, req.duration_days,
    )

@router.post("/io-ops/sockpuppet-network")
async def generate_sockpuppet_network(req: SockpuppetReq):
    _auth(req.authorization_confirmed, "generate_sockpuppet_network")
    return _io.generate_sockpuppet_network(req.profile_type, req.count, req.language, req.country)

@router.get("/io-ops/campaigns")
async def list_io_campaigns():
    return _io.list_campaigns()

@router.get("/io-ops/campaign/{campaign_id}")
async def get_io_campaign(campaign_id: str):
    return _io.get_campaign(campaign_id)


# ─── Disinformation ────────────────────────────────────────────────────────────

@router.get("/disinfo/archetypes")
async def list_disinfo_archetypes():
    return _dis.list_archetypes()

@router.get("/disinfo/archetype/{archetype}")
async def get_disinfo_archetype(archetype: str):
    return _dis.get_archetype_detail(archetype)

@router.get("/disinfo/metadata-fields")
async def list_metadata_fields(file_type: str = "image_exif"):
    return _dis.list_metadata_fields(file_type)

@router.get("/disinfo/detection-methods")
async def list_detection_methods():
    return _dis.list_detection_methods()

@router.post("/disinfo/forge-metadata")
async def forge_metadata(req: MetadataForgeReq):
    _auth(req.authorization_confirmed, "forge_metadata")
    return _dis.simulate_metadata_forge(
        req.file_type, req.target_date, req.target_location,
        req.target_author, req.target_device,
    )

@router.post("/disinfo/analyze-authenticity")
async def analyze_authenticity(req: AuthenticityReq):
    _auth(req.authorization_confirmed, "analyze_document_authenticity")
    return _dis.analyze_document_authenticity(req.metadata_json)

@router.post("/disinfo/detect-synthetic")
async def detect_synthetic(req: SyntheticDetectReq):
    return _dis.detect_synthetic_content(req.content_type, req.indicators)

@router.get("/disinfo/result/{result_id}")
async def get_disinfo_result(result_id: str):
    return _dis.get_result(result_id)


# ─── PSYOP ─────────────────────────────────────────────────────────────────────

@router.get("/psyop/cognitive-biases")
async def list_cognitive_biases():
    return _psy.list_cognitive_biases()

@router.get("/psyop/bias/{bias}")
async def get_bias_detail(bias: str):
    return _psy.get_bias_detail(bias)

@router.get("/psyop/frameworks")
async def list_psyop_frameworks():
    return _psy.list_psyop_frameworks()

@router.get("/psyop/target-segments")
async def list_target_segments():
    return _psy.list_target_segments()

@router.get("/psyop/countermeasures")
async def list_io_countermeasures():
    return _psy.list_countermeasures()

@router.post("/psyop/profile-segment")
async def profile_target_segment(req: TargetProfileReq):
    _auth(req.authorization_confirmed, "profile_target_segment")
    return _psy.profile_target_segment(req.segment, req.context, req.vulnerabilities)

@router.post("/psyop/design-message")
async def design_psyop_message(req: PsyopMessageReq):
    _auth(req.authorization_confirmed, "design_psyop_message")
    return _psy.design_psyop_message(
        req.framework, req.target_segment, req.objective,
        req.core_narrative, req.biases_to_exploit,
    )

@router.post("/psyop/io-resilience")
async def assess_io_resilience(req: IOResilienceReq):
    return _psy.assess_io_resilience(req.organization, req.checks)

@router.get("/psyop/profile/{profile_id}")
async def get_psyop_profile(profile_id: str):
    return _psy.get_profile(profile_id)


# ─── IO Attribution ────────────────────────────────────────────────────────────

@router.get("/attribution/actors")
async def list_known_actors():
    return _attr.list_known_actors()

@router.get("/attribution/actor/{actor}")
async def get_actor_detail(actor: str):
    return _attr.get_actor_detail(actor)

@router.get("/attribution/indicators")
async def list_attribution_indicators():
    return _attr.list_attribution_indicators()

@router.get("/attribution/counterintel-frameworks")
async def list_counterintel_frameworks():
    return _attr.list_counterintel_frameworks()

@router.post("/attribution/analyze-campaign")
async def analyze_io_campaign(req: IOCampaignAnalyzeReq):
    _auth(req.authorization_confirmed, "analyze_io_campaign")
    return _attr.analyze_io_campaign(
        req.campaign_indicators, req.platforms, req.narratives, req.temporal_pattern,
    )

@router.post("/attribution/canary-trap")
async def setup_canary_trap(req: CanaryTrapReq):
    _auth(req.authorization_confirmed, "canary_trap_setup")
    return _attr.canary_trap_setup(req.document_name, req.suspects, req.variation_type)

@router.post("/attribution/counterintel-check")
async def counterintel_check(req: CounterIntelReq):
    return _attr.opsec_counterintel_check(req.org_name, req.frameworks_applied)

@router.get("/attribution/analysis/{analysis_id}")
async def get_io_analysis(analysis_id: str):
    return _attr.get_analysis(analysis_id)


# ─── Narrative Monitor ─────────────────────────────────────────────────────────

@router.get("/monitor/categories")
async def list_narrative_categories():
    return _nm.list_narrative_categories()

@router.get("/monitor/fact-check-orgs")
async def list_fact_check_orgs():
    return _nm.list_fact_check_orgs()

@router.get("/monitor/counter-strategies")
async def list_counter_strategies():
    return _nm.list_counter_strategies()

@router.get("/monitor/sources")
async def list_monitoring_sources():
    return _nm.list_monitoring_sources()

@router.post("/monitor/start")
async def start_monitoring(req: MonitorStartReq):
    return _nm.start_monitoring(req.keywords, req.categories, req.platforms, req.alert_threshold)

@router.post("/monitor/detect-cib")
async def detect_coordinated_behavior(req: CIBDetectReq):
    return _nm.detect_coordinated_behavior(req.keywords, req.time_window_hours)

@router.post("/monitor/counter-narrative")
async def generate_counter_narrative(req: CounterNarrativeReq):
    _auth(req.authorization_confirmed, "generate_counter_narrative")
    return _nm.generate_counter_narrative(
        req.false_claim, req.strategy, req.target_audience, req.evidence_links,
    )

@router.get("/monitor/monitors")
async def list_monitors():
    return _nm.list_monitors()

@router.get("/monitor/{monitor_id}")
async def get_monitor(monitor_id: str):
    return _nm.get_monitor(monitor_id)

@router.get("/monitor/alert/{alert_id}")
async def get_alert(alert_id: str):
    return _nm.get_alert(alert_id)
