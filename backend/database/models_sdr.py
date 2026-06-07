from database.models import Base
from sqlalchemy import Column, Integer, String, Boolean, DateTime, JSON, Float, Text
from datetime import datetime
import uuid as _uuid


class SDRRecording(Base):
    __tablename__ = "sdr_recordings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    recording_id = Column(String(36), unique=True, index=True, default=lambda: str(_uuid.uuid4()))
    frequency_mhz = Column(Float, nullable=False)
    sample_rate = Column(Integer, default=2000000)
    gain = Column(Integer, default=40)
    modulation = Column(String(20), nullable=True)
    duration = Column(Integer, default=10)
    file_path = Column(String(500), nullable=True)
    file_size = Column(Integer, nullable=True)
    file_type = Column(String(20), default="wav")
    protocol = Column(String(50), nullable=True)
    decoded_content = Column(JSON, default=list)
    replay_count = Column(Integer, default=0)
    simulated = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class SDRDevice(Base):
    __tablename__ = "sdr_devices"

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_type = Column(String(50), nullable=False)
    serial = Column(String(100), unique=True, nullable=False)
    status = Column(String(20), default="connected")
    last_used = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
