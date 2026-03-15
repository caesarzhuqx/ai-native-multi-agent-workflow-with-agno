from __future__ import annotations

from pydantic import BaseModel, Field

from app.models.metrics import WorkflowMetrics
from app.models.outputs import (
    ActionGenerationResult,
    ClassificationResult,
    EvaluationResult,
    OperatorSummary,
    RecommendedAction,
    ReviewResult,
    ValidationIssue,
)
from app.models.records import PipelineRecord


class RevOpsWorkflowState(BaseModel):
    run_id: str
    input_path: str = ""
    input_records: list[PipelineRecord] = Field(default_factory=list)
    validated_records: list[PipelineRecord] = Field(default_factory=list)
    validation_issues: list[ValidationIssue] = Field(default_factory=list)
    classifications: list[ClassificationResult] = Field(default_factory=list)
    actions: list[RecommendedAction] = Field(default_factory=list)
    action_generation: ActionGenerationResult | None = None
    review: ReviewResult | None = None
    evaluation: EvaluationResult | None = None
    summary: OperatorSummary | None = None
    output_dir: str = "demo"
    metrics: WorkflowMetrics
