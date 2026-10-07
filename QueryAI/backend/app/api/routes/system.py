"""QueryAI — Schema, History, and System API routes."""
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from app.database.connection import get_db, check_app_db, check_biz_db
from app.services.schema_history_service import (
    get_schema_overview, get_single_table_schema,
    list_history, get_history_item, list_conversations,
)
from app.ai.llm import check_ollama_status
from app.ai.rag import index_schema
from app.schemas.models import (
    SchemaResponse, TableInfo,
    HistoryListResponse, HistoryItemResponse, ConversationResponse,
    SystemStatusResponse,
)
from app.core.exceptions import SchemaNotFoundError, http_not_found, http_internal
from app.core.logging import get_logger

log = get_logger(__name__)

# ── Schema Router ──────────────────────────────────────────────────────────────
schema_router = APIRouter(prefix="/schema", tags=["Schema"])

@schema_router.get("", response_model=SchemaResponse, summary="Get full database schema")
async def get_schema():
    """Return all tables, columns, PKs, FKs, and row estimates."""
    try:
        return get_schema_overview()
    except Exception as exc:
        log.error("Schema fetch failed", error=str(exc))
        raise http_internal("Failed to retrieve schema. Check database connection.")


@schema_router.get("/{table_name}", response_model=TableInfo, summary="Get single table schema")
async def get_table(table_name: str):
    try:
        return get_single_table_schema(table_name)
    except SchemaNotFoundError as exc:
        raise http_not_found(exc.message)


@schema_router.post("/index", summary="Re-index schema into vector store")
async def reindex_schema():
    """Force re-indexing of schema metadata into ChromaDB."""
    try:
        count = index_schema(force=True)
        return {"message": "Schema indexed successfully", "documents": count}
    except Exception as exc:
        raise http_internal(f"Indexing failed: {str(exc)}")


# ── History Router ─────────────────────────────────────────────────────────────
history_router = APIRouter(prefix="/history", tags=["History"])

@history_router.get("", response_model=HistoryListResponse, summary="List query history")
async def get_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    conversation_id: Optional[uuid.UUID] = Query(None),
    db: Session = Depends(get_db),
):
    return list_history(db, page=page, page_size=page_size, conversation_id=conversation_id)


@history_router.get("/conversations", response_model=list[ConversationResponse], summary="List conversations")
async def get_conversations(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return list_conversations(db, page=page, page_size=page_size)


@history_router.get("/{item_id}", response_model=HistoryItemResponse, summary="Get history item")
async def get_history_detail(item_id: uuid.UUID, db: Session = Depends(get_db)):
    try:
        item = get_history_item(db, item_id)
        return HistoryItemResponse.model_validate(item)
    except SchemaNotFoundError:
        raise http_not_found(f"History item {item_id} not found.")


# ── System Router ──────────────────────────────────────────────────────────────
system_router = APIRouter(prefix="/system", tags=["System"])

@system_router.get("/status", response_model=SystemStatusResponse, summary="System health status")
async def system_status(db: Session = Depends(get_db)):
    """Check connectivity of all components."""
    import chromadb
    from app.core.config import settings

    ollama = check_ollama_status()
    app_db = check_app_db()
    biz_db = check_biz_db()

    # ChromaDB check
    try:
        client = chromadb.HttpClient(host=settings.chromadb_host, port=settings.chromadb_port)
        col = client.get_or_create_collection(settings.chromadb_collection)
        chroma_status = {"status": "connected", "documents": col.count()}
        schema_indexed = col.count() > 0
        schema_count = col.count()
    except Exception as exc:
        chroma_status = {"status": "disconnected", "error": str(exc)}
        schema_indexed = False
        schema_count = 0

    is_ollama_ok = ollama.get("status") == "running"
    is_chroma_ok = chroma_status.get("status") == "connected"
    is_biz_ok = biz_db.get("status") == "connected"

    return SystemStatusResponse(
        app_db=app_db,
        business_db=biz_db,
        ollama=ollama,
        chromadb=chroma_status,
        schema_indexed=schema_indexed,
        schema_table_count=schema_count,
        current_model=settings.ollama_llm_model,
        available_models=ollama.get("available_models", [settings.ollama_llm_model]),
        mysql_connected=is_biz_ok,
        ollama_connected=is_ollama_ok,
        chromadb_connected=is_chroma_ok,
    )
