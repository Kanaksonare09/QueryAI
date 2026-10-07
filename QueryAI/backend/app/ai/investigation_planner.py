"""
QueryAI — Investigation Planner for Root-Cause Analysis Mode.
Generates structured investigation plans to find root causes of metric changes.
"""
from typing import Any, Optional
from pydantic import BaseModel, Field

from app.ai.llm import invoke_structured_llm
from app.conversation.memory import ConversationMemory
from app.core.exceptions import LLMError
from app.core.logging import get_logger

log = get_logger(__name__)


class InvestigationPlan(BaseModel):
    target_metric: str = Field(description="The primary metric being investigated (e.g. revenue, orders)")
    comparison: str = Field(description="The comparison being made (e.g. Q3 vs Q2, this month vs last month)")
    investigations: list[str] = Field(description="List of dimensions to investigate (e.g. region, product, customer_segment)")
    explanation: str = Field(description="Why this investigation plan makes sense")


_INVESTIGATION_SYSTEM = """You are an expert data analyst investigating root causes of business metric changes.
Given a user's causal question, the available schema, and conversation context, your job is to output a structured investigation plan.

RULES:
1. Identify the target metric.
2. Identify the comparison period or condition.
3. Select up to 5 reasonable dimensions from the schema to break down the metric and find the driver.
4. Only select dimensions that actually exist or can be derived from the provided tables.
"""

_INVESTIGATION_HUMAN = """DATABASE TABLES:
{schema_tables}

CONVERSATION CONTEXT:
{context}

QUESTION:
{question}

Generate the investigation plan."""


def create_investigation_plan(
    question: str, 
    tables: list[str], 
    memory: ConversationMemory
) -> InvestigationPlan:
    """Creates a structured plan for investigating a metric change."""
    prompt = _INVESTIGATION_HUMAN.format(
        schema_tables=", ".join(tables),
        context=memory.to_context_string(),
        question=question,
    )
    
    try:
        plan_dict = invoke_structured_llm(
            system_prompt=_INVESTIGATION_SYSTEM,
            human_prompt=prompt,
            response_schema=InvestigationPlan.model_json_schema()
        )
        plan = InvestigationPlan(**plan_dict)
        log.info("Investigation plan created", metric=plan.target_metric, investigations=plan.investigations)
        return plan
    except Exception as exc:
        log.error("Failed to create investigation plan", error=str(exc))
        raise LLMError("Failed to formulate an investigation plan.") from exc
