"""
Modèles SQLAlchemy pour le module de génération de rapports d'audit.
"""
from database.models import Base
from sqlalchemy import Column, Integer, String, Boolean, DateTime, JSON, Float, Text
from datetime import datetime
import uuid as _uuid


class AuditReport(Base):
    __tablename__ = "audit_reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    report_id = Column(String(36), unique=True, index=True, default=lambda: str(_uuid.uuid4()))
    campaign_id = Column(String(100), nullable=False, index=True)
    title = Column(String(300), nullable=False)
    format = Column(String(20), nullable=False)
    file_path = Column(String(500), nullable=True)
    file_size = Column(Integer, nullable=True)
    pages_count = Column(Integer, nullable=True)
    status = Column(String(20), default="generating")
    options = Column(JSON, default=dict)
    summary = Column(Text, nullable=True)
    risk_score = Column(Float, nullable=True)
    generated_by = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class ReportTemplate(Base):
    __tablename__ = "report_templates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False)
    company_name = Column(String(200), nullable=True)
    logo_url = Column(String(500), nullable=True)
    primary_color = Column(String(20), default="#1a237e")
    secondary_color = Column(String(20), default="#0d47a1")
    font_family = Column(String(100), default="Inter")
    sections = Column(JSON, default=list)
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
