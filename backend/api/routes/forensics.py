"""
Routes /api/forensics — Malware analysis and digital forensics.
File analysis, IOC extraction, PowerShell deobfuscation, memory dump analysis.
"""
from __future__ import annotations

import json
import tempfile
import uuid
from pathlib import Path

from fastapi import APIRouter, Body, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database.db import get_db
from core.agents.forensics_agent import ForensicsAgent

router = APIRouter()
_agent = ForensicsAgent()

_UPLOAD_DIR = Path("./data/forensics_uploads")
_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


# ── Pydantic models ───────────────────────────────────────────────────────────

class PowerShellRequest(BaseModel):
    script: str


class MemoryDumpRequest(BaseModel):
    dump_path: str   # path on server filesystem


# ── File Analysis ─────────────────────────────────────────────────────────────

@router.post("/analyze")
async def analyze_file(
    file: UploadFile = File(...),
    db:   Session    = Depends(get_db),
):
    """
    Upload a file for malware/forensic analysis.
    Runs: file type detection, hash calculation, strings, IOC extraction, YARA, sandbox (if Docker available).
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename required")

    case_id   = str(uuid.uuid4())[:8]
    safe_name = "".join(c for c in file.filename if c.isalnum() or c in (".", "_", "-"))
    save_path = _UPLOAD_DIR / f"{case_id}_{safe_name}"

    try:
        content = await file.read()
        save_path.write_bytes(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"File save failed: {e}")

    try:
        result = await _agent.analyze_file(str(save_path), filename=file.filename)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {e}")

    # Persist to DB
    try:
        from database.models import ForensicsCase
        case = ForensicsCase(
            case_id=case_id,
            filename=file.filename,
            file_hash=result.get("file_hash", ""),
            file_type=result.get("file_type", ""),
            file_size=result.get("file_size", 0),
            iocs=json.dumps(result.get("iocs", {})),
            analysis_results=json.dumps({
                k: v for k, v in result.items()
                if k not in ("iocs", "strings_sample")
            }, default=str)[:8000],
            sandbox_output=result.get("sandbox", {}).get("stdout", "")[:3000],
            is_malicious=result.get("is_malicious", False),
            malware_family=result.get("malware_family"),
            status="completed",
        )
        db.add(case)
        db.commit()
        result["case_id"] = case_id
    except Exception:
        pass

    return result


# ── Case details ──────────────────────────────────────────────────────────────

@router.get("/case/{case_id}")
def get_case(case_id: str, db: Session = Depends(get_db)):
    """Get forensics case details by case ID."""
    try:
        from database.models import ForensicsCase
        case = db.query(ForensicsCase).filter_by(case_id=case_id).first()
        if not case:
            raise HTTPException(status_code=404, detail="Case not found")

        return {
            "case_id":        case.case_id,
            "filename":       case.filename,
            "file_hash":      case.file_hash,
            "file_type":      case.file_type,
            "file_size":      case.file_size,
            "iocs":           json.loads(case.iocs or "{}"),
            "analysis":       json.loads(case.analysis_results or "{}"),
            "sandbox_output": case.sandbox_output,
            "is_malicious":   case.is_malicious,
            "malware_family": case.malware_family,
            "stix_report":    json.loads(case.stix_report or "null"),
            "status":         case.status,
            "created_at":     case.created_at.isoformat() if case.created_at else None,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── List cases ────────────────────────────────────────────────────────────────

@router.get("/cases")
def list_cases(
    limit: int     = Query(20, le=100),
    db:    Session = Depends(get_db),
):
    """List all forensics cases."""
    try:
        from database.models import ForensicsCase
        cases = (
            db.query(ForensicsCase)
            .order_by(ForensicsCase.created_at.desc())
            .limit(limit)
            .all()
        )
        return {
            "cases": [
                {
                    "case_id":       c.case_id,
                    "filename":      c.filename,
                    "file_hash":     c.file_hash,
                    "file_type":     c.file_type,
                    "file_size":     c.file_size,
                    "is_malicious":  c.is_malicious,
                    "malware_family": c.malware_family,
                    "status":        c.status,
                    "created_at":    c.created_at.isoformat() if c.created_at else None,
                }
                for c in cases
            ],
            "total": len(cases),
        }
    except Exception as e:
        return {"cases": [], "error": str(e)}


# ── PowerShell deobfuscation ──────────────────────────────────────────────────

@router.post("/powershell")
async def deobfuscate_powershell(req: PowerShellRequest):
    """
    Deobfuscate a PowerShell script.
    Handles base64 encoding, char obfuscation, string reversal, IEX extraction.
    """
    if not req.script or not req.script.strip():
        raise HTTPException(status_code=400, detail="PowerShell script required")

    try:
        result = await _agent.deobfuscate_powershell(req.script)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Deobfuscation failed: {e}")


# ── Memory dump analysis ──────────────────────────────────────────────────────

@router.post("/memory")
async def analyze_memory_dump(
    file: UploadFile | None = File(None),
    dump_path: str | None   = Query(None),
    db: Session             = Depends(get_db),
):
    """
    Analyze a memory dump with Volatility3.
    Upload a dump file OR provide a server-side path via ?dump_path=...
    """
    if file:
        case_id   = str(uuid.uuid4())[:8]
        safe_name = "".join(c for c in (file.filename or "dump") if c.isalnum() or c in (".", "_", "-"))
        save_path = _UPLOAD_DIR / f"memdump_{case_id}_{safe_name}"
        content   = await file.read()
        save_path.write_bytes(content)
        dump_path = str(save_path)
    elif not dump_path:
        raise HTTPException(status_code=400, detail="Upload a dump file or provide dump_path")

    if not Path(dump_path).exists():
        raise HTTPException(status_code=404, detail="Memory dump file not found")

    try:
        result = await _agent.analyze_memory_dump(dump_path)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Memory analysis failed: {e}")


# ── IOCs ──────────────────────────────────────────────────────────────────────

@router.get("/iocs/{case_id}")
def get_iocs(case_id: str, db: Session = Depends(get_db)):
    """Get extracted IOCs for a forensics case."""
    try:
        from database.models import ForensicsCase
        case = db.query(ForensicsCase).filter_by(case_id=case_id).first()
        if not case:
            raise HTTPException(status_code=404, detail="Case not found")

        return {
            "case_id":  case_id,
            "filename": case.filename,
            "iocs":     json.loads(case.iocs or "{}"),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── STIX report ───────────────────────────────────────────────────────────────

@router.get("/stix/{case_id}")
async def get_stix_report(case_id: str, db: Session = Depends(get_db)):
    """Generate or retrieve STIX 2.1 report for a forensics case."""
    try:
        from database.models import ForensicsCase
        case = db.query(ForensicsCase).filter_by(case_id=case_id).first()
        if not case:
            raise HTTPException(status_code=404, detail="Case not found")

        # Return cached if available
        if case.stix_report:
            return json.loads(case.stix_report)

        # Generate STIX report
        analysis = json.loads(case.analysis_results or "{}")
        analysis["file_hash"]     = case.file_hash
        analysis["filename"]      = case.filename
        analysis["is_malicious"]  = case.is_malicious
        analysis["malware_family"] = case.malware_family
        analysis["iocs"]          = json.loads(case.iocs or "{}")

        stix = await _agent.generate_stix_report(analysis)

        # Cache it
        try:
            case.stix_report = json.dumps(stix)
            db.commit()
        except Exception:
            pass

        return stix
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
