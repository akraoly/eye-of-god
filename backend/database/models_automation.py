"""SQLAlchemy models — Automation Stratégique (Bloc 7)."""
from database.models import Base
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float, Text
from datetime import datetime
import uuid as _uuid


class AutomationPlan(Base):
    __tablename__ = "automation_plans"
    id          = Column(Integer, primary_key=True, autoincrement=True)
    plan_id     = Column(String(36), unique=True, index=True, default=lambda: str(_uuid.uuid4()))
    plan_type   = Column(String(30), nullable=False)  # attack_plan|campaign|payload|opsec
    name        = Column(String(200), nullable=True)
    status      = Column(String(20), default="created")
    target      = Column(String(100), nullable=True)
    objective   = Column(String(50), nullable=True)
    risk_score  = Column(Float, nullable=True)
    simulated   = Column(Boolean, default=True)
    created_at  = Column(DateTime, default=datetime.utcnow)


class AutomationEvent(Base):
    __tablename__ = "automation_events"
    id          = Column(Integer, primary_key=True, autoincrement=True)
    event_id    = Column(String(36), unique=True, index=True, default=lambda: str(_uuid.uuid4()))
    plan_id     = Column(String(36), nullable=True)
    event_type  = Column(String(50), nullable=True)  # phase_advance|payload_gen|opsec_check
    details     = Column(Text, nullable=True)
    severity    = Column(String(20), default="info")
    created_at  = Column(DateTime, default=datetime.utcnow)
