from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class AgentTrace(BaseModel):
    agent_name: str
    started_at: datetime
    ended_at: datetime
    latency_ms: int
    success: bool
    retries: int = 0
    generation_mode: str | None = None
    model_name: str | None = None
    token_input: int | None = None
    token_output: int | None = None
    repair_triggered: bool = False
    error_message: str | None = None


class WorkflowMetrics(BaseModel):
    run_started_at: datetime
    run_ended_at: datetime | None = None
    total_latency_ms: int | None = None
    success: bool = False
    traces: list[AgentTrace] = Field(default_factory=list)
