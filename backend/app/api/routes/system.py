"""
Database & System API routes — schema, SQL, status, models.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database.session import get_db, get_readonly_db, check_mysql_connection
from app.database.schema_inspector import SchemaInspector, validate_sql
from app.database.sql_executor import SQLExecutor
from app.schemas.schemas import TableSchema, SQLQueryRequest, SQLQueryResponse, SystemStatus, ModelConfig
from app.models.models import Document, DocumentStatus, Conversation
from app.services.ollama_service import get_ollama_service, set_active_model
from app.rag.vector_store import VectorStore, get_chroma_client
import structlog

logger = structlog.get_logger()

router = APIRouter(prefix="/system", tags=["System"])
db_router = APIRouter(prefix="/database", tags=["Database"])


# ─── System Status ────────────────────────────────────────────────────────────

@router.get("/status", response_model=SystemStatus)
async def get_system_status(db: Session = Depends(get_db)):
    """Get overall system health status."""
    mysql_info = check_mysql_connection()
    ollama_info = await get_ollama_service().health_check()

    # ChromaDB check
    chroma_status = "disconnected"
    total_chunks = 0
    try:
        vs = VectorStore()
        stats = vs.get_collection_stats()
        total_chunks = stats["total_chunks"]
        chroma_status = "connected"
    except Exception as e:
        chroma_status = f"error: {str(e)}"

    doc_count = db.query(Document).count()
    indexed_count = db.query(Document).filter(Document.status == DocumentStatus.indexed).count()
    conv_count = db.query(Conversation).count()

    active = get_ollama_service().model
    return SystemStatus(
        mysql_status=mysql_info.get("status", "disconnected"),
        mysql_database=mysql_info.get("database"),
        mysql_connected=mysql_info.get("status") == "connected",
        ollama_status=ollama_info.get("status", "unavailable"),
        ollama_connected=ollama_info.get("status") == "running",
        active_model=active,
        current_model=active,  # Sidebar alias
        available_models=ollama_info.get("available_models", []),
        chromadb_status=chroma_status,
        chromadb_connected=chroma_status == "connected",
        total_chunks=total_chunks,
        document_count=doc_count,
        indexed_document_count=indexed_count,
        conversation_count=conv_count,
    )


@router.post("/model")
@router.post("/models/switch", include_in_schema=False)  # frontend alias
async def update_model(config: ModelConfig):
    """Switch active Ollama model."""
    set_active_model(config.model)
    return {"message": f"Model switched to {config.model}", "active_model": config.model}


@router.get("/models")
async def list_models():
    """List available Ollama models."""
    ollama = get_ollama_service()
    models = await ollama.list_models()
    return {"models": models, "active": ollama.model}


# ─── Database Routes ──────────────────────────────────────────────────────────

@db_router.get("/schema", response_model=List[TableSchema])
def get_schema(db: Session = Depends(get_readonly_db)):
    """Return full database schema for user-facing tables."""
    inspector = SchemaInspector(db)
    schemas = inspector.get_full_schema()
    return schemas


@db_router.get("/tables")
def list_tables(db: Session = Depends(get_readonly_db)):
    """List all user-facing table names."""
    inspector = SchemaInspector(db)
    return {"tables": inspector.get_all_tables()}


@db_router.post("/query", response_model=SQLQueryResponse)
def execute_query(req: SQLQueryRequest, db: Session = Depends(get_readonly_db)):
    """Execute a raw SQL query (read-only, validated)."""
    is_safe, err = validate_sql(req.sql)
    if not is_safe:
        raise HTTPException(status_code=400, detail=f"SQL validation failed: {err}")

    executor = SQLExecutor(db)
    result = executor.execute(req.sql)

    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])

    return SQLQueryResponse(
        columns=result["columns"],
        rows=result["rows"],
        row_count=result["row_count"],
        truncated=result.get("truncated", False),
        execution_time_ms=result["execution_time_ms"],
        sql_executed=result["sql_executed"],
    )
