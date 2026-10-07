"""
QueryAI — Chat and Frontend Integration Routes.
Provides full compatibility with the dashboard UI:
  - POST /chat/message  (natural-language analytics queries)
  - GET  /documents/     (document management stub)
"""
from typing import Optional, Any
from fastapi import APIRouter, Depends, HTTPException, Body
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.services.query_service import run_query_pipeline
from app.services.investigation_service import run_investigation_pipeline
from app.schemas.query import QueryRequest
from app.schemas.investigation import InvestigationRequest
from app.ai.intent_detector import detect_intent
from app.conversation.context_manager import get_conversation_memory
from app.core.logging import get_logger

log = get_logger(__name__)

chat_router = APIRouter(prefix="/chat", tags=["Chat"])
docs_router = APIRouter(prefix="/documents", tags=["Documents"])


class ChatMessageRequest(BaseModel):
    message: Optional[str] = None
    query: Optional[str] = None
    conversation_id: Optional[str] = None
    include_sql: bool = True
    include_charts: bool = True


@chat_router.post("/message")
@chat_router.post("")
async def handle_chat_message(
    payload: ChatMessageRequest,
    db: Session = Depends(get_db),
):
    """
    Handle natural language query from frontend chat interface.
    Executes full Text-to-SQL pipeline with schema RAG, validation, execution,
    and returns formatted chart data and insights.
    """
    question = (payload.message or payload.query or "").strip()
    if not question:
        raise HTTPException(status_code=422, detail="Message or query cannot be empty.")

    conv_id = None
    if payload.conversation_id:
        try:
            import uuid
            conv_id = uuid.UUID(payload.conversation_id)
        except Exception:
            conv_id = None

    # Detect intent first to route to investigation mode
    memory = get_conversation_memory(db, conv_id) if conv_id else None
    intent_res = detect_intent(question, memory)
    
    if intent_res.intent.value == "ROOT_CAUSE_ANALYSIS":
        inv_req = InvestigationRequest(question=question, conversation_id=conv_id)
        inv_res = run_investigation_pipeline(inv_req, db)
        
        return {
            "answer": inv_res.final_insight or "Investigation complete.",
            "citations": [],
            "sql_results": None,
            "chart_data": [],
            "chart_type": "table",
            "tools_used": ["investigation_planner", "schema_rag", "driver_analysis"],
            "intent": "ROOT_CAUSE_ANALYSIS",
            "processing_time_ms": 0.0,
            "conversation_id": str(inv_res.conversation_id),
            "confidence_score": 90,
            "query_plan": None,
            "clarification_options": None,
            "optimization_suggestions": None,
            "investigation": inv_res.model_dump()
        }

    req = QueryRequest(question=question, conversation_id=conv_id)
    res = run_query_pipeline(req, db)

    # ── Format Recharts chart_data ─────────────────────────────────────────────
    chart_data = []
    chart_type = "bar"
    if res.visualization:
        chart_type = res.visualization.type

    if res.result and res.result.rows and res.result.columns:
        cols = res.result.columns
        x_col = res.visualization.x_column if res.visualization and res.visualization.x_column in cols else cols[0]
        y_col = res.visualization.y_column if res.visualization and res.visualization.y_column in cols else (cols[1] if len(cols) > 1 else cols[0])
        
        x_idx = cols.index(x_col)
        y_idx = cols.index(y_col)

        for row in res.result.rows[:20]:
            try:
                name_val = str(row[x_idx]) if row[x_idx] is not None else "N/A"
                val = row[y_idx]
                if isinstance(val, (int, float)):
                    num_val = val
                else:
                    try:
                        num_val = float(str(val).replace("$", "").replace(",", ""))
                    except Exception:
                        num_val = 0
                chart_data.append({"name": name_val, y_col: num_val})
            except Exception:
                pass

    # ── Format SQL results ─────────────────────────────────────────────────────
    sql_results = None
    if res.result:
        rows_as_dicts = [
            dict(zip(res.result.columns, [str(v) if v is not None else "" for v in r]))
            for r in res.result.rows
        ]
        sql_results = {
            "sql_executed": res.generated_sql,
            "columns": res.result.columns,
            "rows": rows_as_dicts,
            "row_count": res.result.row_count,
            "execution_time_ms": res.result.execution_time_ms,
        }

    citations = [
        {"type": "database", "table": t, "filename": t}
        for t in (res.relevant_tables or [])
    ]

    return {
        "answer": res.insight or "Here are the query results:",
        "citations": citations,
        "sql_results": sql_results,
        "chart_data": chart_data,
        "chart_type": chart_type,
        "tools_used": ["schema_rag", "text_to_sql", "sql_validator"],
        "intent": res.intent or "sql_query",
        "processing_time_ms": res.result.execution_time_ms if res.result else 0.0,
        "conversation_id": str(res.conversation_id) if res.conversation_id else None,
        "confidence_score": res.confidence_score,
        "query_plan": res.query_plan,
        "clarification_options": res.clarification_options,
        "optimization_suggestions": res.optimization_suggestions,
    }


# ── Document stubs for sidebar ─────────────────────────────────────────────────
@docs_router.get("")
@docs_router.get("/")
async def list_documents():
    return {"documents": []}
