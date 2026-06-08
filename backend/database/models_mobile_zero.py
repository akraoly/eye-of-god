"""SQLAlchemy models — Mobile Zero-Click (Bloc 1)."""
from database.models import Base
from sqlalchemy import Column, Integer, String, Boolean, DateTime, JSON, Text
from datetime import datetime
import uuid as _uuid


class MobileInfection(Base):
    __tablename__ = "mobile_infections"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    infection_id = Column(String(36), unique=True, index=True, default=lambda: str(_uuid.uuid4()))
    platform     = Column(String(10), nullable=False)      # ios | android
    target_phone = Column(String(50), nullable=True)
    vector       = Column(String(50), nullable=True)       # imessage | rcs | bluetooth
    cve          = Column(String(30), nullable=True)
    status       = Column(String(30), default="pending")   # pending | infected | active | lost | cleaned
    root_obtained = Column(Boolean, default=False)
    persistence  = Column(String(50), nullable=True)
    capabilities = Column(JSON, default=list)
    c2_address   = Column(String(100), nullable=True)
    last_seen    = Column(DateTime, nullable=True)
    simulated    = Column(Boolean, default=True)
    created_at   = Column(DateTime, default=datetime.utcnow)


class BasebandSession(Base):
    __tablename__ = "baseband_sessions"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    implant_id   = Column(String(36), unique=True, index=True, default=lambda: str(_uuid.uuid4()))
    target       = Column(String(100), nullable=True)      # MSISDN ou description
    chipset      = Column(String(100), nullable=True)
    cve          = Column(String(30), nullable=True)
    status       = Column(String(30), default="active")
    capabilities = Column(JSON, default=list)
    simulated    = Column(Boolean, default=True)
    created_at   = Column(DateTime, default=datetime.utcnow)


class BluetoothSession(Base):
    __tablename__ = "bluetooth_sessions"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    session_id   = Column(String(36), unique=True, index=True, default=lambda: str(_uuid.uuid4()))
    target_mac   = Column(String(17), nullable=True)
    exploit_name = Column(String(50), nullable=True)
    cve          = Column(String(30), nullable=True)
    result       = Column(String(50), nullable=True)      # rce_shell | crashed | failed
    simulated    = Column(Boolean, default=True)
    created_at   = Column(DateTime, default=datetime.utcnow)
