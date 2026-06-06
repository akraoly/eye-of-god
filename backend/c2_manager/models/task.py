"""Task / Command model."""
from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel, Field


class TaskStatus(str):
    QUEUED    = "queued"
    SENT      = "sent"
    RUNNING   = "running"
    COMPLETED = "completed"
    ERROR     = "error"
    TIMEOUT   = "timeout"


class Task(BaseModel):
    id:           str
    agent_id:     str
    c2_type:      str
    command:      str
    args:         list[str] = Field(default_factory=list)
    status:       str = "queued"
    result:       str | None = None
    error:        str | None = None
    created_at:   datetime = Field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None
