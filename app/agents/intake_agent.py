from __future__ import annotations

from dataclasses import dataclass

from app.models.outputs import ValidationIssue
from app.models.records import PipelineRecord
from app.tools.validators import load_pipeline_records


@dataclass
class IntakeAgent:
    name: str = "intake_coordinator"

    def run(self, input_path: str) -> tuple[list[PipelineRecord], list[ValidationIssue]]:
        return load_pipeline_records(input_path)
