"""
Text-to-SQL execution engine with security guardrails.
"""
import time
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import text, event
from sqlalchemy.orm import Session
from app.config import settings
from app.database.schema_inspector import validate_sql
import structlog

logger = structlog.get_logger()


class SQLExecutor:
    def __init__(self, session: Session):
        self.session = session
        self.timeout = settings.sql_query_timeout
        self.row_limit = settings.sql_row_limit

    def execute(self, sql: str) -> Dict[str, Any]:
        """
        Execute a validated SQL query and return structured results.
        Returns: {columns, rows, row_count, truncated, execution_time_ms, error}
        """
        # Re-validate before execution
        is_safe, err = validate_sql(sql)
        if not is_safe:
            return {"error": err, "columns": [], "rows": [], "row_count": 0}

        # Inject row limit
        safe_sql = self._inject_limit(sql)

        start = time.perf_counter()
        try:
            result = self.session.execute(
                text(safe_sql).execution_options(timeout=self.timeout)
            )
            rows_raw = result.fetchall()
            columns = list(result.keys())
            rows = [list(r) for r in rows_raw]
            elapsed_ms = round((time.perf_counter() - start) * 1000, 2)

            truncated = len(rows) >= self.row_limit

            logger.info("SQL executed", rows=len(rows), elapsed_ms=elapsed_ms)
            return {
                "columns": columns,
                "rows": rows,
                "row_count": len(rows),
                "truncated": truncated,
                "execution_time_ms": elapsed_ms,
                "sql_executed": safe_sql,
                "error": None,
            }
        except Exception as e:
            elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
            logger.error("SQL execution error", error=str(e))
            return {
                "error": str(e),
                "columns": [],
                "rows": [],
                "row_count": 0,
                "execution_time_ms": elapsed_ms,
            }

    def _inject_limit(self, sql: str) -> str:
        """Add LIMIT clause if not already present."""
        sql_upper = sql.upper()
        if "LIMIT" not in sql_upper:
            return f"{sql.rstrip(';')} LIMIT {self.row_limit}"
        return sql

    def rows_to_markdown_table(self, columns: List[str], rows: List[List[Any]]) -> str:
        """Format query results as markdown table."""
        if not columns:
            return "_No results_"
        header = "| " + " | ".join(str(c) for c in columns) + " |"
        sep = "| " + " | ".join("---" for _ in columns) + " |"
        body = "\n".join(
            "| " + " | ".join(str(v) if v is not None else "NULL" for v in row) + " |"
            for row in rows
        )
        return f"{header}\n{sep}\n{body}"

    def infer_chart_type(self, columns: List[str], rows: List[List[Any]]) -> Optional[str]:
        """Heuristically suggest a chart type for the result set."""
        if len(columns) < 2 or len(rows) == 0:
            return None
        if len(rows) == 1:
            return None
        # If first col is categorical and second is numeric → bar
        try:
            float(rows[0][1])
            if len(rows) <= 5:
                return "pie"
            return "bar"
        except (TypeError, ValueError):
            return None
