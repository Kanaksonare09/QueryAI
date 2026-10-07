"""
QueryAI — Conversation Memory.

Tracks active entities per conversation turn:
  - tables mentioned
  - columns referenced
  - filters applied
  - metrics / aggregations
  - date ranges
  - active visualization type
  - last generated SQL

This is NOT persisted to DB — it's rebuilt from QueryHistory on demand.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ConversationMemory:
    """In-memory representation of conversation state built from history."""

    conversation_id: Optional[str] = None
    tables: list[str] = field(default_factory=list)
    columns: list[str] = field(default_factory=list)
    filters: list[str] = field(default_factory=list)
    metrics: list[str] = field(default_factory=list)
    dimensions: list[str] = field(default_factory=list)
    date_range: Optional[str] = None
    visualization_type: Optional[str] = None
    last_sql: Optional[str] = None
    last_question: Optional[str] = None
    turn_count: int = 0

    def to_context_string(self) -> str:
        """
        Build a compact context string for the LLM prompt.
        Only includes non-empty fields to keep token usage low.
        """
        if self.turn_count == 0:
            return "None"

        parts = []
        if self.last_question:
            parts.append(f"Previous question: {self.last_question}")
        if self.tables:
            parts.append(f"Tables in use: {', '.join(self.tables)}")
        if self.columns:
            parts.append(f"Columns referenced: {', '.join(self.columns[:10])}")
        if self.filters:
            parts.append(f"Active filters: {', '.join(self.filters[:5])}")
        if self.metrics:
            parts.append(f"Metrics: {', '.join(self.metrics)}")
        if self.dimensions:
            parts.append(f"Dimensions: {', '.join(self.dimensions)}")
        if self.date_range:
            parts.append(f"Date range: {self.date_range}")
        if self.visualization_type:
            parts.append(f"Current visualization: {self.visualization_type}")
        if self.last_sql:
            # Truncate SQL to keep prompt short
            sql_preview = self.last_sql[:300]
            parts.append(f"Last SQL: {sql_preview}")

        return "\n".join(parts) if parts else "None"

    def update_from_turn(
        self,
        question: str,
        sql: Optional[str],
        tables: Optional[list[str]],
        viz_type: Optional[str] = None,
    ) -> None:
        """Update memory with data from a completed turn."""
        self.turn_count += 1
        self.last_question = question
        self.last_sql = sql

        if tables:
            # Merge, keeping unique, most recent first
            seen = set()
            merged = []
            for t in tables + self.tables:
                if t not in seen:
                    seen.add(t)
                    merged.append(t)
            self.tables = merged[:10]

        if viz_type:
            self.visualization_type = viz_type

        # Extract entities from SQL if available
        if sql:
            self._extract_from_sql(sql)

        # Extract date references from question
        self._extract_dates(question)

    def _extract_from_sql(self, sql: str) -> None:
        """Extract columns, filters, metrics from SQL using regex heuristics."""
        sql_upper = sql.upper()

        # Extract column names from SELECT clause
        select_match = re.search(r"SELECT\s+(.*?)\s+FROM", sql, re.IGNORECASE | re.DOTALL)
        if select_match:
            select_clause = select_match.group(1)
            # Find column references (word.word or just word)
            col_refs = re.findall(r"(?:\w+\.)?(\w+)\s+(?:AS\s+)?", select_clause, re.IGNORECASE)
            if col_refs:
                self.columns = list(dict.fromkeys(col_refs))[:15]

        # Extract aggregation metrics
        agg_matches = re.findall(
            r"(SUM|AVG|COUNT|MAX|MIN)\s*\(\s*(?:\w+\.)?(\w+)\s*\)",
            sql, re.IGNORECASE,
        )
        if agg_matches:
            self.metrics = list(dict.fromkeys(
                f"{func.upper()}({col})" for func, col in agg_matches
            ))

        # Extract GROUP BY dimensions
        group_match = re.search(r"GROUP\s+BY\s+(.*?)(?:ORDER|HAVING|LIMIT|$)", sql, re.IGNORECASE | re.DOTALL)
        if group_match:
            dims = re.findall(r"(?:\w+\.)?(\w+)", group_match.group(1))
            self.dimensions = list(dict.fromkeys(dims))[:5]

        # Extract WHERE filters (simplified)
        where_match = re.search(r"WHERE\s+(.*?)(?:GROUP|ORDER|LIMIT|$)", sql, re.IGNORECASE | re.DOTALL)
        if where_match:
            where_clause = where_match.group(1).strip()
            # Split on AND/OR, take first few
            filter_parts = re.split(r"\s+AND\s+|\s+OR\s+", where_clause, flags=re.IGNORECASE)
            self.filters = [f.strip()[:80] for f in filter_parts if f.strip()][:5]

    def _extract_dates(self, question: str) -> None:
        """Extract date range references from the question."""
        q_lower = question.lower()

        # Year patterns
        year_matches = re.findall(r"\b(20[12]\d)\b", question)
        if year_matches:
            if len(year_matches) >= 2:
                self.date_range = f"{year_matches[0]} to {year_matches[-1]}"
            else:
                self.date_range = year_matches[0]

        # Quarter patterns
        quarter_matches = re.findall(r"\b(Q[1-4])\b", question, re.IGNORECASE)
        if quarter_matches:
            q_str = ", ".join(q.upper() for q in quarter_matches)
            if self.date_range:
                self.date_range = f"{q_str} {self.date_range}"
            else:
                self.date_range = q_str

        # Relative date patterns
        for pattern, label in [
            (r"last\s+(\d+)\s+days?", "last N days"),
            (r"last\s+month", "last month"),
            (r"this\s+year", "this year"),
            (r"last\s+year", "last year"),
            (r"this\s+quarter", "this quarter"),
            (r"last\s+quarter", "last quarter"),
        ]:
            if re.search(pattern, q_lower):
                self.date_range = label
                break
