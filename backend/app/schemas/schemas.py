"""
Pydantic v2 schemas for API request/response validation.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field
from enum import Enum


# ─── Document Schemas ──────────────────────────────────────────────────────

class DocumentStatus(str, Enum):
    pending = "pending"
    processing = "processing"
    indexed = "indexed"
    failed = "failed"


class DocumentOut(BaseModel):
    id: str
    filename: str
    original_filename: str
    file_type: str
    file_size: int
    status: DocumentStatus
    chunk_count: int
    page_count: Optional[int]
    category: Optional[str]
    collection_id: Optional[str]
    uploaded_at: datetime
    indexed_at: Optional[datetime]
    error_message: Optional[str]

    class Config:
        from_attributes = True


class CollectionCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    color: str = "#6366f1"


class CollectionOut(BaseModel):
    id: str
    name: str
    description: Optional[str]
    color: str
    document_count: int = 0
    created_at: datetime

    class Config:
        from_attributes = True


# ─── Chat Schemas ──────────────────────────────────────────────────────────

class Citation(BaseModel):
    filename: Optional[str] = None
    file_type: Optional[str] = None
    document_id: Optional[str] = None
    page: Optional[str] = None
    section: Optional[str] = None
    score: Optional[float] = None
    type: str = "document"  # document | database
    sql: Optional[str] = None
    row_count: Optional[int] = None


class ChartData(BaseModel):
    type: str  # bar | line | pie | area
    columns: List[str]
    # rows can be list-of-lists OR list-of-dicts (agent returns dicts)
    rows: List[Any]


class ChatRequest(BaseModel):
    # Accept either 'message' (frontend) or 'query' (API docs) interchangeably
    message: Optional[str] = Field(None, min_length=1, max_length=10000)
    query: Optional[str] = Field(None, min_length=1, max_length=10000)
    conversation_id: Optional[str] = None
    collection_id: Optional[str] = None
    document_ids: Optional[List[str]] = None
    model: Optional[str] = None
    temperature: float = Field(0.1, ge=0.0, le=2.0)
    max_tokens: int = Field(4096, ge=100, le=32000)
    include_sql: bool = True
    include_charts: bool = True

    @property
    def resolved_query(self) -> str:
        """Return whichever of 'message' or 'query' was provided."""
        return (self.message or self.query or "").strip()


class ChatResponse(BaseModel):
    conversation_id: str
    message_id: str
    answer: str
    citations: List[Citation] = []
    sql_results: Optional[Dict[str, Any]] = None
    chart_data: Optional[ChartData] = None
    tools_used: List[str] = []
    intent: Optional[Dict[str, Any]] = None
    thinking: Optional[str] = None
    model: str
    processing_time_ms: float


class MessageOut(BaseModel):
    id: str
    role: str
    content: str
    sources: Optional[List[Citation]] = None
    sql_queries: Optional[List[str]] = None
    tools_used: Optional[List[str]] = None
    chart_data: Optional[Dict] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ConversationOut(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int = 0

    class Config:
        from_attributes = True


class ConversationDetail(ConversationOut):
    messages: List[MessageOut] = []


# ─── Database Schemas ──────────────────────────────────────────────────────

class TableColumn(BaseModel):
    name: str
    type: str
    nullable: bool
    key: str
    default: Optional[str]
    extra: str


class ForeignKey(BaseModel):
    column: str
    references_table: str
    references_column: str


class TableSchema(BaseModel):
    table_name: str
    columns: List[TableColumn]
    foreign_keys: List[ForeignKey]
    row_count: int


class SQLQueryRequest(BaseModel):
    sql: str = Field(..., min_length=1, max_length=5000)


class SQLQueryResponse(BaseModel):
    columns: List[str]
    rows: List[List[Any]]
    row_count: int
    truncated: bool = False
    execution_time_ms: float
    sql_executed: str
    error: Optional[str] = None


# ─── System Schemas ────────────────────────────────────────────────────────

class SystemStatus(BaseModel):
    mysql_status: str
    mysql_database: Optional[str]
    ollama_status: str
    active_model: str
    current_model: str  # alias used by Sidebar
    available_models: List[str]
    chromadb_status: str
    total_chunks: int
    document_count: int
    indexed_document_count: int
    conversation_count: int
    # Boolean flags for Sidebar status dots
    mysql_connected: bool = False
    ollama_connected: bool = False
    chromadb_connected: bool = False


class ModelConfig(BaseModel):
    model: str
    temperature: float = Field(0.1, ge=0.0, le=2.0)
    max_tokens: int = Field(4096, ge=100, le=32000)
