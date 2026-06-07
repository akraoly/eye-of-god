"""
Routes /api/credentials — CredentialAgent (Module 9).

Hash identification, cracking, validation, Kerbrute, and encrypted storage.
All endpoints are JWT-protected via the main router.
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database.db import get_db
from core.agents.credential_agent import CredentialAgent

router = APIRouter()
_agent = CredentialAgent()


# ── Request models ─────────────────────────────────────────────────────────────

class IdentifyHashRequest(BaseModel):
    hash_str: str = Field(..., description="Hash string to identify")


class CrackHashRequest(BaseModel):
    hash_str: str = Field(..., description="Hash to crack")
    hash_type: str = Field(..., description="Hashcat mode number e.g. '0'=MD5, '1000'=NTLM")
    wordlist: str = Field(
        "/usr/share/wordlists/rockyou.txt",
        description="Path to wordlist file",
    )
    rules: Optional[str] = Field(None, description="Path to hashcat rules file")


class CrackFileRequest(BaseModel):
    hash_file: str = Field(..., description="Path to file containing hashes")
    hash_type: str = Field(..., description="Hashcat mode number")
    wordlist: str = Field("/usr/share/wordlists/rockyou.txt")


class ValidateRequest(BaseModel):
    target: str = Field(..., description="Target IP / hostname")
    username: str
    password: str
    protocol: str = Field("smb", description="smb | winrm | ssh | ldap | mssql | rdp")


class KerbruteRequest(BaseModel):
    domain: str = Field(..., description="Active Directory domain")
    dc_ip: str = Field(..., description="Domain controller IP")
    userlist: str = Field(..., description="Path to username list")
    mode: str = Field("userenum", description="userenum | bruteuser | passwordspray | bruteforce")


class StoreCredentialRequest(BaseModel):
    target: str
    username: str
    password_or_hash: str = Field(..., description="Plaintext password or hash")
    source: str = Field("manual", description="Origin: hashcat | kerbrute | cme | manual | breach")
    hash_type: Optional[str] = None
    is_valid: bool = False


class AnalyzePasswordsRequest(BaseModel):
    passwords: List[str] = Field(..., description="List of cracked plaintext passwords")


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post("/identify")
async def identify_hash(req: IdentifyHashRequest):
    """Identify hash type using pattern matching and hashid."""
    result = await _agent.identify_hash(req.hash_str)
    return result


@router.post("/crack")
async def crack_hash(req: CrackHashRequest):
    """
    Crack a hash with hashcat (dictionary attack).
    Returns immediately with result; for long jobs use Celery.
    """
    result = await _agent.crack_hash(
        hash_str=req.hash_str,
        hash_type=req.hash_type,
        wordlist=req.wordlist,
        rules=req.rules,
    )
    if result.get("available") is False:
        raise HTTPException(status_code=503, detail=result.get("error", "hashcat unavailable"))
    return result


@router.post("/crack/file")
async def crack_file(req: CrackFileRequest):
    """Crack multiple hashes from a file with hashcat."""
    result = await _agent.crack_file(
        hash_file=req.hash_file,
        hash_type=req.hash_type,
        wordlist=req.wordlist,
    )
    if result.get("available") is False:
        raise HTTPException(status_code=503, detail=result.get("error", "hashcat unavailable"))
    return result


@router.get("/crack/status/{job_id}")
async def crack_job_status(job_id: str):
    """
    Get crack job status (Celery).
    Requires Celery worker and Redis running.
    """
    try:
        from core.tasks.celery_app import celery_app
        result = celery_app.AsyncResult(job_id)
        return {
            "job_id": job_id,
            "status": result.status,
            "result": result.result if result.ready() else None,
            "info": result.info if not result.ready() else None,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Celery error: {exc}")


@router.post("/crack/async")
async def crack_hash_async(req: CrackHashRequest):
    """
    Submit a hash crack job to Celery (background).
    Returns job_id — poll via GET /crack/status/{job_id}.
    """
    try:
        from core.tasks.exploit_tasks import crack_hash_task
        task = crack_hash_task.delay(
            hash_str=req.hash_str,
            hash_type=req.hash_type,
            wordlist=req.wordlist,
            rules=req.rules,
        )
        return {
            "job_id": task.id,
            "status": "queued",
            "message": "Job submitted to Celery. Poll /crack/status/{job_id}",
        }
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Celery unavailable: {exc}. Use POST /crack for synchronous mode.",
        )


@router.post("/validate")
async def validate_credentials(req: ValidateRequest):
    """Validate credentials via CrackMapExec (CME)."""
    result = await _agent.validate_credentials(
        target=req.target,
        username=req.username,
        password=req.password,
        protocol=req.protocol,
    )
    if result.get("available") is False:
        raise HTTPException(status_code=503, detail=result.get("error", "CME unavailable"))
    return result


@router.post("/kerbrute")
async def kerbrute(req: KerbruteRequest):
    """Run Kerbrute against an Active Directory domain."""
    result = await _agent.kerbrute(
        domain=req.domain,
        dc_ip=req.dc_ip,
        userlist=req.userlist,
        mode=req.mode,
    )
    if result.get("available") is False:
        raise HTTPException(status_code=503, detail=result.get("error", "kerbrute unavailable"))
    return result


@router.get("/")
async def list_credentials(
    target: Optional[str] = Query(None, description="Filter by target"),
):
    """List stored credentials (passwords masked)."""
    creds = await _agent.list_credentials(target=target)
    return {"count": len(creds), "credentials": creds}


@router.post("/store")
async def store_credential(req: StoreCredentialRequest):
    """Store a credential encrypted with Fernet."""
    cred_id = await _agent.store_credential(
        target=req.target,
        username=req.username,
        password_or_hash=req.password_or_hash,
        source=req.source,
        hash_type=req.hash_type,
        is_valid=req.is_valid,
    )
    return {"cred_id": cred_id, "message": "Credential stored (encrypted)"}


@router.delete("/{cred_id}")
async def delete_credential(cred_id: str, db: Session = Depends(get_db)):
    """Delete a stored credential by cred_id."""
    try:
        from database.models import CrackedCredential
        deleted = (
            db.query(CrackedCredential)
            .filter(CrackedCredential.cred_id == cred_id)
            .delete()
        )
        db.commit()
        if not deleted:
            raise HTTPException(status_code=404, detail="Credential not found")
        return {"message": f"Credential {cred_id} deleted"}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/analyze/patterns")
async def analyze_patterns(req: AnalyzePasswordsRequest):
    """Analyze cracked password patterns to build a targeted wordlist strategy."""
    if not req.passwords:
        raise HTTPException(status_code=400, detail="Password list required")
    result = await _agent.analyze_password_patterns(req.passwords)
    return result
