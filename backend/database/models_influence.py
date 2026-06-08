"""DB models — Bloc 9 Influence Stratégique & Guerre de l'Information."""
from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, Text
from sqlalchemy.sql import func
from database.db import Base


class InfluenceCampaign(Base):
    __tablename__ = "influence_campaigns"
    id          = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(String(36), unique=True, index=True)
    name        = Column(String(200), nullable=False)
    campaign_type = Column(String(30), nullable=False)  # io_ops|disinfo|psyop|monitor
    status      = Column(String(20), default="active")
    created_at  = Column(DateTime(timezone=True), server_default=func.now())


class InfluenceEvent(Base):
    __tablename__ = "influence_events"
    id          = Column(Integer, primary_key=True, index=True)
    event_id    = Column(String(36), unique=True, index=True)
    campaign_id = Column(String(36), nullable=True)
    event_type  = Column(String(50), nullable=True)
    severity    = Column(String(20), default="INFO")
    description = Column(Text, nullable=True)
    created_at  = Column(DateTime(timezone=True), server_default=func.now())
