"""
QueryAI — Database Query Optimizer.

Uses MySQL's EXPLAIN statement to detect potential performance issues
like full table scans or filesorts. Returns optimization suggestions.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import text

from app.database.connection import biz_engine
from app.core.logging import get_logger

log = get_logger(__name__)


def optimize_query(sql: str) -> list[str]:
    """
    Run EXPLAIN on the SQL and analyze the execution plan.
    Returns a list of human-readable optimization suggestions.
    """
    suggestions = []
    
    # Don't try to explain empty or highly complex strings that might not be SELECT
    sql_upper = sql.upper().strip()
    if not sql_upper.startswith("SELECT"):
        return ["Cannot optimize non-SELECT statements."]
        
    try:
        with biz_engine.connect() as conn:
            # Run EXPLAIN (MySQL specific)
            explain_sql = f"EXPLAIN {sql}"
            result = conn.execute(text(explain_sql))
            rows = result.fetchall()
            
            # Analyze each row of the execution plan
            tables_scanned = 0
            for row in rows:
                row_dict = dict(row._mapping)
                
                table_name = row_dict.get("table", "Unknown")
                type_ = row_dict.get("type", "").upper()
                extra = row_dict.get("Extra", "").upper()
                rows_examined = row_dict.get("rows", 0)
                
                # Full table scan check
                if type_ == "ALL":
                    if rows_examined > 1000:
                        suggestions.append(
                            f"Full table scan detected on '{table_name}'. "
                            f"Consider adding an index if filtering on this table."
                        )
                    tables_scanned += 1
                
                # Filesort check
                if "USING FILESORT" in extra:
                    suggestions.append(
                        f"Filesort detected on '{table_name}' due to ORDER BY. "
                        f"Consider indexing the order column to improve sorting performance."
                    )
                    
                # Temporary table check
                if "USING TEMPORARY" in extra:
                    suggestions.append(
                        f"Temporary table created for '{table_name}'. "
                        f"This often happens with complex GROUP BY or DISTINCT clauses."
                    )
            
            if tables_scanned > 1:
                suggestions.append(
                    "Multiple full table scans detected. This query might be slow on large datasets. "
                    "Ensure JOIN conditions are indexed."
                )

    except Exception as exc:
        log.warning("Query optimization failed", error=str(exc))
        return ["Could not analyze query execution plan."]

    if not suggestions:
        return ["Query execution plan looks optimal."]
        
    return suggestions
