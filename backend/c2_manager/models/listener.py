"""Listener model unifié."""
from __future__ import annotations
from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field
from c2_manager.models.config import C2Type


class Listener(BaseModel):
    id:              str
    name:            str
    c2_type:         C2Type
    bind_host:       str
    bind_port:       int
    protocol:        str              # http, https, dns, smb, tcp, wss…
    status:          str = "stopped"  # running, stopped, error
    payloads_served: int = 0
    created_at:      datetime = Field(default_factory=datetime.utcnow)
    config:          dict[str, Any] = Field(default_factory=dict)
