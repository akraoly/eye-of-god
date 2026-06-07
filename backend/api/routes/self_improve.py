"""
Routes /api/self-improve — Platform self-improvement and intelligence engine.
"""
from __future__ import annotations

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from core.engines.self_improvement import SelfImprovementEngine

router = APIRouter()
_engine = SelfImprovementEngine()


# ── Request models ────────────────────────────────────────────────────────────

class RecordOutcomeRequest(BaseModel):
    operation_type: str
    target: str
    technique: str
    success: bool
    context: dict = {}
    reason: Optional[str] = None


class TargetProfileRequest(BaseModel):
    os: Optional[str] = None
    services: List[str] = []
    ports: List[int] = []
    domain: Optional[str] = None


class UpdateKnowledgeRequest(BaseModel):
    technique_id: Optional[str] = None
    name: str
    category: str
    description: str
    steps: Optional[str] = None
    tools: List[str] = []
    source_url: Optional[str] = None


class TrainingScenarioRequest(BaseModel):
    skill_gaps: List[str]


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/record")
async def record_outcome(req: RecordOutcomeRequest):
    """Record the outcome of an operation for learning."""
    outcome_id = await _engine.record_operation_outcome(
        operation_type=req.operation_type,
        target=req.target,
        technique=req.technique,
        success=req.success,
        context=req.context,
        reason=req.reason,
    )
    return {
        "outcome_id": outcome_id,
        "recorded": True,
        "technique": req.technique,
        "success": req.success,
        "message": f"Operation outcome recorded — technique stats updated",
    }


@router.get("/postmortem/{job_id}")
async def get_postmortem(job_id: str):
    """Generate or retrieve post-mortem analysis for a pentest job."""
    result = await _engine.generate_postmortem(job_id)
    return result


@router.get("/recommend/{target}")
async def get_recommendations(
    target: str,
    os: Optional[str] = Query(None),
    services: str = Query("", description="Comma-separated service names"),
    ports: str = Query("", description="Comma-separated port numbers"),
    domain: Optional[str] = Query(None),
):
    """Get technique recommendations based on target profile."""
    target_profile = {
        "target": target,
        "os": os or "unknown",
        "services": [s.strip() for s in services.split(",") if s.strip()],
        "ports": [int(p.strip()) for p in ports.split(",") if p.strip().isdigit()],
        "domain": domain,
    }
    recommendations = await _engine.get_technique_recommendations(target_profile)
    return {
        "target_profile": target_profile,
        "recommendations": recommendations,
        "count": len(recommendations),
    }


@router.get("/digest")
async def weekly_digest():
    """Generate weekly intelligence digest with new CVEs, techniques, and recommendations."""
    return await _engine.weekly_intelligence_digest()


@router.get("/gaps")
async def analyze_gaps():
    """Analyze skill gaps based on operations history."""
    return await _engine.analyze_skill_gaps()


@router.get("/techniques")
async def list_techniques(limit: int = Query(50, ge=1, le=500)):
    """List all learned techniques with success statistics."""
    techs = await _engine.get_learned_techniques(limit=limit)
    return {"techniques": techs, "count": len(techs)}


@router.post("/fetch-intelligence")
async def fetch_intelligence():
    """Manually trigger intelligence fetch from security blogs."""
    new_techs = await _engine.fetch_new_techniques()
    return {
        "fetched": len(new_techs),
        "articles": new_techs,
        "message": f"Fetched {len(new_techs)} relevant security articles",
    }


@router.post("/knowledge")
async def update_knowledge(req: UpdateKnowledgeRequest):
    """Add or update a technique in the knowledge base."""
    doc_id = await _engine.update_knowledge_base(req.dict())
    return {
        "doc_id": doc_id,
        "technique": req.name,
        "message": "Technique ingested into knowledge base",
    }


@router.post("/training-scenario")
async def generate_training(req: TrainingScenarioRequest):
    """Generate a CTF-style training scenario for given skill gaps."""
    if not req.skill_gaps:
        raise HTTPException(status_code=400, detail="skill_gaps list cannot be empty")
    scenario = await _engine.generate_training_scenario(req.skill_gaps)
    return scenario
