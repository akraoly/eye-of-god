"""SQLAlchemy models — OSINT Géopolitique (Bloc 6)."""
from database.models import Base
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float, Text
from datetime import datetime
import uuid as _uuid


class GeointSession(Base):
    __tablename__ = "geoint_sessions"
    id          = Column(Integer, primary_key=True, autoincrement=True)
    session_id  = Column(String(36), unique=True, index=True, default=lambda: str(_uuid.uuid4()))
    module      = Column(String(30), nullable=False)  # satellite|maritime|aviation|darkweb|crypto
    query       = Column(String(500), nullable=True)
    result_summary = Column(Text, nullable=True)
    risk_level  = Column(String(20), nullable=True)
    simulated   = Column(Boolean, default=True)
    created_at  = Column(DateTime, default=datetime.utcnow)


class GeointAlert(Base):
    __tablename__ = "geoint_alerts"
    id          = Column(Integer, primary_key=True, autoincrement=True)
    alert_id    = Column(String(36), unique=True, index=True, default=lambda: str(_uuid.uuid4()))
    module      = Column(String(30), nullable=True)
    severity    = Column(String(20), nullable=True)
    title       = Column(String(200), nullable=True)
    description = Column(Text, nullable=True)
    acknowledged = Column(Boolean, default=False)
    created_at  = Column(DateTime, default=datetime.utcnow)
