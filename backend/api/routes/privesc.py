"""
Routes /api/privesc — Privilege escalation enumeration and exploitation guide.
Linux (SUID, sudo, cron, capabilities) and Windows (AlwaysInstallElevated, service perms, tokens).
"""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database.db import get_db
from core.agents.privesc_agent import PrivEscAgent

router = APIRouter()
_agent = PrivEscAgent()


# ── Pydantic models ───────────────────────────────────────────────────────────

class LinuxScanRequest(BaseModel):
    target_ip:    str | None = None   # None = run locally
    local_output: str | None = None   # paste output from remote host


class WindowsScanRequest(BaseModel):
    target_ip:    str | None = None
    local_output: str | None = None   # paste output from whoami /priv, reg query, etc.


class LinpeasRequest(BaseModel):
    target_ip:  str       = "local"
    ssh_creds:  dict | None = None    # {host, user, password, key_file}


class WinpeasRequest(BaseModel):
    target_ip:  str       = ""
    smb_creds:  dict | None = None    # {user, password, domain}


# ── Linux ─────────────────────────────────────────────────────────────────────

@router.post("/linux")
async def linux_privesc(req: LinuxScanRequest, db: Session = Depends(get_db)):
    """
    Run Linux privilege escalation checks.
    Checks: SUID/SGID binaries, sudo -l, world-writable crons, capabilities,
    NFS root_squash, kernel version, PATH injection, writable service files.
    """
    try:
        result = await _agent.check_linux(
            target_ip=req.target_ip,
            local_output=req.local_output,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Linux scan failed: {e}")

    # Save to DB
    try:
        from database.models import PrivEscScan
        scan = PrivEscScan(
            scan_id=result["scan_id"],
            target=result.get("target", "local"),
            os_type="linux",
            findings=json.dumps(result.get("findings", [])),
            high_risk_count=result.get("high_risk_count", 0),
            medium_risk_count=result.get("medium_risk_count", 0),
            auto_exploitable=json.dumps(result.get("auto_exploitable", [])),
            status="completed",
        )
        db.add(scan)
        db.commit()
    except Exception:
        pass

    return result


# ── Windows ───────────────────────────────────────────────────────────────────

@router.post("/windows")
async def windows_privesc(req: WindowsScanRequest, db: Session = Depends(get_db)):
    """
    Run Windows privilege escalation checks.
    Checks: AlwaysInstallElevated, unquoted service paths, weak service perms,
    token impersonation, scheduled tasks, DLL hijacking, credentials in registry,
    AS-REP Roasting, Kerberoastable accounts.
    """
    try:
        result = await _agent.check_windows(
            target_ip=req.target_ip,
            local_output=req.local_output,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Windows scan failed: {e}")

    # Save to DB
    try:
        from database.models import PrivEscScan
        scan = PrivEscScan(
            scan_id=result["scan_id"],
            target=result.get("target", ""),
            os_type="windows",
            findings=json.dumps(result.get("findings", [])),
            high_risk_count=result.get("high_risk_count", 0),
            medium_risk_count=result.get("medium_risk_count", 0),
            auto_exploitable=json.dumps(result.get("auto_exploitable", [])),
            status="completed",
        )
        db.add(scan)
        db.commit()
    except Exception:
        pass

    return result


# ── GTFOBins lookup ───────────────────────────────────────────────────────────

@router.get("/gtfobins/{binary}")
async def gtfobins_lookup(binary: str):
    """
    GTFOBins lookup for a specific binary.
    Returns available exploit techniques (SUID, SUDO, capabilities, etc.).
    """
    if not binary or len(binary) > 100:
        raise HTTPException(status_code=400, detail="Invalid binary name")

    try:
        result = await _agent.get_gtfobins(binary)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"GTFOBins lookup failed: {e}")


# ── LinPEAS ───────────────────────────────────────────────────────────────────

@router.post("/linpeas")
async def run_linpeas(req: LinpeasRequest, db: Session = Depends(get_db)):
    """
    Download and run linpeas.sh on the target.
    Use target_ip='local' for local execution.
    Provide ssh_creds for remote execution (not yet implemented).
    """
    try:
        result = await _agent.run_linpeas(
            target_ip=req.target_ip,
            ssh_creds=req.ssh_creds,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LinPEAS failed: {e}")

    # Save findings to DB if completed
    if result.get("status") == "completed" and result.get("findings"):
        try:
            from database.models import PrivEscScan
            import uuid
            scan = PrivEscScan(
                scan_id=str(uuid.uuid4())[:8],
                target=req.target_ip or "local",
                os_type="linux",
                findings=json.dumps(result.get("findings", [])),
                high_risk_count=len([f for f in result.get("findings", []) if f.get("risk") in ("HIGH", "CRITICAL")]),
                medium_risk_count=len([f for f in result.get("findings", []) if f.get("risk") == "MEDIUM"]),
                auto_exploitable=json.dumps([]),
                status="completed",
            )
            db.add(scan)
            db.commit()
        except Exception:
            pass

    return result


# ── List scans ────────────────────────────────────────────────────────────────

@router.get("/scans")
def list_scans(
    limit:   int     = Query(20, le=100),
    os_type: str | None = Query(None, description="linux|windows"),
    db:      Session = Depends(get_db),
):
    """List all privilege escalation scans."""
    try:
        from database.models import PrivEscScan
        query = db.query(PrivEscScan).order_by(PrivEscScan.created_at.desc())
        if os_type:
            query = query.filter(PrivEscScan.os_type == os_type.lower())
        scans = query.limit(limit).all()

        return {
            "scans": [
                {
                    "scan_id":         s.scan_id,
                    "target":          s.target,
                    "os_type":         s.os_type,
                    "high_risk_count": s.high_risk_count,
                    "medium_risk_count": s.medium_risk_count,
                    "auto_exploitable_count": len(json.loads(s.auto_exploitable or "[]")),
                    "status":          s.status,
                    "created_at":      s.created_at.isoformat() if s.created_at else None,
                }
                for s in scans
            ],
            "total": len(scans),
        }
    except Exception as e:
        return {"scans": [], "error": str(e)}


# ── Scan details ──────────────────────────────────────────────────────────────

@router.get("/scan/{scan_id}")
def get_scan(scan_id: str, db: Session = Depends(get_db)):
    """Get detailed results for a specific privilege escalation scan."""
    try:
        from database.models import PrivEscScan
        scan = db.query(PrivEscScan).filter_by(scan_id=scan_id).first()
        if not scan:
            raise HTTPException(status_code=404, detail="Scan not found")

        return {
            "scan_id":         scan.scan_id,
            "target":          scan.target,
            "os_type":         scan.os_type,
            "findings":        json.loads(scan.findings or "[]"),
            "high_risk_count": scan.high_risk_count,
            "medium_risk_count": scan.medium_risk_count,
            "auto_exploitable": json.loads(scan.auto_exploitable or "[]"),
            "status":          scan.status,
            "created_at":      scan.created_at.isoformat() if scan.created_at else None,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
