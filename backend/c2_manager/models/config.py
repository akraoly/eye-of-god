"""Modèles de configuration — C2Config, C2Type, C2Status."""
from __future__ import annotations
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class C2Type(str, Enum):
    COBALT_STRIKE = "cobalt_strike"
    METASPLOIT    = "metasploit"
    SLIVER        = "sliver"
    HAVOC         = "havoc"
    MYTHIC        = "mythic"
    COVENANT      = "covenant"
    EMPIRE        = "empire"
    POSHC2        = "poshc2"
    PUPY          = "pupy"
    KOADIC        = "koadic"
    ASYNCRAT      = "asyncrat"
    QUASAR        = "quasar"
    DEIMOS        = "deimos"
    VILLAIN       = "villain"
    REDGUARD      = "redguard"
    BRUTE_RATEL   = "brute_ratel"
    NIGHTHAWK     = "nighthawk"
    PWNDOC        = "pwndoc"
    FACTION       = "faction"


class C2Status(str, Enum):
    CONNECTED    = "connected"
    DISCONNECTED = "disconnected"
    CONNECTING   = "connecting"
    ERROR        = "error"
    UNKNOWN      = "unknown"


class C2Config(BaseModel):
    """Configuration unifiée pour tous les C2."""
    name:       str
    c2_type:    C2Type
    host:       str
    port:       int
    ssl:        bool       = False
    auth_token: str | None = None
    username:   str | None = None
    password:   str | None = None
    api_key:    str | None = None
    extra:      dict[str, Any] = Field(default_factory=dict)

    @property
    def base_url(self) -> str:
        scheme = "https" if self.ssl else "http"
        return f"{scheme}://{self.host}:{self.port}"

    @property
    def ws_url(self) -> str:
        scheme = "wss" if self.ssl else "ws"
        return f"{scheme}://{self.host}:{self.port}"
