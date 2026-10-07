"""
MySQL Schema Inspector — reads table structure without exposing the entire schema.
Supports intelligent table selection based on query relevance.
"""
import re
from typing import Any, Dict, List, Optional
from sqlalchemy import text
from sqlalchemy.orm import Session
import structlog

logger = structlog.get_logger()

# Tables used by the application itself (exclude from user-visible schema)
APP_TABLES = {
    "app_documents", "app_collections", "app_document_chunks",
    "app_conversations", "app_messages"
}

FORBIDDEN_SQL_PATTERNS = re.compile(
    r"\b(DROP|DELETE|TRUNCATE|ALTER|CREATE|INSERT|UPDATE|RENAME|GRANT|REVOKE"
    r"|EXECUTE|EXEC|LOAD\s+DATA|INTO\s+OUTFILE|DUMPFILE)\b",
    re.IGNORECASE,
)

ALLOWED_STARTING_KEYWORDS = re.compile(r"^\s*(SELECT|WITH|SHOW|DESCRIBE|EXPLAIN)\b", re.IGNORECASE)


class SchemaInspector:
    def __init__(self, session: Session):
        self.session = session

    def get_all_tables(self) -> List[str]:
        """Return all user-facing tables (excluding app metadata tables)."""
        result = self.session.execute(text("SHOW TABLES"))
        tables = [row[0] for row in result.fetchall()]
        return [t for t in tables if t not in APP_TABLES]

    def get_table_schema(self, table_name: str) -> Dict[str, Any]:
        """Get full schema for a single table."""
        # Validate table name (prevent injection)
        if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", table_name):
            raise ValueError(f"Invalid table name: {table_name}")

        columns_result = self.session.execute(text(f"DESCRIBE `{table_name}`"))
        columns = []
        for row in columns_result.fetchall():
            columns.append({
                "name": row[0],
                "type": row[1],
                "nullable": row[2] == "YES",
                "key": row[3],
                "default": row[4],
                "extra": row[5],
            })

        # Get foreign keys
        fk_result = self.session.execute(text(f"""
            SELECT
                kcu.COLUMN_NAME,
                kcu.REFERENCED_TABLE_NAME,
                kcu.REFERENCED_COLUMN_NAME
            FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu
            WHERE kcu.TABLE_SCHEMA = DATABASE()
              AND kcu.TABLE_NAME = :table_name
              AND kcu.REFERENCED_TABLE_NAME IS NOT NULL
        """), {"table_name": table_name})
        foreign_keys = [
            {"column": r[0], "references_table": r[1], "references_column": r[2]}
            for r in fk_result.fetchall()
        ]

        # Row count estimate
        count_result = self.session.execute(text(f"SELECT COUNT(*) FROM `{table_name}`"))
        row_count = count_result.scalar()

        return {
            "table_name": table_name,
            "columns": columns,
            "foreign_keys": foreign_keys,
            "row_count": row_count,
        }

    def get_full_schema(self) -> List[Dict[str, Any]]:
        """Get schema for all user-facing tables."""
        tables = self.get_all_tables()
        return [self.get_table_schema(t) for t in tables]

    def get_relevant_schema(self, tables: List[str]) -> List[Dict[str, Any]]:
        """Get schema only for specified tables."""
        all_tables = self.get_all_tables()
        valid_tables = [t for t in tables if t in all_tables]
        return [self.get_table_schema(t) for t in valid_tables]

    def schema_to_prompt_string(self, schemas: List[Dict[str, Any]]) -> str:
        """Format schema as a string suitable for LLM prompting."""
        lines = []
        for s in schemas:
            lines.append(f"Table: {s['table_name']} (rows: {s['row_count']})")
            for col in s["columns"]:
                pk = " [PK]" if col["key"] == "PRI" else ""
                nullable = "" if col["nullable"] else " NOT NULL"
                lines.append(f"  - {col['name']}: {col['type']}{pk}{nullable}")
            for fk in s["foreign_keys"]:
                lines.append(f"  FK: {fk['column']} → {fk['references_table']}.{fk['references_column']}")
            lines.append("")
        return "\n".join(lines)


def validate_sql(sql: str) -> tuple[bool, Optional[str]]:
    """
    Validate SQL for safety. Returns (is_safe, error_message).
    """
    sql_stripped = sql.strip()

    if not sql_stripped:
        return False, "Empty SQL query."

    if not ALLOWED_STARTING_KEYWORDS.match(sql_stripped):
        return False, "Only SELECT/WITH/SHOW/DESCRIBE/EXPLAIN queries are allowed."

    if FORBIDDEN_SQL_PATTERNS.search(sql_stripped):
        return False, "Query contains forbidden SQL keywords."

    # Block multiple statements
    if ";" in sql_stripped.rstrip(";"):
        return False, "Multiple SQL statements are not allowed."

    return True, None
