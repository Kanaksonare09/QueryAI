"""
QueryAI — SQL Generation Pipeline.
Orchestrates: RAG retrieval → prompt construction → LLM call → SQL extraction.
"""
import re
from app.ai.llm import invoke_llm
from app.ai.rag import get_relevant_schema_ddl
from app.ai.prompts import SQL_GENERATION_SYSTEM, SQL_GENERATION_HUMAN
from app.core.exceptions import LLMError
from app.core.logging import get_logger

log = get_logger(__name__)

_SQL_FENCE_RE = re.compile(r"```(?:sql)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)
_LEAD_SELECT_RE = re.compile(r"(SELECT\s.+)", re.DOTALL | re.IGNORECASE)


def _extract_sql(raw: str) -> str:
    """
    Extract clean SQL from LLM response.
    Handles: code fences, leading text, whitespace.
    """
    # Try code fence first
    match = _SQL_FENCE_RE.search(raw)
    if match:
        return match.group(1).strip()

    # Try finding SELECT anywhere in the response
    match = _LEAD_SELECT_RE.search(raw)
    if match:
        return match.group(1).strip()

    # Return as-is (cleaned)
    return raw.strip()


def generate_sql(
    question: str,
    conversation_context: str = "",
    query_plan_str: str = "",
    top_k_tables: int = 6,
) -> tuple[str, list[str]]:
    """
    Generate SQL for a natural-language question.

    Returns:
      (sql_string, relevant_table_names)

    Raises:
      LLMError if the LLM cannot generate SQL.
    """
    # 1. RAG: retrieve relevant schema
    schema_ddl, relevant_tables = get_relevant_schema_ddl(question, top_k=top_k_tables)

    log.info("Generating SQL", question=question[:80], tables=relevant_tables)

    # 2. Build prompt
    human_prompt = SQL_GENERATION_HUMAN.format(
        schema=schema_ddl,
        conversation_context=conversation_context or "None",
        query_plan=query_plan_str or "None",
        question=question,
    )

    # 3. Call LLM
    raw_response = invoke_llm(SQL_GENERATION_SYSTEM, human_prompt, temperature=0.0)

    # 4. Check for "cannot answer"
    if "CANNOT_ANSWER" in raw_response.upper():
        raise LLMError(
            "The question cannot be answered with the available database schema. "
            "Please rephrase or ask about the available data."
        )

    # 5. Extract SQL
    sql = _extract_sql(raw_response)

    if not sql or len(sql) < 6:
        raise LLMError("LLM returned an empty or invalid SQL response.")

    log.info("SQL generated", sql=sql[:120])
    return sql, relevant_tables
