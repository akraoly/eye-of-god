"""Implant / Agent / Beacon model unifié."""
from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel, Field
from c2_manager.models.config import C2Type


class Implant(BaseModel):
    id:           str
    name:         str
    c2_type:      C2Type
    listener_id:  str
    external_ip:  str = ""
    internal_ip:  str = ""
    hostname:     str = ""
    username:     str = ""
    os:           str = ""
    arch:         str = ""
    pid:          int = 0
    process_name: str = ""
    integrity:    str = "USER"   # SYSTEM, ADMIN, USER
    last_checkin: datetime = Field(default_factory=datetime.utcnow)
    first_seen:   datetime = Field(default_factory=datetime.utcnow)
    notes:        str | None = None
    active:       bool = True
    meta:         dict = Field(default_factory=dict)
