"""
SQLAlchemy models for the BLE Scanner module.
"""
from database.models import Base
from sqlalchemy import Column, Integer, String, Boolean, DateTime, JSON, Text
from datetime import datetime
import uuid as _uuid


class BLEDevice(Base):
    __tablename__ = "ble_devices"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    ble_id       = Column(String(36), unique=True, index=True, default=lambda: str(_uuid.uuid4()))
    mac_address  = Column(String(17), unique=True, index=True, nullable=False)
    name         = Column(String(200), nullable=True)
    rssi         = Column(Integer, default=-70)
    manufacturer = Column(String(100), nullable=True)
    device_type  = Column(String(50), default="unknown")
    services     = Column(JSON, default=list)
    first_seen   = Column(DateTime, default=datetime.utcnow)
    last_seen    = Column(DateTime, default=datetime.utcnow)
    is_tracker   = Column(Boolean, default=False)
    tracker_type = Column(String(50), nullable=True)
    gatt_services= Column(JSON, default=list)
    vulns        = Column(JSON, default=list)
    simulated    = Column(Boolean, default=False)
    created_at   = Column(DateTime, default=datetime.utcnow)


class BLELog(Base):
    __tablename__ = "ble_logs"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    mac_address = Column(String(17), nullable=False, index=True)
    action      = Column(String(50), nullable=False)
    details     = Column(JSON, nullable=True)
    success     = Column(Boolean, default=True)
    timestamp   = Column(DateTime, default=datetime.utcnow, index=True)
