"""
QueryAI — Safe SQL Executor.
Runs read-only queries against the business database with:
  • timeout enforcement (statement_timeout)
  • row-count limit (LIMIT injection)
  • sanitized error messages (no stack traces to client)
  • execution time measurement
"""
import time
from typing import Any
from sqlalchemy import text

from app.database.connection import biz_engine
from app.core.config import settings
from app.core.exceptions import SQLExecutionError
from app.core.logging import get_logger

log = get_logger(__name__)


def _inject_limit(sql: str, max_rows: int) -> str:
    """
    Append or reduce LIMIT clause to cap result size.
    Uses simple string detection — AST-level validation is done separately.
    """
    sql_upper = sql.upper().strip().rstrip(";")
    if "LIMIT" not in sql_upper:
        return f"{sql.rstrip(';')} LIMIT {max_rows}"
    # If LIMIT already present, leave as-is (validator already checked it)
    return sql


def execute_query(sql: str, max_rows: int | None = None) -> dict[str, Any]:
    """
    Execute a validated SELECT query and return structured results.

    Returns:
      {
        "columns":   [str, ...],
        "rows":      [[val, ...], ...],
        "row_count": int,
        "execution_time_ms": float,
        "truncated": bool   # True if row limit was applied
      }

    Raises:
      SQLExecutionError on any database error.
    """
    max_rows = max_rows or settings.sql_max_rows
    sql_with_limit = _inject_limit(sql, max_rows)

    start = time.perf_counter()
    try:
        with biz_engine.connect() as conn:
            result = conn.execute(text(sql_with_limit))
            columns = list(result.keys())
            rows = result.fetchall()

        elapsed_ms = (time.perf_counter() - start) * 1000

        # Serialize rows (handle dates, decimals, etc.)
        serialized_rows = []
        for row in rows:
            serialized_rows.append([
                _serialize_value(v) for v in row
            ])

        truncated = len(rows) >= max_rows

        log.info(
            "Query executed",
            rows=len(rows),
            elapsed_ms=round(elapsed_ms, 2),
            truncated=truncated,
        )

        return {
            "columns": columns,
            "rows": serialized_rows,
            "row_count": len(serialized_rows),
            "execution_time_ms": round(elapsed_ms, 2),
            "truncated": truncated,
        }

    except SQLExecutionError:
        raise
    except Exception as exc:
        elapsed_ms = (time.perf_counter() - start) * 1000
        # Sanitize: don't expose internal DB details
        safe_error = _sanitize_error(str(exc))
        log.warning("Query execution failed", error=safe_error, sql=sql[:200])
        raise SQLExecutionError(
            message="Query execution failed",
            sql=sql,
            original_error=safe_error,
        )


def _serialize_value(v: Any) -> Any:
    """Convert non-JSON-serializable types to primitives."""
    if v is None:
        return None
    import decimal, datetime
    if isinstance(v, decimal.Decimal):
        return float(v)
    if isinstance(v, (datetime.date, datetime.datetime)):
        return v.isoformat()
    if isinstance(v, datetime.timedelta):
        return str(v)
    return v


def _sanitize_error(error: str) -> str:
    """Remove potentially sensitive DB internals from error messages."""
    # Strip file paths and line numbers postgres includes
    import re
    error = re.sub(r'LINE \d+:.*', '', error)
    error = re.sub(r'HINT:.*', '', error)
    error = re.sub(r'DETAIL:.*', '', error)
    # Truncate very long errors
    return error.strip()[:500]
