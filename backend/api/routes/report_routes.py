"""
Routes /api/reports/audit — Génération de rapports d'audit professionnels.
Préfixe "/reports/audit" dans le router principal.
"""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.auth.dependencies import get_current_user
from database.db import get_db
from database.models import AppUser
from services.reporting.report_generator_service import ReportGeneratorService
from services.reporting.collectors.evidence_collector import EvidenceCollector

router = APIRouter()

# Singletons
report_service = ReportGeneratorService()
evidence_collector = EvidenceCollector()


# ── Schémas Pydantic ──────────────────────────────────────────────────────────

class GenerateReportRequest(BaseModel):
    campaign_id: str = Field(..., min_length=1, max_length=100)
    format: str = Field("pdf", pattern="^(pdf|html|docx|markdown)$")
    options: dict = Field(default_factory=dict)
    title: str | None = Field(None, max_length=300)
    company_name: str | None = Field(None, max_length=200)


class CreateTemplateRequest(BaseModel):
    name: str = Field(..., max_length=200)
    company_name: str | None = None
    logo_url: str | None = None
    primary_color: str = "#1a237e"
    secondary_color: str = "#0d47a1"
    font_family: str = "Inter"
    sections: list = Field(default_factory=list)
    is_default: bool = False


class UpdateTemplateRequest(BaseModel):
    name: str | None = None
    company_name: str | None = None
    logo_url: str | None = None
    primary_color: str | None = None
    secondary_color: str | None = None
    font_family: str | None = None
    sections: list | None = None
    is_default: bool | None = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/generate")
async def generate_report(
    req: GenerateReportRequest,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    """Lance la génération asynchrone d'un rapport d'audit complet."""
    # Assurer les tables en DB
    try:
        from database.models_reporting import AuditReport, ReportTemplate
        from database.db import engine
        AuditReport.__table__.create(bind=engine, checkfirst=True)
        ReportTemplate.__table__.create(bind=engine, checkfirst=True)
    except Exception:
        pass

    result = await report_service.generate_report(
        campaign_id=req.campaign_id,
        format=req.format,
        options=req.options,
        title=req.title,
        db=db,
        generated_by=current_user.username,
    )

    if result.get("status") == "error":
        raise HTTPException(status_code=500, detail="Échec de la génération du rapport")

    return result


@router.get("/status/{report_id}")
async def get_report_status(
    report_id: str,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    """Retourne le statut et les métadonnées d'un rapport."""
    status = await report_service.get_report_status(report_id, db)
    if not status:
        raise HTTPException(status_code=404, detail="Rapport introuvable")
    return status


@router.get("/campaign/{campaign_id}")
async def list_campaign_reports(
    campaign_id: str,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    """Liste tous les rapports d'une campagne."""
    reports = await report_service.list_reports(campaign_id, db)
    return {"campaign_id": campaign_id, "reports": reports, "total": len(reports)}


@router.get("/download/{report_id}")
async def download_report(
    report_id: str,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    """Télécharge le fichier d'un rapport."""
    status = await report_service.get_report_status(report_id, db)
    if not status:
        raise HTTPException(status_code=404, detail="Rapport introuvable")

    file_path = status.get("file_path")
    if not file_path or not Path(file_path).exists():
        raise HTTPException(status_code=404, detail="Fichier de rapport introuvable")

    # Sécurité : vérifier que le chemin est dans le répertoire autorisé
    resolved = Path(file_path).resolve()
    allowed_dir = Path("./data/reports").resolve()
    if not str(resolved).startswith(str(allowed_dir)):
        raise HTTPException(status_code=403, detail="Accès refusé")

    fmt = status.get("format", "")
    media_types = {
        "pdf": "application/pdf",
        "html": "text/html",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "markdown": "text/markdown",
        "json": "application/json",
    }
    media_type = media_types.get(fmt, "application/octet-stream")

    return FileResponse(
        path=file_path,
        media_type=media_type,
        filename=Path(file_path).name,
    )


@router.delete("/{report_id}")
async def delete_report(
    report_id: str,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    """Supprime un rapport (fichier + entrée DB)."""
    deleted = await report_service.delete_report(report_id, db)
    if not deleted:
        raise HTTPException(status_code=404, detail="Rapport introuvable")
    return {"status": "deleted", "report_id": report_id}


@router.get("/preview/{campaign_id}")
async def preview_report(
    campaign_id: str,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    """Génère et retourne une prévisualisation HTML rapide (sans sauvegarde DB)."""
    from services.reporting.report_generator_service import _html_template
    from fastapi.responses import HTMLResponse
    import tempfile

    data = await evidence_collector.collect_all(campaign_id, db)
    data["_title"] = f"Prévisualisation — Campagne {campaign_id}"
    data["_summary"] = await report_service._build_summary(data)
    data["_risk_score"] = await report_service._calculate_risk_score(data)

    html_content = _html_template(data)
    return HTMLResponse(content=html_content, status_code=200)


# ── Templates ─────────────────────────────────────────────────────────────────

@router.post("/template")
async def create_template(
    req: CreateTemplateRequest,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    """Crée un template de rapport personnalisé."""
    try:
        from database.models_reporting import ReportTemplate
        from database.db import engine
        ReportTemplate.__table__.create(bind=engine, checkfirst=True)

        if req.is_default:
            # Désactiver l'ancien défaut
            db.query(ReportTemplate).filter(ReportTemplate.is_default == True).update(
                {"is_default": False}
            )

        tpl = ReportTemplate(
            name=req.name,
            company_name=req.company_name,
            logo_url=req.logo_url,
            primary_color=req.primary_color,
            secondary_color=req.secondary_color,
            font_family=req.font_family,
            sections=req.sections,
            is_default=req.is_default,
        )
        db.add(tpl)
        db.commit()
        db.refresh(tpl)
        return {
            "id": tpl.id,
            "name": tpl.name,
            "is_default": tpl.is_default,
            "created_at": tpl.created_at.isoformat() if tpl.created_at else None,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur création template: {e}")


@router.get("/template/default")
async def get_default_template(
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    """Retourne le template par défaut."""
    try:
        from database.models_reporting import ReportTemplate
        tpl = db.query(ReportTemplate).filter(ReportTemplate.is_default == True).first()
        if not tpl:
            return {
                "id": None,
                "name": "AEGIS AI Default",
                "company_name": "AEGIS AI",
                "primary_color": "#1a237e",
                "secondary_color": "#0d47a1",
                "font_family": "Inter",
                "sections": [],
                "is_default": True,
            }
        return {
            "id": tpl.id,
            "name": tpl.name,
            "company_name": tpl.company_name,
            "logo_url": tpl.logo_url,
            "primary_color": tpl.primary_color,
            "secondary_color": tpl.secondary_color,
            "font_family": tpl.font_family,
            "sections": tpl.sections or [],
            "is_default": tpl.is_default,
        }
    except Exception as e:
        return {"error": str(e)}


@router.put("/template/{template_id}")
async def update_template(
    template_id: int,
    req: UpdateTemplateRequest,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    """Met à jour un template de rapport."""
    try:
        from database.models_reporting import ReportTemplate
        tpl = db.query(ReportTemplate).filter(ReportTemplate.id == template_id).first()
        if not tpl:
            raise HTTPException(status_code=404, detail="Template introuvable")

        if req.is_default:
            db.query(ReportTemplate).filter(ReportTemplate.is_default == True).update(
                {"is_default": False}
            )

        for field, value in req.dict(exclude_none=True).items():
            setattr(tpl, field, value)

        db.commit()
        db.refresh(tpl)
        return {"id": tpl.id, "name": tpl.name, "status": "updated"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur mise à jour template: {e}")
