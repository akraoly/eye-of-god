from sqlalchemy import Column, Integer, String, Text, DateTime, Float
from sqlalchemy.orm import declarative_base
from datetime import datetime

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
