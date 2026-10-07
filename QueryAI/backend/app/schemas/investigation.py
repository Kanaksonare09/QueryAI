from __future__ import annotations
import uuid
from typing import Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime

class EvidenceItem(BaseModel):
    dimension: str
    sql: str
    results: list[dict[str, Any]]
    
class InvestigationRequest(BaseModel):
    question: str
    conversation_id: Optional[uuid.UUID] = None

class RootCauseCandidateSchema(BaseModel):
    driver_name: str
    contribution_percent: float
    confidence: str
    explanation: str

class InvestigationResponse(BaseModel):
    investigation_id: uuid.UUID
    conversation_id: uuid.UUID
    question: str
    baseline_summary: str
    candidates: list[RootCauseCandidateSchema]
    final_insight: str
    evidence: list[EvidenceItem]
    status: str
    error_message: Optional[str] = None
