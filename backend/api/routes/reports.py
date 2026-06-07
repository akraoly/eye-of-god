"""
Routes /api/reports — PDF and Markdown report generation.
Pentest, SOC incident, vulnerability, and weekly threat reports.
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database.db import get_db
from core.engines.report_engine import ReportEngine

router  = APIRouter()
_engine = ReportEngine()


# ── Pydantic models ───────────────────────────────────────────────────────────

class PentestReportRequest(BaseModel):
    job_id:            str | None = None
    target:            str        = "Unknown"
    findings:          list       = []
    steps:             list       = []
    raw_outputs:       dict       = {}
    remediations:      list       = []
    executive_summary: str        = ""
    scope:             str        = ""
    methodology:       str        = ""
    classification:    str        = "CONFIDENTIAL"
    format:            str        = "pdf"


class IncidentReportRequest(BaseModel):
    title:              str  = "Security Incident"
    description:        str  = ""
    severity:           str  = "HIGH"
    status:             str  = "INVESTIGATING"
    incident_uuid:      str  = ""
    timeline:           list = []
    iocs:               list = []
    remediation_steps:  list = []


class VulnerabilityReportRequest(BaseModel):
    target:     str  = "Unknown"
    cves:       list = []


class WeeklyReportRequest(BaseModel):
    week_start:  str  = ""
    summary:     str  = ""
    top_cves:    list = []
    exploits:    list = []
    total_cves:  int  = 0
    critical_cves: int = 0
    cisa_kev_new: int = 0


# ── Helper: save to DB ────────────────────────────────────────────────────────

def _save_report(db: Session, report_type: str, title: str, target: str,
                 filename: str, file_path: str, fmt: str = "pdf") -> dict:
    try:
        from database.models import GeneratedReport
        size = Path(file_path).stat().st_size if Path(file_path).exists() else 0
        report = GeneratedReport(
            report_type=report_type,
            title=title,
            target=target,
            filename=filename,
            format=fmt,
            file_path=file_path,
            file_size=size,
        )
        db.add(report)
        db.commit()
        db.refresh(report)
        return {
            "report_id": report.report_id,
            "filename":  filename,
            "file_size": size,
        }
    except Exception:
        return {"filename": filename}


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/pentest")
async def generate_pentest_report(req: PentestReportRequest, db: Session = Depends(get_db)):
    """Generate a full pentest report. Optionally fetch job data from job_id."""
    job_data = req.dict()

    if req.job_id:
        try:
            from database.models import PentestJob, PentestStep
            job = db.query(PentestJob).filter_by(job_id=req.job_id).first()
            if job:
                steps = db.query(PentestStep).filter_by(job_id=req.job_id).all() if hasattr(PentestStep, 'query') else []
                summary = json.loads(job.summary or "{}") if job.summary else {}
                job_data.update({
                    "target":            job.target,
                    "status":            job.status,
                    "executive_summary": summary.get("overview", ""),
                    "findings":          summary.get("cves", []),
                    "steps":             [
                        {
                            "name":     s.name,
                            "status":   s.status,
                            "output":   s.output or "",
                            "duration": s.duration or 0,
                        }
                        for s in steps
                    ],
                })
        except Exception:
            pass  # use req data as-is

    try:
        file_path = _engine.generate_pentest_report(job_data, fmt=req.format)
        filename  = Path(file_path).name
        meta = _save_report(
            db, "pentest",
            f"Pentest Report — {job_data.get('target', 'Unknown')}",
            job_data.get("target", "Unknown"),
            filename, file_path, req.format,
        )
        return {"status": "generated", "filename": filename, "download_url": f"/api/reports/download/{filename}", **meta}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Report generation failed: {e}")


@router.post("/incident")
async def generate_incident_report(req: IncidentReportRequest, db: Session = Depends(get_db)):
    """Generate a SOC incident report."""
    if not req.incident_uuid:
        req.incident_uuid = str(uuid.uuid4())[:8]

    try:
        file_path = _engine.generate_soc_incident_report(req.dict())
        filename  = Path(file_path).name
        meta = _save_report(
            db, "incident", req.title, "SOC", filename, file_path
        )
        return {"status": "generated", "filename": filename, "download_url": f"/api/reports/download/{filename}", **meta}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Report generation failed: {e}")


@router.post("/vulnerability")
async def generate_vulnerability_report(req: VulnerabilityReportRequest, db: Session = Depends(get_db)):
    """Generate a CVE/vulnerability assessment report."""
    try:
        file_path = _engine.generate_vulnerability_report(req.cves, req.target)
        filename  = Path(file_path).name
        meta = _save_report(
            db, "vulnerability",
            f"Vulnerability Report — {req.target}", req.target,
            filename, file_path,
        )
        return {"status": "generated", "filename": filename, "download_url": f"/api/reports/download/{filename}", **meta}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Report generation failed: {e}")


@router.get("/weekly")
async def generate_weekly_report(db: Session = Depends(get_db)):
    """Generate weekly threat intelligence report from stored feed data."""
    threat_data: dict = {
        "week_end":    datetime.utcnow().strftime("%Y-%m-%d"),
        "week_start":  "",
        "top_cves":    [],
        "exploits":    [],
        "total_cves":  0,
        "critical_cves": 0,
        "cisa_kev_new":  0,
    }

    try:
        from database.models import ThreatFeedEntry
        from datetime import timedelta
        week_ago = datetime.utcnow() - timedelta(days=7)
        entries  = (
            db.query(ThreatFeedEntry)
            .filter(ThreatFeedEntry.fetched_at >= week_ago)
            .order_by(ThreatFeedEntry.cvss_score.desc())
            .limit(100)
            .all()
        )
        threat_data["total_cves"]   = len([e for e in entries if e.entry_type == "cve"])
        threat_data["critical_cves"] = len([e for e in entries if e.severity == "CRITICAL"])
        threat_data["top_cves"] = [
            {
                "cve_id":      e.identifier,
                "description": e.description,
                "severity":    e.severity,
                "cvss_score":  e.cvss_score,
            }
            for e in entries if e.entry_type == "cve"
        ][:20]
        threat_data["exploits"] = [
            {"title": e.title, "published_at": e.published_at.isoformat() if e.published_at else ""}
            for e in entries if e.entry_type == "exploit"
        ][:20]
    except Exception:
        pass

    try:
        file_path = _engine.generate_weekly_threat_report(threat_data)
        filename  = Path(file_path).name
        meta = _save_report(
            db, "weekly_threat", "Weekly Threat Intelligence Report",
            "all", filename, file_path,
        )
        return {"status": "generated", "filename": filename, "download_url": f"/api/reports/download/{filename}", **meta}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Report generation failed: {e}")


@router.get("/list")
def list_reports(db: Session = Depends(get_db), limit: int = Query(50, le=200)):
    """List all generated reports."""
    try:
        from database.models import GeneratedReport
        reports = (
            db.query(GeneratedReport)
            .order_by(GeneratedReport.created_at.desc())
            .limit(limit)
            .all()
        )
        return {
            "reports": [
                {
                    "report_id":   r.report_id,
                    "report_type": r.report_type,
                    "title":       r.title,
                    "target":      r.target,
                    "filename":    r.filename,
                    "format":      r.format,
                    "file_size":   r.file_size,
                    "created_at":  r.created_at.isoformat() if r.created_at else None,
                    "download_url": f"/api/reports/download/{r.filename}",
                }
                for r in reports
            ],
            "total": len(reports),
        }
    except Exception as e:
        return {"reports": [], "error": str(e)}


@router.get("/download/{filename}")
def download_report(filename: str, db: Session = Depends(get_db)):
    """Download a generated report file."""
    # Security: no path traversal
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    report_dir = Path("./data/reports")
    file_path  = report_dir / filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Report file not found")

    media_type = "application/pdf" if filename.endswith(".pdf") else "text/markdown"
    return FileResponse(
        path=str(file_path),
        media_type=media_type,
        filename=filename,
    )
