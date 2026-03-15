from __future__ import annotations

from dataclasses import dataclass

from app.models.outputs import ClassificationResult
from app.models.records import PipelineRecord
from app.tools.scoring import classify_record


@dataclass
class ClassificationAgent:
    name: str = "classification_agent"

    def run(self, records: list[PipelineRecord]) -> list[ClassificationResult]:
        return [classify_record(record) for record in records]
