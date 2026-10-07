"""QueryAI — Schema and History Pydantic models."""
from __future__ import annotations
import uuid
from typing import Any, Optional
from datetime import datetime
from pydantic import BaseModel


# ── Schema Models ──────────────────────────────────────────────────────────────
class ColumnInfo(BaseModel):
    name: str
    type: str
    nullable: bool
    default: Optional[str] = None
    max_length: Optional[int] = None
    precision: Optional[int] = None
    comment: Optional[str] = None


class ForeignKeyInfo(BaseModel):
    column: str
    references_table: str
    references_column: str


class TableInfo(BaseModel):
    name: str
    description: Optional[str] = None
    columns: list[ColumnInfo] = []
    primary_keys: list[str] = []
    foreign_keys: list[ForeignKeyInfo] = []
    row_estimate: Optional[int] = None


class SchemaResponse(BaseModel):
    schema_name: str
    tables: list[TableInfo]
    total_tables: int


# ── History Models ─────────────────────────────────────────────────────────────
class ConversationCreate(BaseModel):
    title: Optional[str] = "New Conversation"


class ConversationResponse(BaseModel):
    id: uuid.UUID
    title: str
    is_active: bool
    created_at: datetime
    query_count: int = 0

    model_config = {"from_attributes": True}


class HistoryItemResponse(BaseModel):
    id: uuid.UUID
    conversation_id: Optional[uuid.UUID] = None
    question: str
    generated_sql: Optional[str] = None
    corrected_sql: Optional[str] = None
    status: str
    error_message: Optional[str] = None
    execution_time_ms: Optional[float] = None
    row_count: Optional[int] = None
    visualization_type: Optional[str] = None
    insight: Optional[str] = None
    relevant_tables: Optional[list] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class HistoryListResponse(BaseModel):
    items: list[HistoryItemResponse]
    total: int
    page: int
    page_size: int


# ── Settings Models ────────────────────────────────────────────────────────────
class LLMSettings(BaseModel):
    base_url: str
    model: str
    embed_model: str
    status: str
    available_models: list[str] = []


class SystemStatusResponse(BaseModel):
    app_db: dict
    business_db: dict
    ollama: dict
    chromadb: dict
    schema_indexed: bool
    schema_table_count: int
    current_model: Optional[str] = None
    available_models: list[str] = []
    mysql_connected: bool = True
    ollama_connected: bool = True
    chromadb_connected: bool = True

