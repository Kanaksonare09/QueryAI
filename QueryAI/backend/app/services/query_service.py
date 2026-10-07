"""
QueryAI — Core Query Pipeline Service.

Full V2 pipeline:
  1. Conversation memory extraction
  2. Intent detection
  3. Ambiguity detection
  4. Query Planning (LLM)
  5. Hybrid RAG schema retrieval
  6. SQL generation (LLM)
  7. SQL security validation
  8. SQL execution & auto-correction loop
  9. Confidence scoring
  10. Query optimization (EXPLAIN)
  11. Visualization recommendation
  12. Natural-language insight generation
"""
import time
import uuid
from typing import Optional
from sqlalchemy.orm import Session

from app.conversation.context_manager import get_conversation_memory, get_context_string, invalidate_memory_cache
from app.ai.intent_detector import detect_intent, Intent
from app.ai.ambiguity_detector import detect_ambiguity
from app.ai.query_planner import create_query_plan, plan_to_prompt_context
from app.ai.confidence import calculate_confidence
from app.ai.sql_generator import generate_sql
from app.ai.sql_corrector import correct_sql
from app.ai.insights import recommend_visualization, summarize_results
from app.database.sql_executor import execute_query
from app.database.schema_inspector import get_full_schema
from app.database.optimizer import optimize_query
from app.security.sql_validator import validate_sql
from app.models.history import QueryHistory, QueryStatus, Conversation
from app.schemas.query import QueryRequest, QueryResponse, QueryResultData, VisualizationConfig
from app.core.config import settings
from app.core.exceptions import (
    SQLValidationError, SQLExecutionError, SQLCorrectionFailedError, LLMError
)
from app.core.logging import get_logger

log = get_logger(__name__)


def _ensure_conversation(db: Session, conversation_id: Optional[uuid.UUID]) -> uuid.UUID:
    if conversation_id:
        conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
        if conv:
            return conv.id

    conv = Conversation(title="New Conversation")
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv.id


def run_query_pipeline(request: QueryRequest, db: Session) -> QueryResponse:
    pipeline_start = time.perf_counter()
    conversation_id = _ensure_conversation(db, request.conversation_id)

    history = QueryHistory(
        conversation_id=conversation_id,
        question=request.question,
        status=QueryStatus.PENDING,
    )
    db.add(history)
    db.commit()
    db.refresh(history)

    generated_sql = None
    corrected_sql = None
    correction_attempts = 0
    result_data = None
    viz_config = None
    insight = None
    error_message = None
    relevant_tables = []
    final_status = QueryStatus.ERROR
    intent_str = None
    confidence_score = None
    query_plan_dict = None
    clarification_options = None
    optimization_suggestions = None

    try:
        history.status = QueryStatus.RUNNING
        db.commit()

        # ── Step 1: Conversation Context ───────────────────────────────────────
        memory = get_conversation_memory(db, conversation_id)
        ctx = memory.to_context_string()

        # ── Step 2: Intent Detection ───────────────────────────────────────────
        intent_res = detect_intent(request.question, memory)
        intent_str = intent_res.intent.value
        log.info("Intent detected", intent=intent_str, confidence=intent_res.confidence)

        if intent_res.intent == Intent.GREETING:
            final_status = QueryStatus.SUCCESS
            insight = "Hello! How can I help you explore your data today?"
            return _build_response(locals())

        # ── Step 3: Ambiguity Detection ────────────────────────────────────────
        ambiguity_res = detect_ambiguity(request.question, memory)
        if ambiguity_res.is_ambiguous:
            final_status = QueryStatus.SUCCESS
            insight = ambiguity_res.message
            clarification_options = [opt.model_dump() for opt in ambiguity_res.options]
            intent_str = Intent.AMBIGUOUS_QUERY.value
            return _build_response(locals())

        # ── Step 4: Query Planning ─────────────────────────────────────────────
        full_schema = get_full_schema()
        all_tables = list(full_schema.get("tables", {}).keys())
        query_plan = create_query_plan(request.question, all_tables, memory)
        query_plan_dict = query_plan.model_dump()
        plan_ctx = plan_to_prompt_context(query_plan)

        # ── Step 5 & 6: RAG + SQL Generation ───────────────────────────────────
        generated_sql, relevant_tables = generate_sql(
            question=request.question,
            conversation_context=ctx,
            query_plan_str=plan_ctx,
        )
        history.generated_sql = generated_sql
        history.relevant_tables = relevant_tables
        db.commit()

        # ── Step 7: SQL Validation ─────────────────────────────────────────────
        clean_sql = validate_sql(generated_sql)
        active_sql = clean_sql
        security_passed = True

        # ── Step 8: Execution & Auto-correction ────────────────────────────────
        execution_result = None
        max_retries = settings.sql_max_retries

        for attempt in range(max_retries + 1):
            try:
                execution_result = execute_query(active_sql, max_rows=request.max_rows)
                if attempt > 0:
                    corrected_sql = active_sql
                    correction_attempts = attempt
                    final_status = QueryStatus.CORRECTED
                else:
                    final_status = QueryStatus.SUCCESS
                break

            except SQLExecutionError as exec_err:
                if attempt >= max_retries:
                    raise
                log.info(f"Execution failed (attempt {attempt+1}), correcting...")
                try:
                    active_sql = correct_sql(
                        question=request.question,
                        failed_sql=active_sql,
                        error_message=exec_err.original_error,
                    )
                    validate_sql(active_sql)
                except (SQLCorrectionFailedError, SQLValidationError) as corr_err:
                    raise SQLExecutionError(
                        message=exec_err.message,
                        sql=active_sql,
                        original_error=exec_err.original_error,
                    ) from corr_err

        # ── Build Results ──────────────────────────────────────────────────────
        result_data = QueryResultData(
            columns=execution_result["columns"],
            rows=execution_result["rows"],
            row_count=execution_result["row_count"],
            truncated=execution_result["truncated"],
            execution_time_ms=execution_result["execution_time_ms"],
        )
        history.row_count = result_data.row_count
        history.execution_time_ms = result_data.execution_time_ms

        # ── Step 9: Confidence Scoring ─────────────────────────────────────────
        schema_tables = full_schema.get("tables", {})
        conf = calculate_confidence(
            sql=active_sql,
            schema_tables=schema_tables,
            execution_success=True,
            has_results=(result_data.row_count > 0),
            security_passed=security_passed,
        )
        confidence_score = conf.score

        # ── Step 10: Query Optimization ────────────────────────────────────────
        optimization_suggestions = optimize_query(active_sql)

        # ── Step 11: Visualization Recommendation ──────────────────────────────
        try:
            viz = recommend_visualization(
                question=request.question,
                columns=result_data.columns,
                rows=result_data.rows,
                row_count=result_data.row_count,
            )
            # Override with plan if plan suggested something specific and viz is just fallback
            if query_plan.visualization and viz.get("type") == "table":
                viz["type"] = query_plan.visualization
                
            viz_config = VisualizationConfig(**viz)
            history.visualization_type = viz_config.type
        except Exception as viz_err:
            log.warning("Viz recommendation failed", error=str(viz_err))
            viz_config = VisualizationConfig(type=query_plan.visualization or "table", reason="Fallback")

        # ── Step 12: Insight Generation ────────────────────────────────────────
        try:
            insight = summarize_results(
                question=request.question,
                columns=result_data.columns,
                rows=result_data.rows,
                row_count=result_data.row_count,
                truncated=result_data.truncated,
            )
            history.insight = insight
        except Exception as ins_err:
            log.warning("Insight generation failed", error=str(ins_err))

        # Update Conversation Title
        conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
        if conv and conv.title == "New Conversation":
            conv.title = request.question[:80]
            db.commit()

        # Invalidate memory cache so next turn rebuilds fresh
        invalidate_memory_cache(str(conversation_id))

    except (SQLValidationError, SQLCorrectionFailedError) as sec_err:
        final_status = QueryStatus.ERROR
        error_message = sec_err.message
        security_passed = False
        log.warning("SQL security/correction error", error=error_message)

    except SQLExecutionError as exec_err:
        final_status = QueryStatus.ERROR
        error_message = exec_err.original_error
        log.warning("SQL execution error", error=error_message)

    except LLMError as llm_err:
        final_status = QueryStatus.ERROR
        error_message = llm_err.message
        log.error("LLM error", error=error_message)

    except Exception as exc:
        final_status = QueryStatus.ERROR
        error_message = "An unexpected internal error occurred."
        log.exception("Unexpected pipeline error", error=str(exc))

    finally:
        history.status = final_status
        history.error_message = error_message
        history.corrected_sql = corrected_sql
        history.correction_attempts = correction_attempts
        db.commit()

    return _build_response(locals())


def _build_response(locs: dict) -> QueryResponse:
    """Helper to build the final response object."""
    total_ms = (time.perf_counter() - locs["pipeline_start"]) * 1000
    
    return QueryResponse(
        query_id=locs["history"].id,
        conversation_id=locs["conversation_id"],
        question=locs["request"].question,
        generated_sql=locs.get("generated_sql") or "",
        corrected_sql=locs.get("corrected_sql"),
        correction_attempts=locs.get("correction_attempts", 0),
        status=locs["final_status"].value,
        result=locs.get("result_data"),
        visualization=locs.get("viz_config"),
        insight=locs.get("insight"),
        relevant_tables=locs.get("relevant_tables", []),
        error_message=locs.get("error_message"),
        total_time_ms=round(total_ms, 2),
        intent=locs.get("intent_str"),
        confidence_score=locs.get("confidence_score"),
        query_plan=locs.get("query_plan_dict"),
        clarification_options=locs.get("clarification_options"),
        optimization_suggestions=locs.get("optimization_suggestions"),
    )
