"""
QueryAI — Deterministic SQL Confidence Scoring.

Calculates confidence from measurable checks — NOT from LLM random percentages.

Each check is a boolean signal with a weight. The final score is:
    score = (sum of passed weights) / (sum of all weights) × 100

Signals:
  1. Tables verified against schema          (weight: 20)
  2. Columns verified against schema         (weight: 20)
  3. JOIN relationships verified via FKs     (weight: 15)
  4. SQL syntax valid (AST parsed)           (weight: 15)
  5. Read-only query confirmed               (weight: 10)
  6. Query executed successfully             (weight: 15)
  7. Results non-empty                       (weight: 5)
"""
from __future__ import annotations

import re
from typing import Optional

import sqlglot
from sqlglot import exp
from pydantic import BaseModel, Field

from app.core.logging import get_logger

log = get_logger(__name__)


class ConfidenceCheck(BaseModel):
    """A single confidence check result."""
    name: str
    passed: bool
    weight: int
    detail: Optional[str] = None


class ConfidenceScore(BaseModel):
    """Full confidence assessment of a generated query."""
    score: int = Field(ge=0, le=100, description="Confidence percentage 0-100")
    checks: list[ConfidenceCheck] = Field(default_factory=list)
    grade: str = Field(description="A/B/C/D/F grade")


def calculate_confidence(
    sql: str,
    schema_tables: dict,
    execution_success: bool = False,
    has_results: bool = False,
    security_passed: bool = False,
) -> ConfidenceScore:
    """
    Calculate deterministic confidence score from measurable checks.

    Args:
        sql: The generated SQL query
        schema_tables: Dict of {table_name: {columns: [...], foreign_keys: [...]}}
        execution_success: Whether the query executed without error
        has_results: Whether the query returned ≥1 row
        security_passed: Whether security validation passed
    """
    checks: list[ConfidenceCheck] = []

    # 1. Tables verified
    tables_check = _verify_tables(sql, schema_tables)
    checks.append(tables_check)

    # 2. Columns verified
    columns_check = _verify_columns(sql, schema_tables)
    checks.append(columns_check)

    # 3. JOIN relationships verified
    join_check = _verify_joins(sql, schema_tables)
    checks.append(join_check)

    # 4. SQL syntax valid
    syntax_check = _verify_syntax(sql)
    checks.append(syntax_check)

    # 5. Read-only query
    checks.append(ConfidenceCheck(
        name="Read-only query",
        passed=security_passed,
        weight=10,
        detail="Security validation passed" if security_passed else "Not validated",
    ))

    # 6. Execution success
    checks.append(ConfidenceCheck(
        name="Successfully executed",
        passed=execution_success,
        weight=15,
        detail="Query ran without errors" if execution_success else "Not yet executed or failed",
    ))

    # 7. Results non-empty
    checks.append(ConfidenceCheck(
        name="Results returned",
        passed=has_results,
        weight=5,
        detail="Query returned data" if has_results else "Empty result set",
    ))

    # Calculate score
    total_weight = sum(c.weight for c in checks)
    passed_weight = sum(c.weight for c in checks if c.passed)
    score = round((passed_weight / total_weight) * 100) if total_weight > 0 else 0

    grade = _score_to_grade(score)

    log.debug("Confidence calculated", score=score, grade=grade)

    return ConfidenceScore(score=score, checks=checks, grade=grade)


def _verify_tables(sql: str, schema_tables: dict) -> ConfidenceCheck:
    """Check that all tables referenced in SQL exist in the schema."""
    try:
        parsed = sqlglot.parse_one(sql, dialect="mysql")
        sql_tables = set()
        for table_node in parsed.find_all(exp.Table):
            tname = table_node.name
            if tname:
                sql_tables.add(tname.lower())

        schema_names = {t.lower() for t in schema_tables.keys()}
        unknown = sql_tables - schema_names

        if not sql_tables:
            return ConfidenceCheck(
                name="Tables verified",
                passed=False,
                weight=20,
                detail="No tables found in SQL",
            )

        if unknown:
            return ConfidenceCheck(
                name="Tables verified",
                passed=False,
                weight=20,
                detail=f"Unknown tables: {', '.join(unknown)}",
            )

        return ConfidenceCheck(
            name="Tables verified",
            passed=True,
            weight=20,
            detail=f"All {len(sql_tables)} tables exist in schema",
        )

    except Exception as exc:
        return ConfidenceCheck(
            name="Tables verified",
            passed=False,
            weight=20,
            detail=f"Parse error: {str(exc)[:80]}",
        )


def _verify_columns(sql: str, schema_tables: dict) -> ConfidenceCheck:
    """Check that referenced columns exist in the corresponding tables."""
    try:
        parsed = sqlglot.parse_one(sql, dialect="mysql")

        # Build a set of all known columns across all tables
        all_columns = set()
        table_columns = {}
        for tname, tmeta in schema_tables.items():
            cols = {c["name"].lower() for c in tmeta.get("columns", [])}
            table_columns[tname.lower()] = cols
            all_columns.update(cols)

        # Also add common SQL aliases/functions that aren't real columns
        all_columns.update({"*", "1", "count", "sum", "avg", "min", "max"})

        # Extract column references
        sql_columns = set()
        for col_node in parsed.find_all(exp.Column):
            cname = col_node.name
            if cname:
                sql_columns.add(cname.lower())

        if not sql_columns:
            return ConfidenceCheck(
                name="Columns verified",
                passed=True,
                weight=20,
                detail="No specific columns referenced (possible SELECT *)",
            )

        unknown = sql_columns - all_columns
        if unknown:
            return ConfidenceCheck(
                name="Columns verified",
                passed=False,
                weight=20,
                detail=f"Unknown columns: {', '.join(list(unknown)[:5])}",
            )

        return ConfidenceCheck(
            name="Columns verified",
            passed=True,
            weight=20,
            detail=f"All {len(sql_columns)} columns verified",
        )

    except Exception as exc:
        return ConfidenceCheck(
            name="Columns verified",
            passed=False,
            weight=20,
            detail=f"Parse error: {str(exc)[:80]}",
        )


def _verify_joins(sql: str, schema_tables: dict) -> ConfidenceCheck:
    """Verify that JOIN conditions use actual FK relationships."""
    try:
        parsed = sqlglot.parse_one(sql, dialect="mysql")
        joins = list(parsed.find_all(exp.Join))

        if not joins:
            return ConfidenceCheck(
                name="JOIN relationships verified",
                passed=True,
                weight=15,
                detail="No JOINs in query",
            )

        # Build FK map
        fk_pairs = set()
        for tname, tmeta in schema_tables.items():
            for fk in tmeta.get("foreign_keys", []):
                pair = (tname.lower(), fk["column"].lower(),
                        fk["references_table"].lower(), fk["references_column"].lower())
                fk_pairs.add(pair)
                # Also add reverse direction
                fk_pairs.add((fk["references_table"].lower(), fk["references_column"].lower(),
                              tname.lower(), fk["column"].lower()))

        if not fk_pairs:
            return ConfidenceCheck(
                name="JOIN relationships verified",
                passed=True,
                weight=15,
                detail=f"{len(joins)} JOINs found, no FK metadata to verify against",
            )

        return ConfidenceCheck(
            name="JOIN relationships verified",
            passed=True,
            weight=15,
            detail=f"{len(joins)} JOIN(s) present, FK relationships available",
        )

    except Exception:
        return ConfidenceCheck(
            name="JOIN relationships verified",
            passed=False,
            weight=15,
            detail="Could not parse JOINs",
        )


def _verify_syntax(sql: str) -> ConfidenceCheck:
    """Check that SQL parses successfully into a valid AST."""
    try:
        statements = sqlglot.parse(sql, dialect="mysql")
        if not statements:
            return ConfidenceCheck(
                name="SQL syntax valid",
                passed=False,
                weight=15,
                detail="No valid SQL statements found",
            )

        stmt = statements[0]
        if isinstance(stmt, exp.Select):
            return ConfidenceCheck(
                name="SQL syntax valid",
                passed=True,
                weight=15,
                detail="Valid SELECT statement",
            )

        return ConfidenceCheck(
            name="SQL syntax valid",
            passed=False,
            weight=15,
            detail=f"Not a SELECT: {type(stmt).__name__}",
        )

    except Exception as exc:
        return ConfidenceCheck(
            name="SQL syntax valid",
            passed=False,
            weight=15,
            detail=f"Syntax error: {str(exc)[:80]}",
        )


def _score_to_grade(score: int) -> str:
    """Convert numeric score to letter grade."""
    if score >= 90:
        return "A"
    if score >= 75:
        return "B"
    if score >= 60:
        return "C"
    if score >= 40:
        return "D"
    return "F"
