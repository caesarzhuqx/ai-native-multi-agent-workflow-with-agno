from app.models.metrics import WorkflowMetrics
from app.models.outputs import OperatorSummary, PriorityLevel, RecommendedAction, ReviewResult
from app.models.state import RevOpsWorkflowState
from app.tools.evaluation import evaluate_workflow_output
from app.tools.logging import utc_now


def test_evaluation_harness_scores_expected_checks():
    state = RevOpsWorkflowState(
        run_id="demo",
        metrics=WorkflowMetrics(run_started_at=utc_now()),
        actions=[
            RecommendedAction(
                record_id="O-1",
                priority_level=PriorityLevel.P1,
                score=90,
                recommended_owner="Alicia",
                next_action="Alicia should schedule the buyer meeting today and log the dated next step in CRM by 2026-03-20.",
                reason="Highest priority because the close window is near without a committed next step.",
                business_rationale="Near-close slippage risk is high enough to justify operator escalation.",
                operator_note="Escalate in manager review and confirm the next step today.",
                confidence=0.9,
                escalation_required=True,
            )
        ],
        review=ReviewResult(approved=True, review_summary="Approved."),
        summary=OperatorSummary(
            headline="Demo",
            top_actions=["O-1"],
            risks=["risk"],
            data_quality_notes=["none"],
            manager_notes=["manager"],
        ),
    )

    result = evaluate_workflow_output(state)

    assert result.passed_checks == result.total_checks
