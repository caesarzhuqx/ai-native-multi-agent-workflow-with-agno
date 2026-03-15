from __future__ import annotations

from pathlib import Path
from typing import Any

from agno.workflow import Step, Workflow
from agno.workflow.types import StepInput, StepOutput

from app.workflows.revops_workflow import run_workflow


def create_agentos_workflow() -> Workflow:
    return Workflow(
        name="revops_triage_agentos_workflow",
        description="Run the RevOps triage workflow through AgentOS using a simple input payload.",
        steps=[
            Step(
                name="run_revops_triage",
                executor=_run_revops_triage,
            )
        ],
    )


def _run_revops_triage(step_input: StepInput) -> StepOutput:
    payload = step_input.input if isinstance(step_input.input, dict) else {}
    input_path = str(payload.get("input_path") or Path("data") / "sample_pipeline.csv")
    output_dir = str(payload.get("output_dir") or "demo")

    state = run_workflow(input_path=input_path, output_dir=output_dir)
    content: dict[str, Any] = {
        "run_id": state.run_id,
        "input_path": input_path,
        "output_dir": output_dir,
        "summary_headline": state.summary.headline if state.summary else None,
        "top_actions": state.summary.top_actions if state.summary else [],
        "evaluation_score": state.evaluation.score if state.evaluation else None,
        "artifacts": {
            "actions_json": str(Path(output_dir) / "prioritized_actions.json"),
            "summary_markdown": str(Path(output_dir) / "operator_summary.md"),
            "evaluation_markdown": str(Path(output_dir) / "evaluation_report.md"),
        },
    }
    return StepOutput(step_name="run_revops_triage", content=content)
