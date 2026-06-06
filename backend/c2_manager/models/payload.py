"""Payload config model."""
from __future__ import annotations
from typing import Any
from pydantic import BaseModel, Field
from c2_manager.models.config import C2Type


class PayloadConfig(BaseModel):
    name:        str
    c2_type:     C2Type
    listener_id: str
    format:      str  = "exe"      # exe, dll, ps1, py, elf, macho, shellcode, raw
    arch:        str  = "x64"      # x64, x86
    os:          str  = "windows"  # windows, linux, macos
    obfuscation: bool = True
    sleep:       int  = 60
    jitter:      int  = 10
    extra:       dict[str, Any] = Field(default_factory=dict)
