"""DB models — Bloc 14: Guerre Spatiale & Orbital"""
from sqlalchemy import Column, Integer, String, Float, Boolean, Text, DateTime
from sqlalchemy.sql import func
from database.db import Base


class AsatMission(Base):
    __tablename__ = "asat_missions"
    id              = Column(Integer, primary_key=True)
    mission_id      = Column(String(64), unique=True, index=True)
    norad_id        = Column(Integer)
    sat_name        = Column(String(100))
    method          = Column(String(50))
    status          = Column(String(30))
    pk              = Column(Float)
    intercept_success = Column(Boolean, nullable=True)
    debris_objects  = Column(Integer, default=0)
    is_simulation   = Column(Boolean, default=True)
    planned_at      = Column(DateTime, server_default=func.now())


class GpsWarfareSession(Base):
    __tablename__ = "gps_warfare_sessions"
    id            = Column(Integer, primary_key=True)
    session_id    = Column(String(64), unique=True, index=True)
    session_type  = Column(String(20))  # spoof|jam|navden
    target_system = Column(String(20))
    technique     = Column(String(50))
    status        = Column(String(20))
    is_simulation = Column(Boolean, default=True)
    created_at    = Column(DateTime, server_default=func.now())


class SatJammingOp(Base):
    __tablename__ = "sat_jamming_ops"
    id            = Column(Integer, primary_key=True)
    op_id         = Column(String(64), unique=True, index=True)
    satellite     = Column(String(100))
    mode          = Column(String(50))
    power_kw      = Column(Float)
    status        = Column(String(20))
    is_simulation = Column(Boolean, default=True)
    created_at    = Column(DateTime, server_default=func.now())


class SsaTrack(Base):
    __tablename__ = "ssa_tracks"
    id            = Column(Integer, primary_key=True)
    norad_id      = Column(Integer, index=True)
    obj_name      = Column(String(100))
    obj_type      = Column(String(50))
    altitude_km   = Column(Float)
    maneuver_detected = Column(Boolean, default=False)
    is_simulation = Column(Boolean, default=True)
    tracked_at    = Column(DateTime, server_default=func.now())


class LeoDisruptionOp(Base):
    __tablename__ = "leo_disruption_ops"
    id            = Column(Integer, primary_key=True)
    op_id         = Column(String(64), unique=True, index=True)
    constellation = Column(String(50))
    attack_type   = Column(String(50))
    target_region = Column(String(100))
    terminals_affected = Column(Integer)
    status        = Column(String(20))
    is_simulation = Column(Boolean, default=True)
    created_at    = Column(DateTime, server_default=func.now())
