"""
QueryAI — Driver Analysis for Root-Cause Investigation Mode.
Takes baseline metrics and dimensional breakdowns to determine the top contributing drivers.
"""
from typing import Any
from pydantic import BaseModel, Field

from app.ai.llm import invoke_structured_llm
from app.core.logging import get_logger

log = get_logger(__name__)


class DriverCandidate(BaseModel):
    driver_name: str = Field(description="Name of the driver (e.g. 'Europe Revenue', 'Product A Sales')")
    contribution_percent: float = Field(description="Percentage contribution to the overall change (0-100)")
    confidence: str = Field(description="Confidence level (High, Medium, Low)")
    explanation: str = Field(description="Explanation of how this driver contributed")


class RootCauseReport(BaseModel):
    baseline_summary: str = Field(description="Summary of the overall change (e.g. Revenue declined 18%...)")
    candidates: list[DriverCandidate] = Field(description="Ranked list of top contributing drivers")
    final_insight: str = Field(description="Final evidence-backed explanation")


_ANALYSIS_SYSTEM = """You are an expert AI data analyst.
You will be provided with baseline metrics (the overall change) and investigation evidence (how various segments performed).
Your job is to identify the top drivers of the change and output a structured root-cause report.

RULES:
1. NEVER invent or fabricate percentages. Calculate or infer them ONLY from the provided evidence.
2. If the data shows correlation but not causation, be clear about it in the explanation.
3. Keep the final insight concise and backed purely by the evidence.
4. Rank the candidates by their contribution to the change.
"""

_ANALYSIS_HUMAN = """BASELINE CHANGE:
{baseline_data}

INVESTIGATION EVIDENCE (Breakdowns):
{evidence_data}

Generate the root cause driver analysis report."""


def analyze_drivers(
    baseline_data: str, 
    evidence_data: str
) -> RootCauseReport:
    """Analyzes investigation evidence to determine root causes."""
    prompt = _ANALYSIS_HUMAN.format(
        baseline_data=baseline_data,
        evidence_data=evidence_data,
    )
    
    try:
        report_dict = invoke_structured_llm(
            system_prompt=_ANALYSIS_SYSTEM,
            human_prompt=prompt,
            response_schema=RootCauseReport.model_json_schema()
        )
        report = RootCauseReport(**report_dict)
        log.info("Driver analysis complete", candidates=len(report.candidates))
        return report
    except Exception as exc:
        log.error("Failed to analyze drivers", error=str(exc))
        # Fallback empty report
        return RootCauseReport(
            baseline_summary="Could not complete driver analysis.",
            candidates=[],
            final_insight="An error occurred while analyzing the root cause evidence."
        )
