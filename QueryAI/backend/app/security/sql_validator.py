"""
QueryAI — SQL Security Validator.
Multi-layer validation:
  1. Keyword blocklist (fast pre-check)
  2. sqlglot AST parse + statement type enforcement
  3. Dangerous pattern regex checks
  4. Query complexity limits
"""
import re
import sqlglot
from sqlglot import exp

from app.core.exceptions import SQLValidationError
from app.core.logging import get_logger

log = get_logger(__name__)

# ── Blocked keywords / patterns ────────────────────────────────────────────────
_BLOCKED_KEYWORDS = {
    "DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "TRUNCATE",
    "CREATE", "REPLACE", "MERGE", "UPSERT", "GRANT", "REVOKE",
    "EXECUTE", "EXEC", "CALL", "PRAGMA", "ATTACH", "DETACH",
    "COPY", "VACUUM", "ANALYZE", "REINDEX", "CLUSTER",
    "LOCK", "UNLOCK", "SET", "RESET", "LOAD", "IMPORT",
}

# Patterns that should never appear even inside strings
_DANGEROUS_PATTERNS = [
    r";\s*(DROP|DELETE|UPDATE|INSERT|ALTER|CREATE|TRUNCATE)",  # stacked queries
    r"--",                                                      # SQL comments (allow only if clean)
    r"/\*.*?\*/",                                              # block comments
    r"xp_cmdshell",                                            # MSSQL shell
    r"INFORMATION_SCHEMA\s*\.\s*TABLES.*UNION",               # schema enumeration
    r"SLEEP\s*\(",                                             # time-based injection
    r"PG_SLEEP\s*\(",
    r"WAITFOR\s+DELAY",
    r"BENCHMARK\s*\(",
    r"LOAD_FILE\s*\(",
    r"INTO\s+(OUTFILE|DUMPFILE)",
]

_DANGEROUS_RE = [re.compile(p, re.IGNORECASE | re.DOTALL) for p in _DANGEROUS_PATTERNS]

# Allow SQL comments only if they are benign (not stacked queries)
_COMMENT_RE = re.compile(r"(--[^\n]*|/\*.*?\*/)", re.DOTALL)


def validate_sql(sql: str) -> str:
    """
    Validate SQL for safety. Returns the cleaned SQL string on success.
    Raises SQLValidationError with a descriptive message on failure.
    """
    if not sql or not sql.strip():
        raise SQLValidationError("Empty SQL query provided.")

    sql = sql.strip().rstrip(";")

    # 1. Strip comments for keyword analysis (keep original for AST)
    sql_no_comments = _COMMENT_RE.sub(" ", sql)

    # 2. Keyword blocklist check
    tokens = set(re.split(r'\W+', sql_no_comments.upper()))
    blocked = tokens & _BLOCKED_KEYWORDS
    if blocked:
        raise SQLValidationError(
            f"Query contains forbidden keyword(s): {', '.join(sorted(blocked))}. "
            "Only SELECT statements are allowed."
        )

    # 3. Dangerous pattern check
    for pattern in _DANGEROUS_RE:
        if pattern.search(sql):
            raise SQLValidationError(
                "Query contains a potentially dangerous pattern and was blocked for security."
            )

    # 4. AST-level parse and statement type check
    try:
        statements = sqlglot.parse(sql, dialect="postgres")
    except Exception as exc:
        raise SQLValidationError(f"SQL syntax error: {str(exc)[:200]}")

    if not statements:
        raise SQLValidationError("No valid SQL statement found.")

    if len(statements) > 1:
        raise SQLValidationError(
            "Multiple statements are not allowed. Please submit one query at a time."
        )

    stmt = statements[0]

    # Must be a SELECT
    if not isinstance(stmt, exp.Select):
        stmt_type = type(stmt).__name__
        raise SQLValidationError(
            f"Only SELECT statements are permitted. Got: {stmt_type}."
        )

    # 5. No subquery writes (INSERT INTO ... SELECT ...)
    for node in stmt.walk():
        if isinstance(node, (exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Create)):
            raise SQLValidationError("Nested write operations are not permitted.")

    # 6. Complexity: no more than 10 JOINs (abuse guard)
    joins = list(stmt.find_all(exp.Join))
    if len(joins) > 10:
        raise SQLValidationError(
            f"Query has {len(joins)} JOIN operations. Maximum allowed is 10."
        )

    log.debug("SQL validation passed", sql=sql[:100])
    return sql


def is_safe_sql(sql: str) -> tuple[bool, str | None]:
    """
    Returns (True, None) if safe, (False, reason) if not.
    Non-raising convenience wrapper.
    """
    try:
        validate_sql(sql)
        return True, None
    except SQLValidationError as exc:
        return False, exc.message
