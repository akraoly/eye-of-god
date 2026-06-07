"""
Routes /api/re — Reverse engineering with Ghidra and static analysis tools.
Upload binary, run analysis, retrieve decompiled code and findings.
"""
from __future__ import annotations

import json
import shutil
import tempfile
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from database.db import get_db
from core.agents.re_agent import REAgent

router = APIRouter()
_agent = REAgent()

_WORK_DIR = Path("./data/re_workspace")
_WORK_DIR.mkdir(parents=True, exist_ok=True)


# ── Upload and analyze ────────────────────────────────────────────────────────

@router.post("/analyze")
async def analyze_binary(
    file: UploadFile = File(...),
    db:   Session    = Depends(get_db),
):
    """
    Upload a binary file and start reverse engineering analysis.
    Returns analysis results including checksec, strings, symbols, and optional Ghidra decompilation.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename required")

    # Save uploaded file to workspace
    analysis_id = str(uuid.uuid4())[:8]
    safe_name   = "".join(c for c in file.filename if c.isalnum() or c in (".", "_", "-"))
    save_path   = _WORK_DIR / f"{analysis_id}_{safe_name}"

    try:
        content = await file.read()
        save_path.write_bytes(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"File save failed: {e}")

    # Run analysis
    try:
        result = await _agent.analyze_binary(str(save_path), binary_name=file.filename)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {e}")

    # Save to DB
    try:
        from database.models import REAnalysis
        sha256 = result.get("hashes", {}).get("sha256", "")
        rec = REAnalysis(
            analysis_id=analysis_id,
            binary_name=file.filename,
            binary_hash=sha256,
            file_type=result.get("file_type", ""),
            arch=result.get("arch", ""),
            protections=json.dumps(result.get("protections", {})),
            strings_count=result.get("strings_count", 0),
            functions_count=result.get("functions_count", 0),
            vulnerabilities=json.dumps(result.get("vulnerabilities", [])),
            claude_analysis=result.get("claude_analysis", {}).get("analysis", ""),
            ghidra_available=result.get("ghidra_available", False),
            decompiled_path=str(save_path),
            status="completed",
        )
        db.add(rec)
        db.commit()
    except Exception:
        pass  # DB save failure is non-fatal

    # Strip very large fields from response to keep it manageable
    response = {k: v for k, v in result.items() if k not in ("strings",)}
    response["analysis_id"]   = analysis_id
    response["strings_sample"] = result.get("strings", {}).get("interesting", [])[:20]
    response["ips_found"]      = result.get("strings", {}).get("ips", [])[:10]
    response["urls_found"]     = result.get("strings", {}).get("urls", [])[:10]

    return response


# ── Get analysis ──────────────────────────────────────────────────────────────

@router.get("/analysis/{analysis_id}")
def get_analysis(analysis_id: str, db: Session = Depends(get_db)):
    """Get full analysis results by analysis ID."""
    try:
        from database.models import REAnalysis
        rec = db.query(REAnalysis).filter_by(analysis_id=analysis_id).first()
        if not rec:
            raise HTTPException(status_code=404, detail="Analysis not found")

        return {
            "analysis_id":    rec.analysis_id,
            "binary_name":    rec.binary_name,
            "binary_hash":    rec.binary_hash,
            "file_type":      rec.file_type,
            "arch":           rec.arch,
            "protections":    json.loads(rec.protections or "{}"),
            "strings_count":  rec.strings_count,
            "functions_count": rec.functions_count,
            "vulnerabilities": json.loads(rec.vulnerabilities or "[]"),
            "claude_analysis": rec.claude_analysis,
            "ghidra_available": rec.ghidra_available,
            "status":         rec.status,
            "created_at":     rec.created_at.isoformat() if rec.created_at else None,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── List analyses ─────────────────────────────────────────────────────────────

@router.get("/analyses")
def list_analyses(
    limit: int     = Query(20, le=100),
    db:    Session = Depends(get_db),
):
    """List all reverse engineering analyses."""
    try:
        from database.models import REAnalysis
        records = (
            db.query(REAnalysis)
            .order_by(REAnalysis.created_at.desc())
            .limit(limit)
            .all()
        )
        return {
            "analyses": [
                {
                    "analysis_id":    r.analysis_id,
                    "binary_name":    r.binary_name,
                    "binary_hash":    r.binary_hash,
                    "file_type":      r.file_type,
                    "arch":           r.arch,
                    "vuln_count":     len(json.loads(r.vulnerabilities or "[]")),
                    "ghidra_available": r.ghidra_available,
                    "status":         r.status,
                    "created_at":     r.created_at.isoformat() if r.created_at else None,
                }
                for r in records
            ],
            "total": len(records),
        }
    except Exception as e:
        return {"analyses": [], "error": str(e)}


# ── Extract strings ───────────────────────────────────────────────────────────

@router.post("/strings/{analysis_id}")
async def extract_strings(analysis_id: str, db: Session = Depends(get_db)):
    """Extract and return strings from a previously analyzed binary."""
    try:
        from database.models import REAnalysis
        rec = db.query(REAnalysis).filter_by(analysis_id=analysis_id).first()
        if not rec:
            raise HTTPException(status_code=404, detail="Analysis not found")

        binary_path = rec.decompiled_path
        if not binary_path or not Path(binary_path).exists():
            raise HTTPException(status_code=404, detail="Binary file no longer available")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    try:
        strings = await _agent.extract_strings(binary_path)
        return {
            "analysis_id": analysis_id,
            "total":       len(strings.get("all", [])),
            "ips":         strings.get("ips", []),
            "urls":        strings.get("urls", []),
            "paths":       strings.get("paths", [])[:50],
            "interesting": strings.get("interesting", [])[:50],
            "sample":      strings.get("all", [])[:100],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"String extraction failed: {e}")


# ── Get decompiled code ───────────────────────────────────────────────────────

@router.get("/decompiled/{analysis_id}")
def get_decompiled(analysis_id: str, db: Session = Depends(get_db)):
    """Get decompiled code from Ghidra analysis."""
    try:
        from database.models import REAnalysis
        rec = db.query(REAnalysis).filter_by(analysis_id=analysis_id).first()
        if not rec:
            raise HTTPException(status_code=404, detail="Analysis not found")

        return {
            "analysis_id":    analysis_id,
            "binary_name":    rec.binary_name,
            "ghidra_available": rec.ghidra_available,
            "decompiled_path": rec.decompiled_path,
            "claude_analysis": rec.claude_analysis,
            "note": (
                "Ghidra decompilation available at decompiled_path"
                if rec.ghidra_available else
                "Ghidra not available — static analysis only"
            ),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
