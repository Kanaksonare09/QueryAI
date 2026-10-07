"""
QueryAI — Query Planner.

Creates a structured query plan BEFORE SQL generation.
The plan helps the SQL generator understand the task and
produces more accurate queries.

Uses Pydantic models for structured output.
"""
from __future__ import annotations

import json
import re
from typing import Optional

from pydantic import BaseModel, Field

from app.conversation.memory import ConversationMemory
from app.ai.llm import invoke_llm
from app.core.logging import get_logger

log = get_logger(__name__)


class QueryPlan(BaseModel):
    """Structured representation of what the user wants."""

    intent: str = Field(description="Type: comparison, trend, ranking, aggregation, detail, filter")
    metric: Optional[str] = Field(None, description="Primary metric (e.g. revenue, order count)")
    dimensions: list[str] = Field(default_factory=list, description="Grouping dimensions")
    filters: list[str] = Field(default_factory=list, description="Filter conditions in natural language")
    sort_by: Optional[str] = Field(None, description="Sort column/metric")
    sort_order: str = Field("desc", description="asc or desc")
    limit: Optional[int] = Field(None, description="Row limit")
    required_tables: list[str] = Field(default_factory=list, description="Tables needed")
    time_period: Optional[str] = Field(None, description="Date range if applicable")
    visualization: Optional[str] = Field(None, description="Suggested chart type")
    confidence_notes: list[str] = Field(default_factory=list, description="Potential ambiguities")


QUERY_PLAN_SYSTEM = """You are a query planning assistant. Given a user question and database context, create a structured query plan.

Output ONLY a JSON object with this structure (no explanation, no markdown):
{
  "intent": "comparison|trend|ranking|aggregation|detail|filter",
  "metric": "primary metric name or null",
  "dimensions": ["grouping columns"],
  "filters": ["filter conditions in plain English"],
  "sort_by": "sort column or null",
  "sort_order": "asc|desc",
  "limit": null or integer,
  "required_tables": ["table names needed"],
  "time_period": "date range or null",
  "visualization": "bar|line|pie|table|kpi or null",
  "confidence_notes": ["any ambiguities or assumptions"]
}"""

QUERY_PLAN_HUMAN = """Available tables: {available_tables}

Conversation context:
{context}

User question: {question}

Create the query plan:"""


def create_query_plan(
    question: str,
    available_tables: list[str],
    memory: Optional[ConversationMemory] = None,
) -> QueryPlan:
    """
    Generate a structured query plan.

    Tries LLM first, falls back to heuristic plan on failure.
    """
    context = memory.to_context_string() if memory else "None"

    try:
        human = QUERY_PLAN_HUMAN.format(
            available_tables=", ".join(available_tables),
            context=context,
            question=question,
        )
        raw = invoke_llm(QUERY_PLAN_SYSTEM, human, temperature=0.0)

        # Extract JSON
        json_match = re.search(r"\{.*\}", raw, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group())
            plan = QueryPlan(**data)
            log.info("Query plan created", intent=plan.intent, tables=plan.required_tables)
            return plan

    except Exception as exc:
        log.warning("LLM query planning failed, using heuristic", error=str(exc))

    # Heuristic fallback
    return _heuristic_plan(question, available_tables, memory)


def _heuristic_plan(
    question: str,
    available_tables: list[str],
    memory: Optional[ConversationMemory] = None,
) -> QueryPlan:
    """Rule-based query plan when LLM is unavailable."""
    q_lower = question.lower()

    # Detect intent
    intent = "detail"
    if any(w in q_lower for w in ["compare", "vs", "versus", "between"]):
        intent = "comparison"
    elif any(w in q_lower for w in ["trend", "over time", "monthly", "weekly", "daily", "growth"]):
        intent = "trend"
    elif any(w in q_lower for w in ["top", "best", "worst", "highest", "lowest", "rank"]):
        intent = "ranking"
    elif any(w in q_lower for w in ["total", "sum", "average", "count", "how many"]):
        intent = "aggregation"
    elif any(w in q_lower for w in ["filter", "where", "only", "specific"]):
        intent = "filter"

    # Detect metric
    metric = None
    for m in ["revenue", "sales", "amount", "orders", "quantity", "profit", "salary", "cost", "value"]:
        if m in q_lower:
            metric = m
            break

    # Detect limit
    limit = None
    limit_match = re.search(r"\b(?:top|bottom|first|last)\s+(\d+)\b", q_lower)
    if limit_match:
        limit = int(limit_match.group(1))

    # Detect time period
    time_period = None
    year_match = re.findall(r"\b(20[12]\d)\b", question)
    if year_match:
        time_period = " to ".join(year_match) if len(year_match) > 1 else year_match[0]

    # Detect visualization
    viz = None
    if intent == "trend":
        viz = "line"
    elif intent == "comparison":
        viz = "bar"
    elif intent == "ranking":
        viz = "bar"
    elif intent == "aggregation" and not limit:
        viz = "kpi"

    return QueryPlan(
        intent=intent,
        metric=metric,
        dimensions=[],
        filters=[],
        sort_order="desc" if intent in ("ranking",) else "desc",
        limit=limit,
        required_tables=available_tables[:5],
        time_period=time_period,
        visualization=viz,
        confidence_notes=[],
    )


def plan_to_prompt_context(plan: QueryPlan) -> str:
    """Convert a query plan to a compact string for the SQL generation prompt."""
    parts = [f"Query type: {plan.intent}"]

    if plan.metric:
        parts.append(f"Primary metric: {plan.metric}")
    if plan.dimensions:
        parts.append(f"Group by: {', '.join(plan.dimensions)}")
    if plan.filters:
        parts.append(f"Filters: {', '.join(plan.filters)}")
    if plan.time_period:
        parts.append(f"Time period: {plan.time_period}")
    if plan.limit:
        parts.append(f"Limit: {plan.limit}")
    if plan.sort_by:
        parts.append(f"Sort: {plan.sort_by} {plan.sort_order}")

    return "\n".join(parts)
