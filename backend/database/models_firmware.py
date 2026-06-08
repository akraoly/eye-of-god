"""
SQLAlchemy models — Firmware Implants (Bloc 2).
Table unifiée + tables spécialisées par type.
"""
from database.models import Base
from sqlalchemy import Column, Integer, String, Boolean, DateTime, JSON, Text, Float
from datetime import datetime
import uuid as _uuid


class FirmwareImplant(Base):
    """Table unifiée pour tous les implants firmware."""
    __tablename__ = "firmware_implants"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    implant_id    = Column(String(36), unique=True, index=True, default=lambda: str(_uuid.uuid4()))
    type          = Column(String(30), nullable=False, index=True)
    # type : uefi | hdd | smm | intel_me | nic | gpu | tpm | acpi
    target_id     = Column(String(200), nullable=True)   # hostname / IP / serial
    target_info   = Column(JSON, default=dict)           # vendor, model, version
    status        = Column(String(30), default="detected")
    # status : detected | dumped | infected | active | cleaned | failed
    payload_type  = Column(String(100), nullable=True)
    payload_hash  = Column(String(64), nullable=True)
    payload_path  = Column(String(500), nullable=True)
    capabilities  = Column(JSON, default=list)           # liste des capacités actives
    stealth_level = Column(Integer, default=5)           # 1-10
    persistence   = Column(String(50), default="firmware")
    notes         = Column(Text, nullable=True)
    simulated     = Column(Boolean, default=True)
    created_at    = Column(DateTime, default=datetime.utcnow)
    updated_at    = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class FirmwareDump(Base):
    """Dumps de firmware capturés."""
    __tablename__ = "firmware_dumps"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    dump_id       = Column(String(36), unique=True, index=True, default=lambda: str(_uuid.uuid4()))
    implant_id    = Column(String(36), nullable=True, index=True)
    type          = Column(String(30), nullable=False)
    target        = Column(String(200), nullable=True)
    vendor        = Column(String(100), nullable=True)
    version       = Column(String(100), nullable=True)
    file_path     = Column(String(500), nullable=True)
    file_size     = Column(Integer, nullable=True)
    sha256        = Column(String(64), nullable=True)
    raw_output    = Column(Text, nullable=True)
    simulated     = Column(Boolean, default=True)
    created_at    = Column(DateTime, default=datetime.utcnow)


class FirmwareOperation(Base):
    """Journal de toutes les opérations firmware."""
    __tablename__ = "firmware_operations"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    op_id         = Column(String(36), unique=True, index=True, default=lambda: str(_uuid.uuid4()))
    implant_id    = Column(String(36), nullable=True, index=True)
    type          = Column(String(30), nullable=False)
    action        = Column(String(100), nullable=False)
    target        = Column(String(200), nullable=True)
    status        = Column(String(20), default="done")
    result        = Column(JSON, default=dict)
    error         = Column(Text, nullable=True)
    simulated     = Column(Boolean, default=True)
    created_at    = Column(DateTime, default=datetime.utcnow)
