"""SQLAlchemy models — Zero-Day Industriel (Bloc 3)."""
from database.models import Base
from sqlalchemy import Column, Integer, String, Boolean, DateTime, JSON, Text, Float
from datetime import datetime
import uuid as _uuid


class FuzzJob(Base):
    __tablename__ = "fuzz_jobs"
    id         = Column(Integer, primary_key=True, autoincrement=True)
    job_id     = Column(String(36), unique=True, index=True, default=lambda: str(_uuid.uuid4()))
    fuzzer     = Column(String(30), nullable=False)  # kernel|browser|mobile|protocol
    target     = Column(String(100), nullable=True)
    status     = Column(String(20), default="running")
    crashes_found = Column(Integer, default=0)
    coverage_pct  = Column(Float, nullable=True)
    simulated  = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class ZeroDayCrash(Base):
    __tablename__ = "zeroday_crashes"
    id         = Column(Integer, primary_key=True, autoincrement=True)
    crash_id   = Column(String(36), unique=True, index=True, default=lambda: str(_uuid.uuid4()))
    job_id     = Column(String(36), nullable=True, index=True)
    fuzzer     = Column(String(30), nullable=True)
    crash_type = Column(String(50), nullable=True)
    severity   = Column(String(20), nullable=True)
    cvss       = Column(Float, nullable=True)
    exploitable = Column(Boolean, default=False)
    cve_candidate = Column(Boolean, default=False)
    simulated  = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class ZeroDayExploit(Base):
    __tablename__ = "zeroday_exploits"
    id          = Column(Integer, primary_key=True, autoincrement=True)
    exploit_id  = Column(String(36), unique=True, index=True, default=lambda: str(_uuid.uuid4()))
    crash_id    = Column(String(36), nullable=True, index=True)
    exploit_type = Column(String(50), nullable=True)
    platform    = Column(String(30), nullable=True)
    cve_candidate = Column(String(30), nullable=True)
    cvss_estimate = Column(Float, nullable=True)
    reliability = Column(String(10), nullable=True)
    exploit_path = Column(String(500), nullable=True)
    status      = Column(String(20), default="generated")
    tested      = Column(Boolean, default=False)
    simulated   = Column(Boolean, default=True)
    created_at  = Column(DateTime, default=datetime.utcnow)
