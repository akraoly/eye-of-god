"""SQLAlchemy models — Air-Gap Exploitation (Bloc 4)."""
from database.models import Base
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float, Text
from datetime import datetime
import uuid as _uuid


class AirGapSession(Base):
    __tablename__ = "airgap_sessions"
    id          = Column(Integer, primary_key=True, autoincrement=True)
    session_id  = Column(String(36), unique=True, index=True, default=lambda: str(_uuid.uuid4()))
    technique   = Column(String(50), nullable=False)  # em|acoustic|sidechannel|thermal|usb
    attack_type = Column(String(80), nullable=True)
    target      = Column(String(200), nullable=True)
    success     = Column(Boolean, default=False)
    data_leaked = Column(Text, nullable=True)
    simulated   = Column(Boolean, default=True)
    created_at  = Column(DateTime, default=datetime.utcnow)


class AirGapExfil(Base):
    __tablename__ = "airgap_exfil"
    id          = Column(Integer, primary_key=True, autoincrement=True)
    exfil_id    = Column(String(36), unique=True, index=True, default=lambda: str(_uuid.uuid4()))
    session_id  = Column(String(36), nullable=True, index=True)
    channel     = Column(String(30), nullable=True)  # em|acoustic|thermal|optical|power
    bandwidth_bps = Column(Float, nullable=True)
    data_bytes  = Column(Integer, nullable=True)
    success     = Column(Boolean, default=False)
    simulated   = Column(Boolean, default=True)
    created_at  = Column(DateTime, default=datetime.utcnow)
