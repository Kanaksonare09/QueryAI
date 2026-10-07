"""QueryAI — Schema and History services."""
import uuid
from typing import Optional
from sqlalchemy.orm import Session

from app.database.schema_inspector import get_full_schema, get_table_schema
from app.schemas.models import (
    SchemaResponse, TableInfo, ColumnInfo, ForeignKeyInfo,
    HistoryListResponse, HistoryItemResponse, ConversationResponse,
)
from app.models.history import QueryHistory, Conversation
from app.core.exceptions import SchemaNotFoundError
from app.core.logging import get_logger

log = get_logger(__name__)


# ── Schema Service ─────────────────────────────────────────────────────────────

def get_schema_overview() -> SchemaResponse:
    """Return full schema as structured Pydantic models."""
    raw = get_full_schema()
    tables = []
    for tname, tmeta in raw["tables"].items():
        tables.append(TableInfo(
            name=tname,
            description=tmeta.get("description"),
            columns=[ColumnInfo(**c) for c in tmeta.get("columns", [])],
            primary_keys=tmeta.get("primary_keys", []),
            foreign_keys=[ForeignKeyInfo(**fk) for fk in tmeta.get("foreign_keys", [])],
            row_estimate=tmeta.get("row_estimate"),
        ))
    return SchemaResponse(
        schema_name=raw["schema"],
        tables=sorted(tables, key=lambda t: t.name),
        total_tables=len(tables),
    )


def get_single_table_schema(table_name: str) -> TableInfo:
    try:
        raw = get_table_schema(table_name)
    except KeyError:
        raise SchemaNotFoundError(f"Table '{table_name}' not found.")
    return TableInfo(
        name=table_name,
        description=raw.get("description"),
        columns=[ColumnInfo(**c) for c in raw.get("columns", [])],
        primary_keys=raw.get("primary_keys", []),
        foreign_keys=[ForeignKeyInfo(**fk) for fk in raw.get("foreign_keys", [])],
        row_estimate=raw.get("row_estimate"),
    )


# ── History Service ────────────────────────────────────────────────────────────

def list_history(
    db: Session,
    page: int = 1,
    page_size: int = 20,
    conversation_id: Optional[uuid.UUID] = None,
) -> HistoryListResponse:
    query = db.query(QueryHistory)
    if conversation_id:
        query = query.filter(QueryHistory.conversation_id == conversation_id)
    total = query.count()
    items = (
        query
        .order_by(QueryHistory.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return HistoryListResponse(
        items=[HistoryItemResponse.model_validate(h) for h in items],
        total=total,
        page=page,
        page_size=page_size,
    )


def get_history_item(db: Session, item_id: uuid.UUID) -> QueryHistory:
    item = db.query(QueryHistory).filter(QueryHistory.id == item_id).first()
    if not item:
        raise SchemaNotFoundError(f"History item '{item_id}' not found.")
    return item


def list_conversations(db: Session, page: int = 1, page_size: int = 20) -> list[ConversationResponse]:
    convs = (
        db.query(Conversation)
        .filter(Conversation.is_active == True)
        .order_by(Conversation.updated_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    result = []
    for c in convs:
        result.append(ConversationResponse(
            id=c.id,
            title=c.title,
            is_active=c.is_active,
            created_at=c.created_at,
            query_count=len(c.queries),
        ))
    return result
