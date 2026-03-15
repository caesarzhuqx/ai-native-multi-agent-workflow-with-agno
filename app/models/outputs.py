from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class PriorityLevel(str, Enum):
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class ValidationIssue(BaseModel):
    record_id: str | None = None
    severity: str = Field(default="warning")
    message: str


class ClassificationResult(BaseModel):
    record_id: str
    priority_level: PriorityLevel
    score: int = Field(ge=0, le=100)
    risk_flags: list[str] = Field(default_factory=list)
    intent_signals: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)


class RecommendedAction(BaseModel):
    record_id: str
    priority_level: PriorityLevel
    score: int = Field(ge=0, le=100)
    recommended_owner: str
    due_date: date | None = None
    next_action: str
    reason: str
    business_rationale: str
    operator_note: str
    confidence: float = Field(ge=0.0, le=1.0)
    escalation_required: bool = False


class ActionGenerationResult(BaseModel):
    actions: list[RecommendedAction] = Field(default_factory=list)
    generation_mode: Literal["rules", "agno"] = "rules"
    model_name: str | None = None
    token_input: int | None = None
    token_output: int | None = None


class ReviewResult(BaseModel):
    approved: bool
    issues: list[str] = Field(default_factory=list)
    repaired_actions: list[RecommendedAction] = Field(default_factory=list)
    repair_triggered: bool = False
    repaired_record_ids: list[str] = Field(default_factory=list)
    revision_rounds: int = 0
    review_summary: str = ""


class OperatorSummary(BaseModel):
    headline: str
    top_actions: list[str]
    risks: list[str]
    data_quality_notes: list[str]
    manager_notes: list[str]


class EvaluationCheck(BaseModel):
    name: str
    passed: bool
    detail: str


class EvaluationResult(BaseModel):
    score: str
    passed_checks: int
    total_checks: int
    checks: list[EvaluationCheck] = Field(default_factory=list)
