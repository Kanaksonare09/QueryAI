"""
QueryAI — Automatic SQL Correction.
When a query fails, sends the error + original SQL + question back to the
LLM to generate a corrected query. Respects MAX_RETRIES limit.
"""
import re
from app.ai.llm import invoke_llm
from app.ai.rag import get_relevant_schema_ddl
from app.ai.prompts import SQL_CORRECTION_SYSTEM, SQL_CORRECTION_HUMAN
from app.core.exceptions import LLMError, SQLCorrectionFailedError
from app.core.logging import get_logger

log = get_logger(__name__)

_SQL_FENCE_RE = re.compile(r"```(?:sql)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)
_LEAD_SELECT_RE = re.compile(r"(SELECT\s.+)", re.DOTALL | re.IGNORECASE)


def _extract_sql(raw: str) -> str:
    match = _SQL_FENCE_RE.search(raw)
    if match:
        return match.group(1).strip()
    match = _LEAD_SELECT_RE.search(raw)
    if match:
        return match.group(1).strip()
    return raw.strip()


def correct_sql(
    question: str,
    failed_sql: str,
    error_message: str,
) -> str:
    """
    Attempt to correct a failed SQL query using LLM feedback.

    Returns:
      Corrected SQL string.

    Raises:
      SQLCorrectionFailedError if correction is not possible.
    """
    schema_ddl, _ = get_relevant_schema_ddl(question)

    log.info("Attempting SQL correction", error=error_message[:100])

    human_prompt = SQL_CORRECTION_HUMAN.format(
        schema=schema_ddl,
        question=question,
        failed_sql=failed_sql,
        error_message=error_message,
    )

    raw_response = invoke_llm(SQL_CORRECTION_SYSTEM, human_prompt, temperature=0.1)

    if "CANNOT_CORRECT" in raw_response.upper():
        raise SQLCorrectionFailedError(
            "The SQL error could not be automatically corrected. "
            "Please rephrase your question."
        )

    corrected = _extract_sql(raw_response)
    if not corrected or len(corrected) < 6:
        raise SQLCorrectionFailedError("LLM returned an empty correction.")

    log.info("SQL corrected", corrected=corrected[:120])
    return corrected
