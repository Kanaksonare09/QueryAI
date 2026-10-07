"""
QueryAI — SQLAlchemy models for query history and conversations.
"""
import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import (
    String, Text, Integer, Float, Boolean,
    DateTime, ForeignKey, Enum as SAEnum, func, JSON
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
import enum

from app.models.base import Base, TimestampMixin


class QueryStatus(str, enum.Enum):
    PENDING    = "pending"
    RUNNING    = "running"
    SUCCESS    = "success"
    ERROR      = "error"
    CORRECTED  = "corrected"  # succeeded after auto-correction


class Conversation(Base, TimestampMixin):
    """Groups related follow-up queries together."""
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False, default="New Conversation")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    queries: Mapped[list["QueryHistory"]] = relationship(
        "QueryHistory", back_populates="conversation", cascade="all, delete-orphan",
        order_by="QueryHistory.created_at"
    )


class QueryHistory(Base, TimestampMixin):
    """Stores every query attempt with full pipeline metadata."""
    __tablename__ = "query_history"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    conversation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True
    )

    # User input
    question: Mapped[str] = mapped_column(Text, nullable=False)

    # Generated SQL
    generated_sql: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    corrected_sql: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    correction_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Execution
    status: Mapped[QueryStatus] = mapped_column(
        SAEnum(QueryStatus), default=QueryStatus.PENDING, nullable=False
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    execution_time_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    row_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # AI pipeline metadata (stored as JSON)
    relevant_tables: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    visualization_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    insight: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    conversation: Mapped[Optional["Conversation"]] = relationship(
        "Conversation", back_populates="queries"
    )
