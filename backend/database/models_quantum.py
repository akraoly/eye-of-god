"""SQLAlchemy models — Quantum & Cryptographie (Bloc 8)."""
from database.models import Base
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float, Text
from datetime import datetime
import uuid as _uuid


class QuantumJob(Base):
    __tablename__ = "quantum_jobs"
    id          = Column(Integer, primary_key=True, autoincrement=True)
    job_id      = Column(String(36), unique=True, index=True, default=lambda: str(_uuid.uuid4()))
    job_type    = Column(String(30), nullable=False)  # shor|grover|pqc_audit|crypto_attack|key_gen|qkd
    algorithm   = Column(String(50), nullable=True)
    key_size    = Column(Integer, nullable=True)
    status      = Column(String(20), default="completed")
    result_summary = Column(Text, nullable=True)
    simulated   = Column(Boolean, default=True)
    created_at  = Column(DateTime, default=datetime.utcnow)


class CryptoKey(Base):
    __tablename__ = "crypto_keys"
    id          = Column(Integer, primary_key=True, autoincrement=True)
    key_id      = Column(String(36), unique=True, index=True, default=lambda: str(_uuid.uuid4()))
    label       = Column(String(200), nullable=True)
    algorithm   = Column(String(50), nullable=False)
    key_bits    = Column(Integer, nullable=True)
    quantum_safe = Column(Boolean, default=False)
    hsm_protected = Column(Boolean, default=True)
    expires_at  = Column(String(20), nullable=True)
    simulated   = Column(Boolean, default=True)
    created_at  = Column(DateTime, default=datetime.utcnow)
