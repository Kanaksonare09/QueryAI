"""QueryAI — SQL Explanation, Result Summarization, Viz Recommendation."""
import json
import re
from app.ai.llm import invoke_llm
from app.ai.prompts import (
    SQL_EXPLANATION_SYSTEM, SQL_EXPLANATION_HUMAN,
    RESULT_SUMMARY_SYSTEM, RESULT_SUMMARY_HUMAN,
    VIZ_RECOMMENDATION_SYSTEM, VIZ_RECOMMENDATION_HUMAN,
)
from app.core.logging import get_logger

log = get_logger(__name__)

VALID_VIZ_TYPES = {"bar", "line", "pie", "donut", "area", "scatter", "table", "kpi"}


# ── SQL Explanation ────────────────────────────────────────────────────────────
def explain_sql(sql: str) -> str:
    """Return a beginner-friendly explanation of the SQL query."""
    human = SQL_EXPLANATION_HUMAN.format(sql=sql)
    return invoke_llm(SQL_EXPLANATION_SYSTEM, human, temperature=0.3)


# ── Result Summarization ───────────────────────────────────────────────────────
def summarize_results(
    question: str,
    columns: list[str],
    rows: list[list],
    row_count: int,
    truncated: bool = False,
) -> str:
    """Return a 2-4 sentence insight about the query results."""
    sample_rows = rows[:10]
    sample_size = len(sample_rows)

    # Format as simple table text
    data_lines = []
    for row in sample_rows:
        data_lines.append(", ".join(str(v) for v in row))

    truncation_note = (
        f"(Note: Results were truncated. Showing {sample_size} of {row_count} rows.)"
        if truncated else ""
    )

    human = RESULT_SUMMARY_HUMAN.format(
        question=question,
        columns=", ".join(columns),
        data_sample="\n".join(data_lines),
        sample_size=sample_size,
        row_count=row_count,
        truncation_note=truncation_note,
    )
    return invoke_llm(RESULT_SUMMARY_SYSTEM, human, temperature=0.3)


# ── Visualization Recommendation ───────────────────────────────────────────────
def recommend_visualization(
    question: str,
    columns: list[str],
    rows: list[list],
    row_count: int,
) -> dict:
    """
    Recommend the best chart type for the results.
    Returns a dict: {type, x_column, y_column, color_column, reason}
    Falls back to heuristics if LLM fails.
    """
    # Fast heuristic fallbacks
    if row_count == 0:
        return {"type": "table", "x_column": None, "y_column": None, "color_column": None, "reason": "No data"}
    if row_count == 1 and len(columns) == 1:
        return {"type": "kpi", "x_column": None, "y_column": columns[0], "color_column": None, "reason": "Single value"}

    sample = rows[:5]
    sample_str = "\n".join(", ".join(str(v) for v in row) for row in sample)

    human = VIZ_RECOMMENDATION_HUMAN.format(
        question=question,
        columns=", ".join(columns),
        sample=sample_str,
        row_count=row_count,
    )

    try:
        raw = invoke_llm(VIZ_RECOMMENDATION_SYSTEM, human, temperature=0.0)
        # Extract JSON
        json_match = re.search(r"\{.*\}", raw, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
            if result.get("type") in VALID_VIZ_TYPES:
                return result
    except Exception as exc:
        log.warning("Viz recommendation LLM failed, using heuristic", error=str(exc))

    # Heuristic fallback
    return _heuristic_viz(columns, rows, row_count)


def _heuristic_viz(columns: list[str], rows: list[list], row_count: int) -> dict:
    """Simple rule-based fallback for visualization type."""
    num_cols = len(columns)

    if row_count == 1 and num_cols == 1:
        return {"type": "kpi", "x_column": None, "y_column": columns[0], "color_column": None, "reason": "Single metric"}

    # Detect date/time column
    date_keywords = {"date", "month", "year", "week", "day", "time", "period"}
    has_date = any(any(kw in c.lower() for kw in date_keywords) for c in columns)

    # Detect numeric columns
    numeric_cols = []
    for i, col in enumerate(columns):
        if rows:
            val = rows[0][i]
            if isinstance(val, (int, float)) and not isinstance(val, bool):
                numeric_cols.append(col)

    if has_date and numeric_cols and num_cols <= 4:
        return {"type": "line", "x_column": columns[0], "y_column": numeric_cols[0], "color_column": None, "reason": "Time-series data"}

    if num_cols == 2 and numeric_cols and row_count <= 8:
        return {"type": "pie", "x_column": columns[0], "y_column": numeric_cols[0], "color_column": None, "reason": "Categorical proportions"}

    if num_cols <= 3 and numeric_cols:
        return {"type": "bar", "x_column": columns[0], "y_column": numeric_cols[0], "color_column": None, "reason": "Category comparison"}

    return {"type": "table", "x_column": None, "y_column": None, "color_column": None, "reason": "Complex multi-column data"}
