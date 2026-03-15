from __future__ import annotations

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, Field, field_validator, model_validator


class RecordType(str, Enum):
    LEAD = "lead"
    OPPORTUNITY = "opportunity"


class PipelineStage(str, Enum):
    NEW = "new"
    QUALIFYING = "qualifying"
    DISCOVERY = "discovery"
    DEMO = "demo"
    PROPOSAL = "proposal"
    NEGOTIATION = "negotiation"
    COMMIT = "commit"
    CLOSED_WON = "closed_won"
    CLOSED_LOST = "closed_lost"
    NURTURE = "nurture"
    UNKNOWN = "unknown"


class PipelineRecord(BaseModel):
    record_id: str = Field(min_length=1)
    record_type: RecordType
    company_name: str = Field(min_length=1)
    owner: str = Field(min_length=1)
    stage: PipelineStage = PipelineStage.UNKNOWN
    source: str = Field(default="unknown")
    annual_contract_value: int = Field(default=0, ge=0)
    days_in_stage: int = Field(default=0, ge=0)
    last_activity_at: datetime | None = None
    next_step: str | None = None
    close_date: date | None = None
    contact_title: str | None = None
    notes: str = Field(default="")

    @field_validator("company_name", "owner", "source", mode="before")
    @classmethod
    def strip_text(cls, value: str | None) -> str:
        return (value or "").strip()

    @field_validator("next_step", "contact_title", "notes", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    @model_validator(mode="after")
    def normalize_stage_by_type(self) -> "PipelineRecord":
        if self.record_type == RecordType.LEAD and self.stage == PipelineStage.UNKNOWN:
            self.stage = PipelineStage.NEW
        return self
