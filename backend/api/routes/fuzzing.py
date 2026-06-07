"""
Routes /api/fuzzing — AFL++, boofuzz, ffuf fuzzing engine.
"""
from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from core.engines.fuzzing_engine import FuzzingEngine

router = APIRouter()
_engine = FuzzingEngine()


# ── Request models ────────────────────────────────────────────────────────────

class AflFuzzRequest(BaseModel):
    binary_path: str
    corpus_dir: Optional[str] = None
    output_dir: Optional[str] = None
    timeout_hours: int = 1


class NetworkFuzzRequest(BaseModel):
    target_ip: str
    target_port: int
    protocol_name: str = "custom"
    request_template_hex: Optional[str] = None  # hex-encoded bytes


class WebFuzzRequest(BaseModel):
    base_url: str
    wordlist: Optional[str] = None
    method: str = "GET"
    data: Optional[str] = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/afl")
async def start_afl(req: AflFuzzRequest):
    """Start AFL++ binary fuzzing job."""
    result = await _engine.start_afl_fuzzing(
        binary_path=req.binary_path,
        corpus_dir=req.corpus_dir,
        output_dir=req.output_dir,
        timeout_hours=req.timeout_hours,
    )
    if result.get("available") is False:
        raise HTTPException(status_code=503, detail=result["message"])
    return result


@router.post("/network")
async def start_network_fuzz(req: NetworkFuzzRequest):
    """Start boofuzz network protocol fuzzing job."""
    template: Optional[bytes] = None
    if req.request_template_hex:
        try:
            template = bytes.fromhex(req.request_template_hex)
        except ValueError:
            raise HTTPException(status_code=400, detail="request_template_hex must be valid hex")

    result = await _engine.fuzz_network_protocol(
        target_ip=req.target_ip,
        target_port=req.target_port,
        protocol_name=req.protocol_name,
        request_template=template,
    )
    if result.get("available") is False:
        raise HTTPException(status_code=503, detail=result["message"])
    return result


@router.post("/web")
async def start_web_fuzz(req: WebFuzzRequest):
    """Start ffuf web endpoint fuzzing job."""
    if not req.base_url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="base_url must start with http:// or https://")

    result = await _engine.fuzz_web_endpoints(
        base_url=req.base_url,
        wordlist=req.wordlist,
        method=req.method,
        data=req.data,
    )
    if result.get("available") is False:
        raise HTTPException(status_code=503, detail=result["message"])
    return result


@router.get("/job/{job_id}")
async def get_job_status(job_id: str):
    """Get fuzzing job status."""
    result = await _engine.monitor_job(job_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.get("/jobs")
async def list_jobs(limit: int = Query(50, ge=1, le=200)):
    """List all fuzzing jobs."""
    return {"jobs": await _engine.list_jobs(limit=limit)}


@router.get("/crashes/{job_id}")
async def get_crashes(job_id: str):
    """Analyze crash files for a fuzzing job."""
    job = await _engine.monitor_job(job_id)
    if "error" in job:
        raise HTTPException(status_code=404, detail=job["error"])

    crash_dir = job.get("crash_dir", "")
    if not crash_dir:
        return {"crashes": [], "message": "No crash directory for this job"}

    crashes = await _engine.get_crash_analysis(crash_dir)
    return {
        "job_id": job_id,
        "crash_dir": crash_dir,
        "total_crashes": len(crashes),
        "crashes": crashes,
    }


@router.post("/stop/{job_id}")
async def stop_job(job_id: str):
    """Stop a running fuzzing job."""
    stopped = await _engine.stop_job(job_id)
    return {"job_id": job_id, "stopped": stopped, "message": f"Job {job_id} stop requested"}
