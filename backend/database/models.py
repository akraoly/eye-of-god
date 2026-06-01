from sqlalchemy import Column, Integer, BigInteger, String, Text, DateTime, Float, Enum, JSON, Boolean
from sqlalchemy.orm import declarative_base
from datetime import datetime
import uuid as _uuid

Base = declarative_base()


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(100), index=True, default="default")
    user_message = Column(Text, nullable=False)
    assistant_response = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    context_used = Column(Integer, default=0)


class Memory(Base):
    __tablename__ = "memories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    memory_type = Column(String(20), nullable=False)  # 'user' | 'long'
    key = Column(String(200), nullable=False)
    value = Column(Text, nullable=False)
    importance = Column(Float, default=0.5)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class UserProfile(Base):
    __tablename__ = "user_profile"

    id = Column(Integer, primary_key=True, autoincrement=True)
    field = Column(String(200), nullable=False, unique=True)
    value = Column(Text, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow)


# ── Nouvelles tables v2 ───────────────────────────────────────────────────────

class KnowledgeEntry(Base):
    __tablename__ = "knowledge"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(500), nullable=False)
    content = Column(Text, nullable=False)
    summary = Column(Text, nullable=True)
    category = Column(String(100), nullable=False, default="general", index=True)
    source = Column(String(500), nullable=True)
    tags = Column(Text, nullable=True)           # JSON list as string
    importance = Column(Float, default=0.5)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class LearningEvent(Base):
    __tablename__ = "learning_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    topic = Column(String(500), nullable=False)
    source_url = Column(String(1000), nullable=True)
    source_type = Column(String(50), nullable=False, default="text")  # text | url | file
    summary = Column(Text, nullable=True)
    content = Column(Text, nullable=True)
    tags = Column(Text, nullable=True)           # JSON list as string
    importance = Column(Float, default=0.5)
    learned_at = Column(DateTime, default=datetime.utcnow)


class ActionLog(Base):
    __tablename__ = "action_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_name = Column(String(100), nullable=False, index=True)
    action_type = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    input_data = Column(Text, nullable=True)     # JSON string
    output_data = Column(Text, nullable=True)    # JSON string
    status = Column(String(20), nullable=False, default="success")  # success | error | skipped
    executed_at = Column(DateTime, default=datetime.utcnow, index=True)


class LifeGoal(Base):
    __tablename__ = "life_goals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(100), nullable=False, default="general")
    status = Column(String(50), nullable=False, default="active")  # active | paused | done | abandoned
    priority = Column(Integer, default=3)        # 1=critical, 2=high, 3=medium, 4=low
    progress = Column(Integer, default=0)        # 0-100 %
    deadline = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class LifeHabit(Base):
    __tablename__ = "life_habits"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(300), nullable=False)
    description = Column(Text, nullable=True)
    frequency = Column(String(50), nullable=False, default="daily")  # daily | weekly | monthly
    streak = Column(Integer, default=0)
    last_done = Column(DateTime, nullable=True)
    active = Column(Integer, default=1)          # 1 = active, 0 = inactive
    created_at = Column(DateTime, default=datetime.utcnow)


# ── Tables SOC (Phase 1) ────────────────────────────────────────────────────

class Alert(Base):
    """Alerte de sécurité — portée depuis AEGIS AI."""
    __tablename__ = "soc_alerts"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    alert_uuid    = Column(String(36), nullable=False, unique=True,
                           default=lambda: str(_uuid.uuid4()))
    timestamp     = Column(DateTime, default=datetime.utcnow, index=True)
    severity      = Column(String(10), nullable=False, index=True)   # LOW|MEDIUM|HIGH|CRITICAL
    category      = Column(String(50), nullable=False, index=True)   # PORT_SCAN|BRUTE_FORCE|…
    title         = Column(String(255), nullable=False)
    description   = Column(Text, nullable=True)
    source_ip     = Column(String(45), nullable=True, index=True)
    destination_ip= Column(String(45), nullable=True)
    affected_port = Column(Integer, nullable=True)
    protocol      = Column(String(10), nullable=True)
    raw_data      = Column(Text, nullable=True)                      # JSON string
    status        = Column(String(30), default="NEW", index=True)    # NEW|ACK|IN_PROGRESS|RESOLVED|FP
    mitre_tactic  = Column(String(10), nullable=True)               # TA0043…
    mitre_technique = Column(String(10), nullable=True)             # T1595…
    incident_id   = Column(Integer, nullable=True)
    source_engine = Column(String(50), default="manual")            # siem|ids|edr|manual
    created_at    = Column(DateTime, default=datetime.utcnow)


class Incident(Base):
    """Incident de sécurité."""
    __tablename__ = "soc_incidents"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    incident_uuid   = Column(String(36), nullable=False, unique=True,
                             default=lambda: str(_uuid.uuid4()))
    title           = Column(String(255), nullable=False)
    description     = Column(Text, nullable=True)
    severity        = Column(String(10), nullable=False, index=True)
    status          = Column(String(30), default="OPEN", index=True)  # OPEN|INVESTIGATING|CONTAINED|RESOLVED|CLOSED
    priority        = Column(Integer, default=3)                      # 1=critical → 4=low
    affected_systems= Column(Text, nullable=True)
    attack_vector   = Column(Text, nullable=True)
    impact_assessment=Column(Text, nullable=True)
    remediation_steps=Column(Text, nullable=True)
    resolution_notes= Column(Text, nullable=True)
    mitre_tactics   = Column(Text, nullable=True)                    # JSON list
    alert_ids       = Column(Text, nullable=True)                    # JSON list
    playbook_id     = Column(String(50), nullable=True)
    opened_at       = Column(DateTime, default=datetime.utcnow, index=True)
    resolved_at     = Column(DateTime, nullable=True)
    created_at      = Column(DateTime, default=datetime.utcnow)
    updated_at      = Column(DateTime, default=datetime.utcnow)


class SiemRule(Base):
    """Règle de corrélation SIEM (style Sigma)."""
    __tablename__ = "siem_rules"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    name         = Column(String(255), nullable=False, unique=True)
    description  = Column(Text, nullable=True)
    rule_type    = Column(String(30), nullable=False)               # THRESHOLD|SEQUENCE|AGGREGATION
    conditions   = Column(Text, nullable=False)                     # JSON config
    timewindow   = Column(Integer, default=300)                     # secondes
    threshold    = Column(Integer, default=1)
    severity     = Column(String(10), default="MEDIUM")
    category     = Column(String(50), default="OTHER")
    mitre_tactic = Column(String(10), nullable=True)
    mitre_technique = Column(String(10), nullable=True)
    enabled      = Column(Boolean, default=True)
    hit_count    = Column(Integer, default=0)
    last_hit     = Column(DateTime, nullable=True)
    created_at   = Column(DateTime, default=datetime.utcnow)


class SiemEvent(Base):
    """Événement ingéré par le SIEM."""
    __tablename__ = "siem_events"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    timestamp    = Column(DateTime, default=datetime.utcnow, index=True)
    event_type   = Column(String(50), nullable=False, index=True)   # PORT_SCAN|BRUTE_FORCE|…
    source       = Column(String(50), nullable=False)               # ids|edr|manual|agent
    src_ip       = Column(String(45), nullable=True, index=True)
    dst_ip       = Column(String(45), nullable=True)
    hostname     = Column(String(255), nullable=True)
    severity     = Column(String(10), default="LOW")
    data         = Column(Text, nullable=True)                      # JSON raw
    correlated   = Column(Boolean, default=False)
    alert_id     = Column(Integer, nullable=True)
