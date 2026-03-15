from __future__ import annotations

import json
from pathlib import Path

from app.models.state import RevOpsWorkflowState


def write_outputs(state: RevOpsWorkflowState) -> tuple[Path, Path]:
    output_dir = Path(state.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    json_path = output_dir / "prioritized_actions.json"
    markdown_path = output_dir / "operator_summary.md"
    evaluation_path = output_dir / "evaluation_report.md"

    json_payload = [action.model_dump(mode="json") for action in state.actions]
    json_path.write_text(json.dumps(json_payload, indent=2), encoding="utf-8")
    markdown_path.write_text(build_summary_markdown(state), encoding="utf-8")
    evaluation_path.write_text(build_evaluation_markdown(state), encoding="utf-8")
    return json_path, markdown_path


def build_summary_markdown(state: RevOpsWorkflowState) -> str:
    summary = state.summary
    headline = summary.headline if summary else "RevOps daily triage summary"
    top_actions = summary.top_actions if summary else []
    risks = summary.risks if summary else []
    quality_notes = summary.data_quality_notes if summary else []
    manager_notes = summary.manager_notes if summary else []
    review_summary = state.review.review_summary if state.review else "No review summary available."
    action_mode = state.action_generation.generation_mode if state.action_generation else "unknown"
    model_name = state.action_generation.model_name if state.action_generation else None

    def _section(title: str, items: list[str]) -> str:
        lines = "\n".join(f"- {item}" for item in items) if items else "- None"
        return f"## {title}\n{lines}\n"

    return (
        f"# {headline}\n\n"
        f"_Generated from {len(state.validated_records)} validated records._\n\n"
        f"Action generation mode: `{action_mode}`"
        f"{f' via {model_name}' if model_name else ''}\n\n"
        f"Review status: {review_summary}\n\n"
        f"{_section('Top Actions', top_actions)}\n"
        f"{_section('Risks', risks)}\n"
        f"{_section('Data Quality Notes', quality_notes)}\n"
        f"{_section('Manager Notes', manager_notes)}"
    )


def build_evaluation_markdown(state: RevOpsWorkflowState) -> str:
    evaluation = state.evaluation
    if evaluation is None:
        return "# Evaluation Report\n\n- No evaluation result available.\n"

    lines = "\n".join(
        f"- {'PASS' if check.passed else 'FAIL'}: {check.name} - {check.detail}" for check in evaluation.checks
    )
    return f"# Evaluation Report\n\nScore: **{evaluation.score}**\n\n{lines}\n"
