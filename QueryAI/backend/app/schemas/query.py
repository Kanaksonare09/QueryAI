"""
QueryAI — Pydantic schemas for API request/response models.
"""
from __future__ import annotations
import uuid
from typing import Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field


# ── Query Request ──────────────────────────────────────────────────────────────
class QueryRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=2000, description="Natural language question")
    conversation_id: Optional[uuid.UUID] = Field(None, description="Existing conversation to continue")
    max_rows: Optional[int] = Field(None, ge=1, le=5000, description="Override default row limit")

    model_config = {"json_schema_extra": {"example": {
        "question": "What are the top 5 products by revenue?",
        "conversation_id": None,
        "max_rows": 100
    }}}


class ValidateRequest(BaseModel):
    sql: str = Field(..., min_length=6, description="SQL to validate")


class ExplainRequest(BaseModel):
    sql: str = Field(..., min_length=6, description="SQL to explain")
    question: Optional[str] = Field(None, description="Original question for context")


class CorrectRequest(BaseModel):
    question: str
    failed_sql: str
    error_message: str


# ── Query Response ─────────────────────────────────────────────────────────────
class VisualizationConfig(BaseModel):
    type: str
    x_column: Optional[str] = None
    y_column: Optional[str] = None
    color_column: Optional[str] = None
    reason: Optional[str] = None


class QueryResultData(BaseModel):
    columns: list[str]
    rows: list[list[Any]]
    row_count: int
    truncated: bool = False
    execution_time_ms: float


class QueryResponse(BaseModel):
    query_id: uuid.UUID
    conversation_id: Optional[uuid.UUID] = None
    question: str
    generated_sql: str
    corrected_sql: Optional[str] = None
    correction_attempts: int = 0
    status: str
    result: Optional[QueryResultData] = None
    visualization: Optional[VisualizationConfig] = None
    insight: Optional[str] = None
    relevant_tables: list[str] = Field(default_factory=list)
    error_message: Optional[str] = None
    total_time_ms: float = 0.0
    intent: Optional[str] = None
    confidence_score: Optional[int] = None
    query_plan: Optional[dict[str, Any]] = None
    clarification_options: Optional[list[dict[str, str]]] = None
    optimization_suggestions: Optional[list[str]] = None


class ValidateResponse(BaseModel):
    is_valid: bool
    error: Optional[str] = None
    sql: Optional[str] = None


class ExplainResponse(BaseModel):
    explanation: str
    sql: str


class CorrectResponse(BaseModel):
    corrected_sql: str
    is_valid: bool
    error: Optional[str] = None
