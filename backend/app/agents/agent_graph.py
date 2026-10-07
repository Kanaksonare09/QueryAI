"""
LangGraph Agent — orchestrates multi-source reasoning:
  - RAG (document retrieval)
  - Text-to-SQL (MySQL queries)
  - MCP tools
  - Cross-source synthesis

Design note: LangGraph node functions only receive `state`.
DB sessions are registered per-request in a context var so nodes
can still access them without changing the LangGraph call signature.
"""
import json
import re
import uuid
from contextvars import ContextVar
from typing import Any, Dict, List, Optional, TypedDict
from langgraph.graph import StateGraph, END
from app.services.ollama_service import get_ollama_service
from app.rag.vector_store import VectorStore, format_citations
from app.database.schema_inspector import SchemaInspector, validate_sql
from app.database.sql_executor import SQLExecutor
from app.config import settings
import structlog

logger = structlog.get_logger()

# ─── Context-var DB Session Registry ─────────────────────────────────────────
# chat.py sets these before invoking the graph so nodes can read them safely.
_readonly_session: ContextVar = ContextVar("readonly_session", default=None)


def set_agent_db_session(session) -> None:
    """Register a read-only SQLAlchemy session for the current async context."""
    _readonly_session.set(session)


def _get_db():
    """Retrieve the DB session registered for this request context."""
    return _readonly_session.get()


# ─── Agent State ─────────────────────────────────────────────────────────────

class AgentState(TypedDict):
    query: str
    conversation_history: List[Dict[str, str]]
    intent: Dict[str, Any]           # detected intent & required sources
    rag_results: List[Dict]          # retrieved document chunks
    sql_results: Dict[str, Any]      # SQL query + result
    synthesis: str                   # final answer text
    citations: List[Dict]            # source citations
    tools_used: List[str]            # tools invoked
    chart_data: Optional[Dict]       # visualization data
    error: Optional[str]


# ─── Prompt Templates ────────────────────────────────────────────────────────

INTENT_PROMPT = """You are an AI assistant routing system. Analyze the user query and determine which information sources are needed.

User Query: {query}

Conversation History (last 3 exchanges):
{history}

Available sources:
- "documents": The RAG document collection (PDFs, reports, notes, etc.)
- "database": MySQL database (structured sales/business data)  
- "both": Query needs both documents AND database

Respond in JSON only:
{{
  "primary_source": "documents" | "database" | "both",
  "document_filter": null | "specific document name hint",
  "needs_comparison": true | false,
  "needs_visualization": true | false,
  "reasoning": "brief explanation",
  "relevant_tables": ["table1", "table2"] | []
}}
"""

SQL_GEN_PROMPT = """You are an expert MySQL query generator. Generate a safe SELECT query.

User Question: {query}

Database Schema:
{schema}

Rules:
- Use ONLY SELECT statements
- Never use DROP, DELETE, UPDATE, INSERT, ALTER, TRUNCATE
- Always add meaningful aliases for readability
- Use JOINs where needed based on foreign keys
- Add LIMIT if the result could be large (default 100)
- Output ONLY the SQL query, nothing else

SQL:"""

RAG_SYNTHESIS_PROMPT = """You are an expert AI assistant. Answer the user's question based ONLY on the provided document excerpts.

User Question: {query}

Document Excerpts:
{context}

Instructions:
- Base your answer strictly on the document excerpts above
- Be specific about which document each piece of information comes from
- If information cannot be found in the excerpts, say so clearly
- Do not invent or assume facts not present in the documents
- Format your answer with clear structure using markdown

Answer:"""

MULTI_SOURCE_PROMPT = """You are an expert AI analyst. Answer the user's question by synthesizing information from multiple sources.

User Question: {query}

DOCUMENT EVIDENCE:
{doc_context}

DATABASE DATA:
{db_context}

Instructions:
- Synthesize findings from BOTH sources
- Explicitly compare/contrast when relevant
- Note any agreements or contradictions between sources
- Support all claims with specific evidence
- Format with headers and bullet points where helpful
- Be analytical and precise

Comprehensive Answer:"""


# ─── Agent Nodes ─────────────────────────────────────────────────────────────
# All nodes MUST have signature: async def name(state: AgentState) -> AgentState
# No extra kwargs — LangGraph does not forward them.

async def intent_classifier(state: AgentState) -> AgentState:
    """Classify user intent and determine required data sources."""
    ollama = get_ollama_service()
    history = state.get("conversation_history", [])[-6:]  # last 3 exchanges
    history_str = "\n".join(
        f"{m['role'].upper()}: {m['content'][:200]}" for m in history
    )

    prompt = INTENT_PROMPT.format(query=state["query"], history=history_str)

    try:
        response = await ollama.generate(prompt=prompt, temperature=0.0)
        # Extract JSON from response
        json_match = re.search(r"\{.*\}", response, re.DOTALL)
        if json_match:
            intent = json.loads(json_match.group())
        else:
            intent = {"primary_source": "documents", "reasoning": "fallback — no JSON found"}
    except Exception as e:
        logger.error("Intent classification failed", error=str(e))
        intent = {"primary_source": "documents", "reasoning": f"fallback — {e}"}

    return {**state, "intent": intent, "tools_used": []}


async def rag_retrieval(state: AgentState) -> AgentState:
    """Retrieve relevant document chunks from ChromaDB."""
    intent = state.get("intent", {})
    if intent.get("primary_source") not in ("documents", "both"):
        return state

    try:
        vs = VectorStore()
        hits = vs.search(query=state["query"], top_k=settings.top_k_retrieval)
        tools_used = state.get("tools_used", []) + ["RAG_retrieval"]
        return {**state, "rag_results": hits, "tools_used": tools_used}
    except Exception as e:
        logger.error("RAG retrieval failed", error=str(e))
        return {**state, "rag_results": [], "error": str(e)}


async def sql_generation_and_execution(state: AgentState) -> AgentState:
    """Generate SQL from natural language and execute it."""
    intent = state.get("intent", {})
    if intent.get("primary_source") not in ("database", "both"):
        return state

    db_session = _get_db()
    if db_session is None:
        logger.warning("sql_generation_and_execution: no DB session in context")
        return {**state, "sql_results": {"error": "No database session available"}}

    try:
        inspector = SchemaInspector(db_session)
        relevant_tables = intent.get("relevant_tables") or inspector.get_all_tables()
        schemas = inspector.get_relevant_schema(relevant_tables[:6])  # limit to 6 tables
        schema_str = inspector.schema_to_prompt_string(schemas)

        # Generate SQL
        ollama = get_ollama_service()
        sql_prompt = SQL_GEN_PROMPT.format(query=state["query"], schema=schema_str)
        raw_sql = await ollama.generate(prompt=sql_prompt, temperature=0.0)

        # Clean generated SQL — strip markdown fences and comments
        sql = raw_sql.strip()
        sql = re.sub(r"```sql|```", "", sql).strip()
        sql_lines = [ln for ln in sql.split("\n") if not ln.strip().startswith("--") and ln.strip()]
        sql = " ".join(sql_lines).strip()

        # Validate
        is_safe, err = validate_sql(sql)
        if not is_safe:
            return {**state, "sql_results": {"error": f"SQL validation failed: {err}", "generated_sql": sql}}

        # Execute
        executor = SQLExecutor(db_session)
        result = executor.execute(sql)
        result["generated_sql"] = sql

        # Infer chart — always try when we have tabular data
        chart_data = None
        if result.get("columns") and result.get("rows"):
            chart_type = executor.infer_chart_type(result["columns"], result["rows"])
            if chart_type:
                chart_data = {
                    "type": chart_type,
                    "columns": result["columns"],
                    "rows": result["rows"][:50],  # limit chart payload
                }

        tools_used = state.get("tools_used", []) + ["Text-to-SQL", "MySQL_execution"]
        return {
            **state,
            "sql_results": result,
            "chart_data": chart_data,
            "tools_used": tools_used,
        }
    except Exception as e:
        logger.error("SQL generation/execution failed", error=str(e))
        return {**state, "sql_results": {"error": str(e)}}


async def synthesize_answer(state: AgentState) -> AgentState:
    """Generate final answer by synthesizing all retrieved information."""
    ollama = get_ollama_service()
    intent = state.get("intent", {})
    source = intent.get("primary_source", "documents")

    rag_results = state.get("rag_results", [])
    sql_results = state.get("sql_results", {})

    try:
        if source == "both" and rag_results and not sql_results.get("error"):
            # Multi-source synthesis
            doc_context = _format_rag_context(rag_results)
            db_context = _format_sql_context(sql_results)
            prompt = MULTI_SOURCE_PROMPT.format(
                query=state["query"],
                doc_context=doc_context,
                db_context=db_context,
            )
        elif source == "database" or (source == "both" and not rag_results):
            # SQL-only answer
            db_context = _format_sql_context(sql_results)
            prompt = (
                f"Answer this database question based on the SQL results:\n\n"
                f"Question: {state['query']}\n\n"
                f"{db_context}\n\n"
                "Answer concisely with key insights:"
            )
        else:
            # RAG-only answer
            doc_context = _format_rag_context(rag_results)
            prompt = RAG_SYNTHESIS_PROMPT.format(
                query=state["query"],
                context=doc_context,
            )

        synthesis = await ollama.generate(prompt=prompt, temperature=0.1, max_tokens=3000)

        # Build citations
        citations: List[Dict] = []
        if rag_results:
            citations.extend(format_citations(rag_results))
        if sql_results.get("sql_executed"):
            citations.append({
                "type": "database",
                "sql": sql_results["sql_executed"],
                "row_count": sql_results.get("row_count", 0),
            })

        tools_used = state.get("tools_used", []) + ["LLM_synthesis"]
        return {**state, "synthesis": synthesis, "citations": citations, "tools_used": tools_used}

    except Exception as e:
        logger.error("Synthesis failed", error=str(e))
        return {**state, "synthesis": f"I encountered an error: {str(e)}", "error": str(e)}


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _format_rag_context(hits: List[Dict]) -> str:
    if not hits:
        return "No document excerpts found."
    parts = []
    for i, hit in enumerate(hits, 1):
        meta = hit.get("metadata", {})
        loc = f"Page {meta['page_number']}" if meta.get("page_number") else meta.get("section", "")
        loc_str = f" ({loc})" if loc else ""
        parts.append(f"[{i}] From: {meta.get('filename', 'unknown')}{loc_str}\n{hit['content']}")
    return "\n\n---\n\n".join(parts)


def _format_sql_context(sql_results: Dict) -> str:
    if not sql_results or sql_results.get("error"):
        return f"Database query failed: {sql_results.get('error', 'Unknown error')}"

    lines = [f"SQL Query:\n```sql\n{sql_results.get('generated_sql', '')}\n```"]
    cols = sql_results.get("columns", [])
    rows = sql_results.get("rows", [])

    if cols and rows:
        header = " | ".join(str(c) for c in cols)
        sep = " | ".join("---" for _ in cols)
        lines.append(f"\nResults ({sql_results.get('row_count', 0)} rows):")
        lines.append(f"| {header} |")
        lines.append(f"| {sep} |")
        for row in rows[:20]:  # show max 20 rows to LLM
            if isinstance(row, dict):
                vals = [str(row.get(c, "NULL")) for c in cols]
            else:
                vals = [str(v) if v is not None else "NULL" for v in row]
            lines.append("| " + " | ".join(vals) + " |")
    else:
        lines.append("No results returned.")

    return "\n".join(lines)


# ─── Graph Builder ───────────────────────────────────────────────────────────

def build_agent_graph():
    """Build and compile the LangGraph agent."""
    graph = StateGraph(AgentState)

    graph.add_node("intent_classifier", intent_classifier)
    graph.add_node("rag_retrieval", rag_retrieval)
    graph.add_node("sql_generation_and_execution", sql_generation_and_execution)
    graph.add_node("synthesize_answer", synthesize_answer)

    graph.set_entry_point("intent_classifier")

    graph.add_edge("intent_classifier", "rag_retrieval")
    graph.add_edge("rag_retrieval", "sql_generation_and_execution")
    graph.add_edge("sql_generation_and_execution", "synthesize_answer")
    graph.add_edge("synthesize_answer", END)

    return graph.compile()


_agent_graph = None


def get_agent_graph():
    global _agent_graph
    if _agent_graph is None:
        _agent_graph = build_agent_graph()
    return _agent_graph
