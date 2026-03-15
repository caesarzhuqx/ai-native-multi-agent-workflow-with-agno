from __future__ import annotations

from app.models.outputs import EvaluationCheck, EvaluationResult
from app.models.state import RevOpsWorkflowState


def evaluate_workflow_output(state: RevOpsWorkflowState) -> EvaluationResult:
    checks: list[EvaluationCheck] = []

    checks.append(
        EvaluationCheck(
            name="sorted_output",
            passed=_is_sorted(state),
            detail="Actions should be sorted by priority and score in final output.",
        )
    )
    checks.append(
        EvaluationCheck(
            name="p1_escalation_alignment",
            passed=all(action.escalation_required for action in state.actions if action.priority_level.value == "P1"),
            detail="All P1 actions should require escalation.",
        )
    )
    checks.append(
        EvaluationCheck(
            name="concrete_actions",
            passed=all(_looks_concrete(action.next_action) for action in state.actions[:5]),
            detail="Top actions should contain an owner, concrete step, and timing cue.",
        )
    )
    checks.append(
        EvaluationCheck(
            name="review_completed",
            passed=state.review is not None,
            detail="Workflow should include a review step before final output.",
        )
    )
    checks.append(
        EvaluationCheck(
            name="typed_artifacts_present",
            passed=state.summary is not None and len(state.actions) > 0,
            detail="Workflow should produce both structured actions and an operator summary.",
        )
    )

    passed_checks = sum(1 for check in checks if check.passed)
    score = f"{passed_checks}/{len(checks)}"
    return EvaluationResult(
        score=score,
        passed_checks=passed_checks,
        total_checks=len(checks),
        checks=checks,
    )


def _is_sorted(state: RevOpsWorkflowState) -> bool:
    priority_rank = {"P1": 0, "P2": 1, "P3": 2}
    expected = sorted(
        state.actions,
        key=lambda action: (
            priority_rank[action.priority_level.value],
            -action.score,
            -action.confidence,
            action.record_id,
        ),
    )
    return [action.record_id for action in state.actions] == [action.record_id for action in expected]


def _looks_concrete(next_action: str) -> bool:
    lowered = next_action.lower()
    return "should" in lowered and any(token in lowered for token in ["today", "24 hours", "by "])
