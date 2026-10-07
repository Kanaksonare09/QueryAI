"""QueryAI — Query API routes."""
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.services.query_service import run_query_pipeline
from app.ai.insights import explain_sql, recommend_visualization
from app.ai.sql_corrector import correct_sql
from app.security.sql_validator import validate_sql, is_safe_sql
from app.schemas.query import (
    QueryRequest, QueryResponse,
    ValidateRequest, ValidateResponse,
    ExplainRequest, ExplainResponse,
    CorrectRequest, CorrectResponse,
)
from app.core.exceptions import SQLValidationError, LLMError, http_bad_request, http_internal
from app.core.logging import get_logger

log = get_logger(__name__)
router = APIRouter(prefix="/query", tags=["Query"])


@router.post("", response_model=QueryResponse, summary="Run full text-to-SQL pipeline")
async def run_query(request: QueryRequest, db: Session = Depends(get_db)):
    """
    Execute the complete pipeline:
    question → schema retrieval → SQL generation → validation → execution
    → visualization recommendation → natural-language insight.
    """
    try:
        return run_query_pipeline(request, db)
    except LLMError as exc:
        raise HTTPException(status_code=503, detail=exc.message)
    except Exception as exc:
        log.exception("Unhandled error in /query", error=str(exc))
        raise http_internal("An unexpected error occurred.")


@router.post("/validate", response_model=ValidateResponse, summary="Validate SQL safety")
async def validate_query(request: ValidateRequest):
    """Validate a SQL string for safety and correctness without executing it."""
    is_valid, error = is_safe_sql(request.sql)
    return ValidateResponse(is_valid=is_valid, error=error, sql=request.sql if is_valid else None)


@router.post("/explain", response_model=ExplainResponse, summary="Explain SQL in plain language")
async def explain_query(request: ExplainRequest):
    """Generate a beginner-friendly explanation of a SQL query."""
    # Validate before explaining
    is_valid, error = is_safe_sql(request.sql)
    if not is_valid:
        raise http_bad_request(f"Cannot explain invalid SQL: {error}")
    try:
        explanation = explain_sql(request.sql)
        return ExplainResponse(explanation=explanation, sql=request.sql)
    except LLMError as exc:
        raise HTTPException(status_code=503, detail=exc.message)


@router.post("/correct", response_model=CorrectResponse, summary="Auto-correct a failed SQL query")
async def correct_query(request: CorrectRequest):
    """Ask the LLM to correct a failed SQL query given the error message."""
    try:
        corrected = correct_sql(
            question=request.question,
            failed_sql=request.failed_sql,
            error_message=request.error_message,
        )
        is_valid, err = is_safe_sql(corrected)
        return CorrectResponse(corrected_sql=corrected, is_valid=is_valid, error=err)
    except LLMError as exc:
        raise HTTPException(status_code=503, detail=exc.message)
    except Exception as exc:
        raise http_internal(str(exc))
