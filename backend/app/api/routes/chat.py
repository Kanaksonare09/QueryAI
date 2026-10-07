"""
Chat API — main conversation endpoint with LangGraph agent orchestration.
"""
import time
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.schemas.schemas import ChatRequest, ChatResponse, Citation, ChartData
from app.agents.agent_graph import get_agent_graph, set_agent_db_session
from app.database.session import get_db, get_readonly_db
from app.models.models import Conversation, Message
from app.services.ollama_service import get_ollama_service, set_active_model
from app.config import settings
import structlog

logger = structlog.get_logger()

router = APIRouter(prefix="/chat", tags=["Chat"])


@router.post("/message", response_model=ChatResponse)
@router.post("", response_model=ChatResponse, include_in_schema=False)  # backwards-compat
async def chat(
    req: ChatRequest,
    db: Session = Depends(get_db),
    readonly_db: Session = Depends(get_readonly_db),
):
    """
    Main chat endpoint — routes query through LangGraph agent.
    Supports RAG, Text-to-SQL, and multi-source reasoning.
    """
    start = time.perf_counter()

    # Resolve the query text from either field name the caller used
    resolved_query = req.resolved_query
    if not resolved_query:
        raise HTTPException(
            status_code=422,
            detail="Either 'message' or 'query' must be provided.",
        )

    # Switch model if requested
    if req.model:
        set_active_model(req.model)

    ollama = get_ollama_service()

    # ── Conversation management ────────────────────────────────────────────────
    if req.conversation_id:
        conv = db.query(Conversation).filter(Conversation.id == req.conversation_id).first()
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")
    else:
        conv = Conversation(id=str(uuid.uuid4()), title=resolved_query[:100])
        db.add(conv)
        db.commit()

    # Load last 10 messages as conversation history
    history_messages = (
        db.query(Message)
        .filter(Message.conversation_id == conv.id)
        .order_by(Message.created_at.asc())
        .limit(10)
        .all()
    )
    history = [{"role": m.role, "content": m.content} for m in history_messages]

    # Persist user message immediately
    user_msg = Message(
        id=str(uuid.uuid4()),
        conversation_id=conv.id,
        role="user",
        content=resolved_query,
    )
    db.add(user_msg)
    db.commit()

    # ── LangGraph agent execution ─────────────────────────────────────────────
    # Register the read-only DB session so nodes can reach it via context var
    set_agent_db_session(readonly_db)

    agent = get_agent_graph()
    initial_state = {
        "query": resolved_query,
        "conversation_history": history,
        "intent": {},
        "rag_results": [],
        "sql_results": {},
        "synthesis": "",
        "citations": [],
        "tools_used": [],
        "chart_data": None,
        "error": None,
    }

    try:
        state = await agent.ainvoke(initial_state)
    except Exception as e:
        logger.error("Agent execution failed", error=str(e), exc_info=True)
        state = {
            **initial_state,
            "synthesis": (
                f"I encountered an error processing your request. "
                f"Please check that Ollama is running and the model is available. "
                f"Error: {str(e)}"
            ),
            "error": str(e),
        }

    elapsed_ms = round((time.perf_counter() - start) * 1000, 2)

    # ── Build response objects ─────────────────────────────────────────────────
    raw_citations = state.get("citations", [])
    citations = []
    for c in raw_citations:
        try:
            citations.append(Citation(**c))
        except Exception:
            pass  # skip malformed citations

    chart_data = None
    if state.get("chart_data"):
        try:
            chart_data = ChartData(**state["chart_data"])
        except Exception as e:
            logger.warning("ChartData parse failed", error=str(e))

    # Auto-generate conversation title from first exchange
    if len(history) == 0:
        short = resolved_query[:80]
        conv.title = short + ("..." if len(resolved_query) > 80 else "")
        db.commit()

    # Persist assistant message
    sql_q = state.get("sql_results", {}).get("generated_sql")
    assistant_msg = Message(
        id=str(uuid.uuid4()),
        conversation_id=conv.id,
        role="assistant",
        content=state["synthesis"],
        sources=[c.model_dump() for c in citations],
        sql_queries=[sql_q] if sql_q else None,
        tools_used=state.get("tools_used", []),
        chart_data=chart_data.model_dump() if chart_data else None,
    )
    db.add(assistant_msg)
    db.commit()

    return ChatResponse(
        conversation_id=conv.id,
        message_id=assistant_msg.id,
        answer=state["synthesis"],
        citations=citations,
        sql_results=(
            state.get("sql_results")
            if state.get("sql_results", {}).get("columns")
            else None
        ),
        chart_data=chart_data,
        tools_used=state.get("tools_used", []),
        intent=state.get("intent"),
        model=ollama.model,
        processing_time_ms=elapsed_ms,
    )
