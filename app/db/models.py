"""CodexFlight Bot — SQLAlchemy ORM models."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


# ── Threads (Codex sessions) ─────────────────────────────


class Thread(Base):
    __tablename__ = "threads"

    id = Column(String, primary_key=True)  # Codex threadId
    chat_id = Column(Integer, nullable=False)  # Telegram chat_id
    name = Column(String)
    model = Column(String)
    model_provider = Column(String)
    sandbox = Column(String)
    cwd = Column(String)
    is_archived = Column(Boolean, default=False)
    turn_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=_utcnow)
    last_activity = Column(DateTime, default=_utcnow, onupdate=_utcnow)


# ── Bot state (key-value) ────────────────────────────────


class BotState(Base):
    __tablename__ = "bot_state"

    key = Column(String, primary_key=True)
    value = Column(String, nullable=False)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)


# ── Message log ──────────────────────────────────────────


class MessageLog(Base):
    __tablename__ = "message_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    thread_id = Column(String, ForeignKey="threads.id", nullable=False)
    telegram_message_id = Column(Integer)
    role = Column(String(20), nullable=False)  # user | assistant
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=_utcnow)

    __table_args__ = (
        Index("idx_messages_thread", "thread_id", "timestamp"),
    )


# ── Pending approvals ────────────────────────────────────


class PendingApproval(Base):
    __tablename__ = "pending_approvals"

    request_id = Column(String, primary_key=True)  # JSON-RPC request id
    chat_id = Column(Integer, nullable=False)
    message_id = Column(Integer, nullable=False)
    thread_id = Column(String, nullable=False)
    tool_data = Column(Text, nullable=False)  # JSON
    created_at = Column(DateTime, default=_utcnow)
    expires_at = Column(DateTime, nullable=False)
