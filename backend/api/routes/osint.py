"""
Routes /api/osint — OSINTAgent (Module 7).

SSE-streaming full recon + individual lookup endpoints.
All endpoints are JWT-protected via the main router.
JWT can also be passed as ?token=xxx for EventSource compatibility.
"""
from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database.db import get_db
from core.agents.osint_agent import OSINTAgent
from core.auth.jwt_handler import decode_access_token

router = APIRouter()
_agent = OSINTAgent()

# In-memory job store for SSE streaming
_active_jobs: dict = {}


# ── Request models ─────────────────────────────────────────────────────────────

class ReconRequest(BaseModel):
    target: str = Field(..., description="Domain, IP, or organisation name")
    options: dict = Field(
        default_factory=dict,
        description="Optional flags: {check_breaches: bool}",
    )


class DnsRequest(BaseModel):
    domain: str = Field(..., description="Domain to enumerate")


class SubdomainRequest(BaseModel):
    domain: str = Field(..., description="Root domain")


class BreachRequest(BaseModel):
    email_or_domain: str = Field(..., description="Email address or domain")


class MetadataRequest(BaseModel):
    file_path: str = Field(..., description="Absolute path to file for metadata extraction")


class ShodanRequest(BaseModel):
    query: str = Field(..., description="IP address or Shodan search query")


# ── JWT-for-EventSource helper ─────────────────────────────────────────────────

def _auth_token(token: str = Query(None), db: Session = Depends(get_db)):
    """Allow JWT via ?token=xxx for EventSource (browser SSE)."""
    if not token:
        raise HTTPException(status_code=401, detail="Token requis")
    try:
        import jwt
        user_id = decode_access_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Token invalide")
    return user_id


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post("/recon")
async def start_recon(req: ReconRequest, db: Session = Depends(get_db)):
    """
    Start a full OSINT recon job.
    Returns job_id — stream results via GET /api/osint/stream/{job_id}.
    """
    if not req.target.strip():
        raise HTTPException(status_code=400, detail="Target required")

    job_id = uuid.uuid4().hex[:12]

    # Persist job to DB
    try:
        from database.models import OsintJob
        job = OsintJob(
            job_id=job_id,
            target=req.target.strip(),
            status="pending",
            results=None,
        )
        db.add(job)
        db.commit()
    except Exception:
        pass

    return {
        "job_id": job_id,
        "target": req.target,
        "status": "pending",
        "stream_url": f"/api/osint/stream/{job_id}",
    }


@router.get("/stream/{job_id}")
async def stream_recon(
    job_id: str,
    db: Session = Depends(get_db),
    token: str = Query(None),
):
    """
    SSE stream for an OSINT recon job.
    Pass JWT as ?token=xxx for browser EventSource.
    """
    # Token auth for SSE (EventSource can't set headers)
    if token:
        try:
            decode_access_token(token)
        except Exception:
            raise HTTPException(status_code=401, detail="Token invalide")

    # Retrieve job
    target = None
    try:
        from database.models import OsintJob
        job = db.query(OsintJob).filter_by(job_id=job_id).first()
        if not job:
            raise HTTPException(status_code=404, detail="Job introuvable")
        target = job.target
        if job.status == "completed":
            results = job.results or {}
            async def _already_done():
                payload = json.dumps({
                    "type": "already_done",
                    "job_id": job_id,
                    "target": target,
                    "status": "completed",
                    "data": results,
                }, ensure_ascii=False)
                yield f"data: {payload}\n\n"
            return StreamingResponse(
                _already_done(),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
            )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    # Update status
    try:
        from database.models import OsintJob
        job = db.query(OsintJob).filter_by(job_id=job_id).first()
        if job:
            job.status = "running"
            db.commit()
    except Exception:
        pass

    async def _event_generator():
        all_results = {}
        try:
            async for event in _agent.full_recon(target, {}, job_id=job_id):
                payload = json.dumps(event, ensure_ascii=False)
                yield f"data: {payload}\n\n"
                await asyncio.sleep(0)
                # Capture final results
                if event.get("type") == "complete":
                    all_results = event.get("data", {})
        except Exception as exc:
            error_payload = json.dumps({
                "type": "error",
                "job_id": job_id,
                "message": str(exc),
            })
            yield f"data: {error_payload}\n\n"
        finally:
            # Persist results
            try:
                from database.db import SessionLocal
                from database.models import OsintJob
                with SessionLocal() as new_db:
                    j = new_db.query(OsintJob).filter_by(job_id=job_id).first()
                    if j:
                        j.status = "completed"
                        j.results = all_results
                        new_db.commit()
            except Exception:
                pass

    return StreamingResponse(
        _event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/dns")
async def dns_enum(req: DnsRequest):
    """DNS enumeration (A, AAAA, MX, NS, TXT, CNAME, SOA, zone transfer)."""
    result = await _agent.dns_enum(req.domain)
    return result


@router.post("/subdomains")
async def subdomain_discovery(req: SubdomainRequest):
    """Subdomain discovery via crt.sh, sublist3r, and amass."""
    result = await _agent.subdomain_discovery(req.domain)
    return result


@router.get("/dorks/{target:path}")
async def get_dorks(target: str):
    """Generate Google dork strings for a target (not executed)."""
    dorks = await _agent.google_dorks(target)
    return {"target": target, "count": len(dorks), "dorks": dorks}


@router.post("/breach")
async def check_breach(req: BreachRequest):
    """Check email or domain against HaveIBeenPwned."""
    result = await _agent.check_breach(req.email_or_domain)
    return result


@router.post("/shodan")
async def shodan_lookup(req: ShodanRequest):
    """Shodan host lookup or search query."""
    result = await _agent.shodan_lookup(req.query)
    return result


@router.post("/metadata")
async def analyze_metadata(req: MetadataRequest):
    """Extract metadata from a file with exiftool."""
    result = await _agent.analyze_metadata(req.file_path)
    if result.get("available") is False:
        raise HTTPException(status_code=503, detail=result.get("error", "exiftool unavailable"))
    return result


@router.get("/jobs")
async def list_jobs(db: Session = Depends(get_db), limit: int = Query(20, le=100)):
    """List OSINT recon jobs."""
    try:
        from database.models import OsintJob
        jobs = (
            db.query(OsintJob)
            .order_by(OsintJob.created_at.desc())
            .limit(limit)
            .all()
        )
        return {
            "jobs": [
                {
                    "job_id": j.job_id,
                    "target": j.target,
                    "status": j.status,
                    "created_at": j.created_at.isoformat() if j.created_at else None,
                }
                for j in jobs
            ]
        }
    except Exception as exc:
        return {"jobs": [], "error": str(exc)}


@router.get("/jobs/{job_id}")
async def get_job(job_id: str, db: Session = Depends(get_db)):
    """Get OSINT job results."""
    try:
        from database.models import OsintJob
        job = db.query(OsintJob).filter_by(job_id=job_id).first()
        if not job:
            raise HTTPException(status_code=404, detail="Job introuvable")
        return {
            "job_id": job.job_id,
            "target": job.target,
            "status": job.status,
            "results": job.results or {},
            "created_at": job.created_at.isoformat() if job.created_at else None,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
