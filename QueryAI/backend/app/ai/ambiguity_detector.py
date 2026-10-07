"""
QueryAI — Ambiguity Detection.

Detects when a user's question is too vague to generate accurate SQL.
Returns clarification options so the system can ask before guessing.

Rules:
  - Only trigger clarification when truly ambiguous
  - Don't ask unnecessary questions that frustrate users
  - Offer specific, actionable options
"""
from __future__ import annotations

import re
from typing import Optional

from pydantic import BaseModel, Field

from app.conversation.memory import ConversationMemory
from app.core.logging import get_logger

log = get_logger(__name__)


class ClarificationOption(BaseModel):
    """A single clarification option presented to the user."""
    label: str
    value: str
    description: Optional[str] = None


class AmbiguityResult(BaseModel):
    """Result of ambiguity detection."""
    is_ambiguous: bool = False
    ambiguity_type: Optional[str] = None
    message: Optional[str] = None
    options: list[ClarificationOption] = Field(default_factory=list)
    original_question: str = ""


# ── Ambiguity detection rules ─────────────────────────────────────────────────

_UNDEFINED_METRIC_PATTERNS = [
    # "best customers" without defining "best"
    (
        r"\b(best|top|worst|bottom)\s+(customer|client|buyer)s?\b",
        lambda q: not re.search(
            r"\b(revenue|sales|order|amount|quantity|count|value|profit|lifetime)\b",
            q, re.IGNORECASE,
        ),
        'How should I define "best customers"?',
        [
            ClarificationOption(label="Highest total revenue", value="highest total revenue", description="Customers who spent the most"),
            ClarificationOption(label="Most orders", value="most orders", description="Customers with the most order count"),
            ClarificationOption(label="Highest average order value", value="highest average order value", description="Customers with the largest per-order spend"),
            ClarificationOption(label="Highest lifetime value", value="highest lifetime value", description="Based on the lifetime_value field"),
        ],
    ),
    # "best products" without metric
    (
        r"\b(best|top|worst|bottom)\s+(product|item)s?\b",
        lambda q: not re.search(
            r"\b(revenue|sales|sold|quantity|profit|margin|popular|ordered)\b",
            q, re.IGNORECASE,
        ),
        'How should I define "best products"?',
        [
            ClarificationOption(label="Highest revenue", value="highest revenue", description="Total sales amount"),
            ClarificationOption(label="Most units sold", value="most units sold", description="Total quantity ordered"),
            ClarificationOption(label="Highest profit margin", value="highest profit margin", description="(unit_price - cost_price) / unit_price"),
            ClarificationOption(label="Most orders", value="most orders", description="Appears in the most orders"),
        ],
    ),
    # "best employees/salespeople" without metric
    (
        r"\b(best|top|worst|bottom)\s+(employee|salesperson|sales\s*rep|staff)s?\b",
        lambda q: not re.search(
            r"\b(revenue|sales|order|deal|closed|amount|commission)\b",
            q, re.IGNORECASE,
        ),
        'How should I define "best employees"?',
        [
            ClarificationOption(label="Highest sales revenue", value="highest sales revenue", description="Total order value handled"),
            ClarificationOption(label="Most deals closed", value="most deals closed", description="Number of completed orders"),
            ClarificationOption(label="Highest salary", value="highest salary", description="By compensation"),
        ],
    ),
]

_UNDEFINED_TIME_PATTERNS = [
    # "recent orders" without time frame
    (
        r"\brecent\s+(order|sale|transaction|purchase)s?\b",
        lambda q: not re.search(
            r"\b(\d+\s*(day|week|month|year)|last\s*(week|month|year|quarter)|20[12]\d)\b",
            q, re.IGNORECASE,
        ),
        'What period should "recent" cover?',
        [
            ClarificationOption(label="Last 7 days", value="last 7 days"),
            ClarificationOption(label="Last 30 days", value="last 30 days"),
            ClarificationOption(label="Last 90 days", value="last 90 days"),
            ClarificationOption(label="This year", value="this year"),
        ],
    ),
    # "lately" or "recently" without time frame
    (
        r"\b(lately|recently)\b",
        lambda q: not re.search(
            r"\b(\d+\s*(day|week|month|year)|last\s*(week|month|year|quarter)|20[12]\d)\b",
            q, re.IGNORECASE,
        ),
        'What time period do you mean?',
        [
            ClarificationOption(label="Last 7 days", value="last 7 days"),
            ClarificationOption(label="Last 30 days", value="last 30 days"),
            ClarificationOption(label="Last quarter", value="last quarter"),
            ClarificationOption(label="Last year", value="last year"),
        ],
    ),
]

_UNCLEAR_COMPARISON_PATTERNS = [
    # "compare" without clear dimensions
    (
        r"\bcompare\b",
        lambda q: not re.search(
            r"\b(region|product|category|customer|employee|month|quarter|year|department)\b",
            q, re.IGNORECASE,
        ),
        "What would you like to compare?",
        [
            ClarificationOption(label="By region", value="by region"),
            ClarificationOption(label="By product category", value="by product category"),
            ClarificationOption(label="By customer segment", value="by customer segment"),
            ClarificationOption(label="By time period", value="by time period"),
        ],
    ),
]


def detect_ambiguity(
    question: str,
    memory: Optional[ConversationMemory] = None,
) -> AmbiguityResult:
    """
    Check if a question is ambiguous and needs clarification.

    If there's existing conversation context (memory), some ambiguities
    may be resolved by prior context — skip those.
    """
    q_lower = question.lower().strip()

    # If the question is very short (< 3 words), it's likely a follow-up
    # and context should resolve it
    word_count = len(q_lower.split())
    if word_count < 3 and memory and memory.turn_count > 0:
        return AmbiguityResult(is_ambiguous=False, original_question=question)

    # Check all pattern groups
    all_patterns = (
        _UNDEFINED_METRIC_PATTERNS
        + _UNDEFINED_TIME_PATTERNS
        + _UNCLEAR_COMPARISON_PATTERNS
    )

    for pattern, condition_fn, message, options in all_patterns:
        if re.search(pattern, q_lower, re.IGNORECASE):
            if condition_fn(q_lower):
                # Check if conversation memory already resolves this
                if memory and memory.turn_count > 0:
                    # If memory has active metrics/filters, don't re-ask
                    if memory.metrics and "metric" in message.lower():
                        continue
                    if memory.date_range and "period" in message.lower():
                        continue

                log.info("Ambiguity detected", question=question[:60], message=message)
                return AmbiguityResult(
                    is_ambiguous=True,
                    ambiguity_type=_classify_ambiguity_type(message),
                    message=message,
                    options=options,
                    original_question=question,
                )

    return AmbiguityResult(is_ambiguous=False, original_question=question)


def _classify_ambiguity_type(message: str) -> str:
    """Classify the type of ambiguity for logging/analytics."""
    msg_lower = message.lower()
    if "define" in msg_lower or "best" in msg_lower:
        return "undefined_metric"
    if "period" in msg_lower or "time" in msg_lower or "recent" in msg_lower:
        return "unclear_date_range"
    if "compare" in msg_lower:
        return "unclear_comparison"
    return "general"


def resolve_ambiguity(
    original_question: str,
    selected_option: str,
) -> str:
    """
    Combine the original question with the user's clarification choice
    to form a more specific question.
    """
    # Simple approach: append the clarification
    return f"{original_question} ({selected_option})"
