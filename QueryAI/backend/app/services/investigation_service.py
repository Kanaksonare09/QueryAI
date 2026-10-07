"""
QueryAI — Core Investigation Service.
Orchestrates the root-cause analysis pipeline.
"""
import uuid
from sqlalchemy.orm import Session

from app.conversation.context_manager import get_conversation_memory
from app.ai.investigation_planner import create_investigation_plan
from app.ai.driver_analysis import analyze_drivers
from app.ai.llm import invoke_llm
from app.database.schema_inspector import get_full_schema
from app.database.sql_executor import execute_query
from app.security.sql_validator import validate_sql
from app.ai.rag import get_relevant_schema_ddl
from app.schemas.investigation import (
    InvestigationRequest, InvestigationResponse, EvidenceItem, RootCauseCandidateSchema
)
from app.models.history import Conversation
from app.core.logging import get_logger
import re

log = get_logger(__name__)

_SQL_FENCE_RE = re.compile(r"```(?:sql)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)
_SELECT_RE = re.compile(r"(SELECT\s.+)", re.DOTALL | re.IGNORECASE)

_INV_SQL_SYSTEM = """You are an expert MySQL analyst supporting a root-cause investigation.
Generate a single, safe, read-only SELECT query to answer the investigation sub-question.
OUTPUT ONLY the SQL. No explanations. No markdown. No preamble.
Use MySQL syntax only. Always include LIMIT 20 unless aggregating into a few rows.
If the question cannot be answered with the schema, output: -- CANNOT_ANSWER
"""

def _generate_investigation_sql(question: str, schema_ddl: str) -> str | None:
    """Generate SQL for an investigation sub-question, returns None if can't answer."""
    prompt = f"""DATABASE SCHEMA:
{schema_ddl}

INVESTIGATION QUESTION:
{question}

Generate the MySQL SELECT query:"""
    raw = invoke_llm(_INV_SQL_SYSTEM, prompt, temperature=0.0)
    
    if "CANNOT_ANSWER" in raw.upper():
        return None
    
    # Extract SQL
    m = _SQL_FENCE_RE.search(raw)
    if m:
        return m.group(1).strip()
    m = _SELECT_RE.search(raw)
    if m:
        return m.group(1).strip()
    return raw.strip() if raw.strip().upper().startswith("SELECT") else None


def run_investigation_pipeline(request: InvestigationRequest, db: Session) -> InvestigationResponse:
    """Executes the multi-step root cause investigation pipeline."""
    
    # 1. Conversation Setup
    conversation_id = request.conversation_id
    if not conversation_id:
        conv = Conversation(title=request.question[:80])
        db.add(conv)
        db.commit()
        db.refresh(conv)
        conversation_id = conv.id

    memory = get_conversation_memory(db, conversation_id)
    full_schema = get_full_schema()
    schema_tables = list(full_schema.get("tables", {}).keys())

    evidence_items = []
    baseline_summary_data = "No baseline data collected."
    candidates = []
    final_insight = ""
    error_msg = None
    status = "SUCCESS"
    baseline_summary = ""
    
    try:
        # 2. Planning
        plan = create_investigation_plan(request.question, schema_tables, memory)
        log.info("Investigation plan", plan=plan.model_dump())
        
        # 3. Get relevant schema DDL (use the metric + comparison as the query)
        schema_query = f"{plan.target_metric} {plan.comparison}"
        schema_ddl, _ = get_relevant_schema_ddl(schema_query, top_k=6)
        
        # 4. Baseline Query
        baseline_q = (
            f"Show {plan.target_metric} grouped by time period or overall total "
            f"to compare: {plan.comparison}. Show before and after values."
        )
        baseline_sql = _generate_investigation_sql(baseline_q, schema_ddl)
        
        if baseline_sql:
            try:
                baseline_sql = validate_sql(baseline_sql)
                result = execute_query(baseline_sql, max_rows=10)
                baseline_rows = [
                    dict(zip(result["columns"], [str(v) if v is not None else "" for v in r]))
                    for r in result["rows"]
                ]
                evidence_items.append(EvidenceItem(dimension="Baseline", sql=baseline_sql, results=baseline_rows))
                baseline_summary_data = f"Comparison ({plan.comparison}):\n{baseline_rows}"
            except Exception as e:
                log.warning("Baseline query failed", error=str(e))
                baseline_summary_data = f"Could not establish a clear baseline: {e}"
        else:
            baseline_summary_data = f"Could not generate baseline SQL for: {plan.target_metric} / {plan.comparison}"
                
        # 5. Dimension Investigation Queries
        evidence_data_parts = []
        for dim in plan.investigations[:4]:  # max 4 dimensions
            dim_q = (
                f"Break down {plan.target_metric} by {dim}. "
                f"Compare values for {plan.comparison}. "
                f"Order by the dimension that changed the most."
            )
            dim_sql = _generate_investigation_sql(dim_q, schema_ddl)
            
            if dim_sql:
                try:
                    dim_sql = validate_sql(dim_sql)
                    dim_result = execute_query(dim_sql, max_rows=15)
                    dim_rows = [
                        dict(zip(dim_result["columns"], [str(v) if v is not None else "" for v in r]))
                        for r in dim_result["rows"]
                    ]
                    evidence_items.append(EvidenceItem(dimension=dim, sql=dim_sql, results=dim_rows))
                    evidence_data_parts.append(f"By {dim}:\n{dim_rows}")
                except Exception as e:
                    log.warning(f"Dimension query failed for {dim}", error=str(e))
            else:
                log.debug(f"Skipping dimension {dim} — cannot generate SQL")

        evidence_data_str = "\n\n".join(evidence_data_parts) if evidence_data_parts else "No dimension breakdowns available."
        
        # 6. Driver Analysis
        report = analyze_drivers(baseline_summary_data, evidence_data_str)
        baseline_summary = report.baseline_summary
        final_insight = report.final_insight

        for c in report.candidates:
            candidates.append(RootCauseCandidateSchema(
                driver_name=c.driver_name,
                contribution_percent=c.contribution_percent,
                confidence=c.confidence,
                explanation=c.explanation,
            ))
        
        if not candidates and not evidence_items:
            status = "SUCCESS"
            final_insight = (
                "I couldn't determine a reliable driver from the available data. "
                "The schema may not contain enough historical data to make a comparison."
            )

    except Exception as e:
        status = "ERROR"
        error_msg = str(e)
        log.exception("Investigation failed")

    return InvestigationResponse(
        investigation_id=uuid.uuid4(),
        conversation_id=conversation_id,
        question=request.question,
        baseline_summary=baseline_summary,
        candidates=candidates,
        final_insight=final_insight,
        evidence=evidence_items,
        status=status,
        error_message=error_msg,
    )
