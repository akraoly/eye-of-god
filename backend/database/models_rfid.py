from database.models import Base
from sqlalchemy import Column, Integer, String, Boolean, DateTime, JSON, Text
from datetime import datetime
import uuid as _uuid


class RFIDCard(Base):
    __tablename__ = "rfid_cards"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    card_id       = Column(String(36), unique=True, index=True, default=lambda: str(_uuid.uuid4()))
    uid           = Column(String(100), unique=True, nullable=False, index=True)
    card_type     = Column(String(50), default="unknown")
    protocol      = Column(String(50), nullable=True)
    atqa          = Column(String(10), nullable=True)
    sak           = Column(String(10), nullable=True)
    size          = Column(Integer, nullable=True)
    data_hex      = Column(Text, nullable=True)
    blocks_count  = Column(Integer, nullable=True)
    keys_found    = Column(JSON, default=list)
    site_code     = Column(String(50), nullable=True)
    badge_number  = Column(String(50), nullable=True)
    facility_code = Column(String(50), nullable=True)
    vulnerabilities = Column(JSON, default=list)
    cloned        = Column(Boolean, default=False)
    clone_date    = Column(DateTime, nullable=True)
    simulated     = Column(Boolean, default=False)
    first_seen    = Column(DateTime, default=datetime.utcnow)
    created_at    = Column(DateTime, default=datetime.utcnow)


class RFIDLog(Base):
    __tablename__ = "rfid_logs"

    id        = Column(Integer, primary_key=True, autoincrement=True)
    action    = Column(String(50), nullable=False)
    card_uid  = Column(String(100), nullable=True, index=True)
    details   = Column(JSON, nullable=True)
    success   = Column(Boolean, default=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
