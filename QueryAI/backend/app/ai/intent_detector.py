"""
QueryAI — Intent Detection.

Classifies user intent BEFORE SQL generation so the pipeline can
take different paths (skip SQL for viz requests, ask clarification, etc.).

Uses fast heuristic rules first, falls back to LLM only when uncertain.
"""
from __future__ import annotations

import re
import json
from enum import Enum
from typing import Optional

from pydantic import BaseModel

from app.conversation.memory import ConversationMemory
from app.core.logging import get_logger

log = get_logger(__name__)


class Intent(str, Enum):
    DATA_QUERY = "data_query"
    FOLLOW_UP_QUERY = "follow_up_query"
    VISUALIZATION_REQUEST = "visualization_request"
    SQL_EXPLANATION = "sql_explanation"
    SCHEMA_QUESTION = "schema_question"
    DASHBOARD_REQUEST = "dashboard_request"
    OPTIMIZATION_REQUEST = "optimization_request"
    AMBIGUOUS_QUERY = "ambiguous_query"
    GREETING = "greeting"
    ROOT_CAUSE_ANALYSIS = "ROOT_CAUSE_ANALYSIS"


class IntentResult(BaseModel):
    intent: Intent
    confidence: float  # 0.0 to 1.0
    requires_sql_generation: bool
    requires_clarification: bool = False
    visualization_change: Optional[str] = None  # New viz type if intent is VISUALIZATION_REQUEST
    reason: str = ""


# ── Heuristic pattern sets ─────────────────────────────────────────────────────

_VIZ_PATTERNS = [
    r"\b(show|make|change|convert|switch|display)\b.*\b(bar|line|pie|donut|table|kpi|chart|graph|area|scatter)\b",
    r"\b(as a|as an?)\s+(bar|line|pie|donut|table|kpi|chart|area|scatter)\b",
    r"\bvisuali[sz]e\b",
    r"\b(bar|line|pie|donut)\s+chart\b",
]

_EXPLAIN_PATTERNS = [
    r"\bexplain\b.*\b(sql|query|this)\b",
    r"\bwhat does\b.*\b(sql|query|this)\b.*\b(do|mean)\b",
    r"\bhow does\b.*\b(query|sql)\b.*\bwork\b",
    r"\bbreak\s*down\b.*\b(sql|query)\b",
]

_SCHEMA_PATTERNS = [
    r"\b(what|which|show|list|describe)\b.*\b(table|column|schema|field|database|structure)\b",
    r"\btable\b.*\b(look like|contain|have|has)\b",
    r"\brelationship\b.*\b(between|table)\b",
    r"\bforeign key\b",
    r"\bprimary key\b",
]

_DASHBOARD_PATTERNS = [
    r"\b(create|make|build|generate|show me a)\b.*\bdashboard\b",
    r"\bdashboard\b.*\b(for|about|with)\b",
]

_OPTIMIZE_PATTERNS = [
    r"\boptimi[sz]e\b",
    r"\bperformance\b.*\b(query|sql)\b",
    r"\b(slow|fast|speed|improve)\b.*\b(query|sql)\b",
    r"\bexplain\s+plan\b",
    r"\bindex\b.*\b(suggest|recommend|need|missing)\b",
]

_GREETING_PATTERNS = [
    r"^(hi|hello|hey|good\s*(morning|afternoon|evening)|howdy|what'?s up)\s*[!?.]*$",
    r"^(thanks?|thank you|thx)\s*[!?.]*$",
]

_ROOT_CAUSE_PATTERNS = [
    r"\b(why|what caused|reason for)\b.*\b(decrease|increase|drop|fall|rise|grow|change|spike)\b",
    r"\bwhy did\b",
]

_FOLLOW_UP_INDICATORS = [
    r"^(and|but|also|what about|how about|now|then)\b",
    r"^only\b",
    r"^(filter|sort|group|limit|exclude|include|add|remove)\b",
    r"\b(same|those|these|that|them|it|the previous|the last|above)\b",
    r"\bcompare\s+(them|it|those)\b",
    r"\b(instead|rather|also)\b",
]

_VIZ_TYPES_MAP = {
    "bar": "bar",
    "line": "line",
    "pie": "pie",
    "donut": "donut",
    "table": "table",
    "kpi": "kpi",
    "area": "area",
    "scatter": "scatter",
    "chart": "bar",  # default chart type
    "graph": "bar",
}

_AMBIGUOUS_PATTERNS = [
    r"\b(best|top|worst|bottom|biggest|smallest|highest|lowest)\b(?!.*\b(revenue|sales|orders|amount|quantity|count|price|value|profit|salary|cost)\b)",
    r"\b(recent|new|old|latest|earliest)\b(?!.*\b(day|week|month|year|quarter|date|\d{4})\b)",
]


def detect_intent(
    question: str,
    memory: Optional[ConversationMemory] = None,
) -> IntentResult:
    """
    Detect user intent using fast heuristic rules.

    Priority order:
      1. Greeting (short-circuit)
      2. Visualization request (no SQL needed)
      3. SQL explanation
      4. Schema question
      5. Dashboard request
      6. Optimization request
      7. Follow-up query (has conversation context)
      8. Ambiguous query (needs clarification)
      9. Data query (default)
    """
    q = question.strip()
    q_lower = q.lower()

    # 1. Greeting
    for pattern in _GREETING_PATTERNS:
        if re.match(pattern, q_lower):
            return IntentResult(
                intent=Intent.GREETING,
                confidence=0.95,
                requires_sql_generation=False,
                reason="Detected greeting/thanks",
            )
            
    # 1.5 Root Cause Investigation
    for pattern in _ROOT_CAUSE_PATTERNS:
        if re.search(pattern, q_lower):
            return IntentResult(
                intent=Intent.ROOT_CAUSE_ANALYSIS,
                confidence=0.90,
                requires_sql_generation=False,
                reason="Detected root cause investigation",
            )

    # 2. Visualization request — only if there's prior context
    if memory and memory.turn_count > 0:
        for pattern in _VIZ_PATTERNS:
            if re.search(pattern, q_lower):
                # Extract the desired viz type
                viz_type = _extract_viz_type(q_lower)
                return IntentResult(
                    intent=Intent.VISUALIZATION_REQUEST,
                    confidence=0.90,
                    requires_sql_generation=False,
                    visualization_change=viz_type,
                    reason=f"Visualization change to {viz_type}",
                )

    # 3. SQL explanation
    for pattern in _EXPLAIN_PATTERNS:
        if re.search(pattern, q_lower):
            return IntentResult(
                intent=Intent.SQL_EXPLANATION,
                confidence=0.85,
                requires_sql_generation=False,
                reason="User asked to explain SQL",
            )

    # 4. Schema question
    for pattern in _SCHEMA_PATTERNS:
        if re.search(pattern, q_lower):
            return IntentResult(
                intent=Intent.SCHEMA_QUESTION,
                confidence=0.80,
                requires_sql_generation=False,
                reason="User asked about database schema",
            )

    # 5. Dashboard request
    for pattern in _DASHBOARD_PATTERNS:
        if re.search(pattern, q_lower):
            return IntentResult(
                intent=Intent.DASHBOARD_REQUEST,
                confidence=0.85,
                requires_sql_generation=False,
                reason="User wants a dashboard",
            )

    # 6. Optimization request
    for pattern in _OPTIMIZE_PATTERNS:
        if re.search(pattern, q_lower):
            return IntentResult(
                intent=Intent.OPTIMIZATION_REQUEST,
                confidence=0.80,
                requires_sql_generation=False,
                reason="User wants query optimization",
            )

    # 7. Follow-up query — if conversation context exists and indicators match
    if memory and memory.turn_count > 0:
        for pattern in _FOLLOW_UP_INDICATORS:
            if re.search(pattern, q_lower):
                return IntentResult(
                    intent=Intent.FOLLOW_UP_QUERY,
                    confidence=0.80,
                    requires_sql_generation=True,
                    reason="Follow-up referencing previous context",
                )

    # 8. Default: data query
    return IntentResult(
        intent=Intent.DATA_QUERY,
        confidence=0.70,
        requires_sql_generation=True,
        reason="Standard data query",
    )


def _extract_viz_type(text: str) -> str:
    """Extract the target visualization type from the question."""
    for keyword, viz_type in _VIZ_TYPES_MAP.items():
        if keyword in text:
            return viz_type
    return "bar"  # default


def detect_intent_with_llm(
    question: str,
    memory: Optional[ConversationMemory] = None,
) -> IntentResult:
    """
    LLM-based intent detection. Used as fallback when heuristics
    return low confidence. Currently unused — reserved for Phase 2.
    """
    from app.ai.llm import invoke_llm

    context = memory.to_context_string() if memory else "None"
    prompt = f"""Classify the user's intent. Return ONLY a JSON object.

Conversation context: {context}

User message: {question}

Valid intents: data_query, follow_up_query, visualization_request, sql_explanation, schema_question, dashboard_request, optimization_request, ambiguous_query, greeting

Return format: {{"intent": "...", "confidence": 0.0-1.0, "reason": "..."}}"""

    try:
        raw = invoke_llm(
            "You are an intent classifier. Output only valid JSON.",
            prompt,
            temperature=0.0,
        )
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            data = json.loads(match.group())
            intent_str = data.get("intent", "data_query")
            try:
                intent = Intent(intent_str)
            except ValueError:
                intent = Intent.DATA_QUERY

            return IntentResult(
                intent=intent,
                confidence=float(data.get("confidence", 0.6)),
                requires_sql_generation=intent in (
                    Intent.DATA_QUERY,
                    Intent.FOLLOW_UP_QUERY,
                ),
                reason=data.get("reason", "LLM classification"),
            )
    except Exception as exc:
        log.warning("LLM intent detection failed", error=str(exc))

    # Fallback to heuristics
    return detect_intent(question, memory)
