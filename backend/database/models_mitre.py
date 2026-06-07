from database.models import Base
from sqlalchemy import Column, Integer, String, Boolean, DateTime, JSON, Float, Text
from datetime import datetime
import uuid as _uuid


class MitreEvent(Base):
    __tablename__ = "mitre_events"
    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(String(36), unique=True, default=lambda: str(_uuid.uuid4()))
    campaign_id = Column(String(100), nullable=False, index=True)
    action_type = Column(String(100), nullable=False)
    technique_id = Column(String(20), nullable=False, index=True)
    tactic_id = Column(String(10), nullable=False, index=True)
    score = Column(Integer, default=1)
    success = Column(Boolean, default=True)
    details = Column(JSON, default=dict)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)


class MitreCampaignStats(Base):
    __tablename__ = "mitre_campaign_stats"
    id = Column(Integer, primary_key=True, autoincrement=True)
    campaign_id = Column(String(100), unique=True, nullable=False, index=True)
    total_techniques = Column(Integer, default=0)
    total_tactics = Column(Integer, default=0)
    total_score = Column(Integer, default=0)
    coverage = Column(Float, default=0.0)
    attack_graph = Column(JSON, default=dict)
    heatmap = Column(JSON, default=list)
    completed_phases = Column(JSON, default=list)
    updated_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
