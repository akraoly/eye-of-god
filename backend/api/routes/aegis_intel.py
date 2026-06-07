"""
Routes /api/aegis — Renseignement offensif AEGIS
CVE · Exploits · Cibles (pentest autorisé) · Journal · ATT&CK · Rapports
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel, validator
from sqlalchemy.orm import Session

from core.auth.dependencies import get_current_user
from database.db import get_db

router = APIRouter()


# ── Modèles Pydantic ──────────────────────────────────────────────────────────

class TargetCreate(BaseModel):
    name: str
    target_type: str   # domain | ip | org
    target_value: str
    authorization_confirmed: bool
    authorization_note: str = ""
    notes: str = ""
    tags: list[str] = []

    @validator("authorization_confirmed")
    def must_be_authorized(cls, v):
        if not v:
            raise ValueError(
                "authorization_confirmed doit être True. "
                "Confirmez disposer d'une autorisation écrite de pentest."
            )
        return v


class ATTACKEntryCreate(BaseModel):
    technique_id: str
    tactic: str
    technique_name: str
    level: str = "studied"   # studied|practiced|mastered
    source: str = ""
    cve_ids: list[str] = []
    notes: str = ""


class CVEAnnotate(BaseModel):
    notes: str
    status: Optional[str] = None


class IntelLogAnnotate(BaseModel):
    notes: str
    status: Optional[str] = None


class ReportRequest(BaseModel):
    hours: int = 24


class NaturalSearchRequest(BaseModel):
    query: str
    limit: int = 10


# ── CVE ───────────────────────────────────────────────────────────────────────

@router.get("/cves", dependencies=[Depends(get_current_user)])
def list_cves(
    severity: str = Query("", description="CRITICAL|HIGH|MEDIUM|LOW"),
    read: Optional[bool] = Query(None),
    starred: bool = Query(False),
    has_exploit: bool = Query(False),
    affects_project: bool = Query(False),
    source: str = Query(""),
    min_cvss: float = Query(0.0),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    db: Session = Depends(get_db),
):
    from database.models import AegisCVE
    q = db.query(AegisCVE)
    if severity:
        q = q.filter(AegisCVE.severity == severity.upper())
    if read is not None:
        q = q.filter(AegisCVE.read == read)
    if starred:
        q = q.filter(AegisCVE.starred == True)
    if has_exploit:
        q = q.filter(AegisCVE.has_exploit == True)
    if affects_project:
        q = q.filter(AegisCVE.affects_project == True)
    if source:
        q = q.filter(AegisCVE.source == source)
    if min_cvss > 0:
        q = q.filter(AegisCVE.cvss_score >= min_cvss)

    total = q.count()
    rows  = q.order_by(AegisCVE.ingested_at.desc()).offset(offset).limit(limit).all()

    return {
        "total": total,
        "cves": [_cve_dict(r) for r in rows],
    }


@router.get("/cves/stats", dependencies=[Depends(get_current_user)])
def cve_stats(db: Session = Depends(get_db)):
    from database.models import AegisCVE
    from sqlalchemy import func
    since24h = datetime.utcnow() - timedelta(hours=24)
    total = db.query(AegisCVE).count()
    unread = db.query(AegisCVE).filter(AegisCVE.read == False).count()
    critical = db.query(AegisCVE).filter(AegisCVE.severity == "CRITICAL").count()
    new_24h = db.query(AegisCVE).filter(AegisCVE.ingested_at >= since24h).count()
    with_exploit = db.query(AegisCVE).filter(AegisCVE.has_exploit == True).count()
    proj = db.query(AegisCVE).filter(AegisCVE.affects_project == True).count()
    return {
        "total": total, "unread": unread, "critical": critical,
        "new_24h": new_24h, "with_exploit": with_exploit, "affects_project": proj,
    }


@router.get("/cves/{cve_id}", dependencies=[Depends(get_current_user)])
def get_cve(cve_id: str, db: Session = Depends(get_db)):
    from database.models import AegisCVE, AegisExploit
    row = db.query(AegisCVE).filter(AegisCVE.cve_id == cve_id.upper()).first()
    if not row:
        raise HTTPException(404, f"CVE {cve_id} introuvable")
    exploits = db.query(AegisExploit).filter(AegisExploit.cve_id == cve_id.upper()).all()
    d = _cve_dict(row)
    d["exploits"] = [_exploit_dict(e) for e in exploits]
    return d


@router.post("/cves/{cve_id}/read", dependencies=[Depends(get_current_user)])
def mark_cve_read(cve_id: str, db: Session = Depends(get_db)):
    from database.models import AegisCVE
    row = db.query(AegisCVE).filter(AegisCVE.cve_id == cve_id.upper()).first()
    if row:
        row.read = True
        db.commit()
    return {"ok": True}


@router.patch("/cves/{cve_id}", dependencies=[Depends(get_current_user)])
def annotate_cve(cve_id: str, body: CVEAnnotate, db: Session = Depends(get_db)):
    from database.models import AegisCVE
    row = db.query(AegisCVE).filter(AegisCVE.cve_id == cve_id.upper()).first()
    if not row:
        raise HTTPException(404, "CVE introuvable")
    if body.notes is not None:
        row.notes = body.notes
    if body.status:
        row.status = body.status
    db.commit()
    return {"ok": True}


@router.post("/cves/refresh", dependencies=[Depends(get_current_user)])
async def refresh_cves(db: Session = Depends(get_db)):
    """Lance une collecte NVD immédiate."""
    from core.aegis.nvd_collector import fetch_nvd_recent, ingest_cves
    import os
    api_key = os.getenv("AEGIS_NVD_KEY", "")
    cves = fetch_nvd_recent(days=1, api_key=api_key)
    added, alerts = ingest_cves(db, cves)
    return {"added": added, "alerts": alerts}


# ── EXPLOITS ─────────────────────────────────────────────────────────────────

@router.get("/exploits", dependencies=[Depends(get_current_user)])
def list_exploits(
    cve_id: str = Query(""),
    reliability: str = Query(""),
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
):
    from database.models import AegisExploit
    q = db.query(AegisExploit)
    if cve_id:
        q = q.filter(AegisExploit.cve_id == cve_id.upper())
    if reliability:
        q = q.filter(AegisExploit.reliability == reliability)
    rows = q.order_by(AegisExploit.added_at.desc()).limit(limit).all()
    return {"exploits": [_exploit_dict(r) for r in rows], "total": q.count()}


@router.post("/exploits/{exploit_id}/analyze", dependencies=[Depends(get_current_user)])
async def analyze_exploit(exploit_id: str, db: Session = Depends(get_db)):
    from core.aegis.exploit_watcher import analyze_exploit_with_claude
    result = await analyze_exploit_with_claude(db, exploit_id)
    return {"analysis": result}


# ── CIBLES (pentest autorisé) ─────────────────────────────────────────────────

@router.get("/targets", dependencies=[Depends(get_current_user)])
def list_targets(db: Session = Depends(get_db)):
    from database.models import AegisTarget
    rows = db.query(AegisTarget).filter(AegisTarget.active == True).all()
    return {"targets": [_target_dict(r) for r in rows]}


@router.post("/targets", dependencies=[Depends(get_current_user)])
def add_target(body: TargetCreate, db: Session = Depends(get_db)):
    """
    Ajoute une cible de surveillance.
    REQUIS : authorization_confirmed=true (autorisation pentest écrite obligatoire).
    """
    from database.models import AegisTarget
    row = AegisTarget(
        name=body.name,
        target_type=body.target_type,
        target_value=body.target_value,
        authorization_confirmed=body.authorization_confirmed,
        authorization_note=body.authorization_note,
        notes=body.notes,
        tags=json.dumps(body.tags),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _target_dict(row)


@router.delete("/targets/{target_id}", dependencies=[Depends(get_current_user)])
def delete_target(target_id: str, db: Session = Depends(get_db)):
    from database.models import AegisTarget
    row = db.query(AegisTarget).filter(AegisTarget.target_id == target_id).first()
    if row:
        row.active = False
        db.commit()
    return {"ok": True}


@router.post("/targets/{target_id}/recon", dependencies=[Depends(get_current_user)])
async def run_recon(target_id: str, db: Session = Depends(get_db)):
    """
    Lance une reconnaissance passive (DNS + crt.sh) sur une cible autorisée.
    La cible doit avoir authorization_confirmed=True.
    """
    from core.aegis.target_sentinel import run_passive_recon
    result = run_passive_recon(db, target_id)
    if "error" in result:
        raise HTTPException(403, result["error"])
    return result


# ── JOURNAL INTEL ─────────────────────────────────────────────────────────────

@router.get("/intel-log", dependencies=[Depends(get_current_user)])
def list_intel_log(
    entry_type: str = Query(""),
    severity: str = Query(""),
    status: str = Query(""),
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
):
    from database.models import AegisIntelLog
    q = db.query(AegisIntelLog)
    if entry_type:
        q = q.filter(AegisIntelLog.entry_type == entry_type)
    if severity:
        q = q.filter(AegisIntelLog.severity == severity.upper())
    if status:
        q = q.filter(AegisIntelLog.status == status)
    rows = q.order_by(AegisIntelLog.created_at.desc()).limit(limit).all()
    return {"entries": [_intel_dict(r) for r in rows], "total": q.count()}


@router.patch("/intel-log/{entry_id}", dependencies=[Depends(get_current_user)])
def annotate_intel(entry_id: str, body: IntelLogAnnotate, db: Session = Depends(get_db)):
    from database.models import AegisIntelLog
    row = db.query(AegisIntelLog).filter(AegisIntelLog.entry_id == entry_id).first()
    if not row:
        raise HTTPException(404, "Entrée introuvable")
    if body.notes is not None:
        row.notes = body.notes
    if body.status:
        row.status = body.status
    db.commit()
    return {"ok": True}


# ── MATRICE ATT&CK PERSONNELLE ────────────────────────────────────────────────

@router.get("/attack-matrix", dependencies=[Depends(get_current_user)])
def get_attack_matrix(db: Session = Depends(get_db)):
    from database.models import AegisATTACKMap
    rows = db.query(AegisATTACKMap).order_by(AegisATTACKMap.tactic).all()
    by_tactic: dict[str, list] = {}
    for r in rows:
        by_tactic.setdefault(r.tactic, []).append({
            "technique_id":   r.technique_id,
            "technique_name": r.technique_name,
            "level":          r.level,
            "source":         r.source,
            "notes":          r.notes,
            "cve_ids":        json.loads(r.cve_ids or "[]"),
        })
    return {
        "techniques": len(rows),
        "by_tactic":  by_tactic,
        "coverage": {
            "studied":   sum(1 for r in rows if r.level == "studied"),
            "practiced": sum(1 for r in rows if r.level == "practiced"),
            "mastered":  sum(1 for r in rows if r.level == "mastered"),
        }
    }


@router.post("/attack-matrix", dependencies=[Depends(get_current_user)])
def add_attack_technique(body: ATTACKEntryCreate, db: Session = Depends(get_db)):
    from database.models import AegisATTACKMap
    existing = db.query(AegisATTACKMap).filter(
        AegisATTACKMap.technique_id == body.technique_id
    ).first()
    if existing:
        existing.level        = body.level
        existing.source       = body.source
        existing.notes        = body.notes
        existing.cve_ids      = json.dumps(body.cve_ids)
        existing.last_updated = datetime.utcnow()
        db.commit()
        return {"updated": True, "technique_id": body.technique_id}

    row = AegisATTACKMap(
        technique_id=body.technique_id,
        tactic=body.tactic,
        technique_name=body.technique_name,
        level=body.level,
        source=body.source,
        notes=body.notes,
        cve_ids=json.dumps(body.cve_ids),
    )
    db.add(row)
    db.commit()
    return {"created": True, "technique_id": body.technique_id}


# ── RAPPORTS ─────────────────────────────────────────────────────────────────

@router.get("/reports", dependencies=[Depends(get_current_user)])
def list_reports(limit: int = Query(20, le=100), db: Session = Depends(get_db)):
    from database.models import AegisReport
    rows = db.query(AegisReport).order_by(AegisReport.created_at.desc()).limit(limit).all()
    return {"reports": [_report_dict(r) for r in rows]}


@router.post("/reports/generate", dependencies=[Depends(get_current_user)])
async def generate_report(body: ReportRequest, db: Session = Depends(get_db)):
    from core.aegis.report_generator import generate_on_demand_report
    report = await generate_on_demand_report(db, hours=body.hours)
    return _report_dict(report)


@router.get("/reports/{report_id}", dependencies=[Depends(get_current_user)])
def get_report(report_id: str, db: Session = Depends(get_db)):
    from database.models import AegisReport
    row = db.query(AegisReport).filter(AegisReport.report_id == report_id).first()
    if not row:
        raise HTTPException(404, "Rapport introuvable")
    return _report_dict(row)


# ── RECOMMANDATION TACTIQUE ───────────────────────────────────────────────────

@router.get("/tactical/{cve_id}", dependencies=[Depends(get_current_user)])
def tactical_recommendation(cve_id: str, db: Session = Depends(get_db)):
    from database.models import AegisCVE, AegisExploit
    from core.aegis.report_generator import generate_tactical_recommendation
    cve = db.query(AegisCVE).filter(AegisCVE.cve_id == cve_id.upper()).first()
    if not cve:
        raise HTTPException(404, "CVE introuvable")
    exploits = db.query(AegisExploit).filter(AegisExploit.cve_id == cve_id.upper()).all()
    md = generate_tactical_recommendation(
        _cve_dict(cve),
        [_exploit_dict(e) for e in exploits],
    )
    return {"cve_id": cve_id, "markdown": md}


# ── RECHERCHE SÉMANTIQUE ──────────────────────────────────────────────────────

@router.post("/search", dependencies=[Depends(get_current_user)])
async def semantic_search(body: NaturalSearchRequest, db: Session = Depends(get_db)):
    """Recherche sémantique dans la base AEGIS via ChromaDB."""
    from core.memory.vector_store import VectorStore
    try:
        vs = VectorStore()
        results = vs.search(body.query, k=body.limit, filter_meta={"source": "aegis"})
        return {"results": results, "query": body.query}
    except Exception as e:
        return {"results": [], "error": str(e)}


# ── Helpers dict ──────────────────────────────────────────────────────────────

def _cve_dict(r) -> dict:
    return {
        "cve_id":          r.cve_id,
        "title":           r.title,
        "description":     r.description,
        "cvss_score":      r.cvss_score,
        "cvss_vector":     r.cvss_vector,
        "severity":        r.severity,
        "cwe_ids":         _j(r.cwe_ids),
        "affected_products": _j(r.affected_products),
        "references":      _j(r.references),
        "source":          r.source,
        "published_at":    r.published_at.isoformat() if r.published_at else None,
        "ingested_at":     r.ingested_at.isoformat() if r.ingested_at else None,
        "read":            r.read,
        "starred":         r.starred,
        "has_exploit":     r.has_exploit,
        "affects_project": r.affects_project,
        "status":          r.status,
        "ai_summary":      r.ai_summary,
        "notes":           r.notes,
    }


def _exploit_dict(r) -> dict:
    return {
        "exploit_id":   r.exploit_id,
        "cve_id":       r.cve_id,
        "repo_url":     r.repo_url,
        "repo_name":    r.repo_name,
        "repo_owner":   r.repo_owner,
        "description":  r.description,
        "language":     r.language,
        "stars":        r.stars,
        "tags":         _j(r.tags),
        "ai_analysis":  r.ai_analysis,
        "technique":    r.technique,
        "reliability":  r.reliability,
        "attack_vector":r.attack_vector,
        "added_at":     r.added_at.isoformat() if r.added_at else None,
        "status":       r.status,
        "notes":        r.notes,
    }


def _target_dict(r) -> dict:
    return {
        "target_id":              r.target_id,
        "name":                   r.name,
        "target_type":            r.target_type,
        "target_value":           r.target_value,
        "authorization_confirmed":r.authorization_confirmed,
        "authorization_note":     r.authorization_note,
        "notes":                  r.notes,
        "tags":                   _j(r.tags),
        "created_at":             r.created_at.isoformat() if r.created_at else None,
        "last_checked":           r.last_checked.isoformat() if r.last_checked else None,
        "subdomains":             _j(r.subdomains),
        "technologies":           _j(r.technologies),
        "dns_records":            _j(r.dns_records),
        "findings":               _j(r.findings),
        "active":                 r.active,
    }


def _intel_dict(r) -> dict:
    return {
        "entry_id":   r.entry_id,
        "entry_type": r.entry_type,
        "title":      r.title,
        "content":    r.content,
        "cve_id":     r.cve_id,
        "exploit_id": r.exploit_id,
        "target_id":  r.target_id,
        "tags":       _j(r.tags),
        "severity":   r.severity,
        "status":     r.status,
        "notes":      r.notes,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


def _report_dict(r) -> dict:
    return {
        "report_id":   r.report_id,
        "report_type": r.report_type,
        "title":       r.title,
        "content":     r.content,
        "stats":       _j(r.stats),
        "period_start":r.period_start.isoformat() if r.period_start else None,
        "period_end":  r.period_end.isoformat() if r.period_end else None,
        "created_at":  r.created_at.isoformat() if r.created_at else None,
    }


def _j(v) -> list | dict:
    if not v:
        return []
    try:
        return json.loads(v)
    except Exception:
        return []
