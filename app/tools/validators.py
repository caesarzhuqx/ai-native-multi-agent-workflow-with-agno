from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable

from pydantic import ValidationError

from app.models.outputs import ValidationIssue
from app.models.records import PipelineRecord


REQUIRED_COLUMNS = {
    "record_id",
    "record_type",
    "company_name",
    "owner",
    "stage",
    "source",
    "annual_contract_value",
    "days_in_stage",
    "last_activity_at",
    "next_step",
    "close_date",
    "contact_title",
    "notes",
}


def load_pipeline_records(path: str | Path) -> tuple[list[PipelineRecord], list[ValidationIssue]]:
    csv_path = Path(path)
    rows = list(csv.DictReader(csv_path.open("r", encoding="utf-8-sig", newline="")))
    return validate_pipeline_rows(rows)


def validate_pipeline_rows(rows: Iterable[dict[str, str]]) -> tuple[list[PipelineRecord], list[ValidationIssue]]:
    valid_records: list[PipelineRecord] = []
    issues: list[ValidationIssue] = []

    for index, row in enumerate(rows):
        missing_keys = REQUIRED_COLUMNS.difference(row.keys())
        if missing_keys:
            issues.append(
                ValidationIssue(
                    record_id=row.get("record_id"),
                    severity="error",
                    message=f"Row {index + 1} missing columns: {sorted(missing_keys)}",
                )
            )
            continue

        try:
            record = PipelineRecord.model_validate(row)
            valid_records.append(record)
        except ValidationError as exc:
            issues.append(
                ValidationIssue(
                    record_id=row.get("record_id"),
                    severity="error",
                    message=exc.errors()[0]["msg"],
                )
            )

    return valid_records, issues
