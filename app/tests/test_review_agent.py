from app.agents.review_agent import ReviewAgent
from app.models.outputs import ClassificationResult, PriorityLevel, RecommendedAction


def test_review_agent_repairs_high_priority_action():
    review_agent = ReviewAgent()
    classifications = [
        ClassificationResult(
            record_id="O-1",
            priority_level=PriorityLevel.P1,
            score=91,
            risk_flags=["stalled_stage"],
            intent_signals=[],
            evidence=["High ACV and stalled in stage."],
        )
    ]
    actions = [
        RecommendedAction(
            record_id="O-1",
            priority_level=PriorityLevel.P1,
            score=91,
            recommended_owner="Alicia",
            next_action="Call",
            reason="",
            business_rationale="",
            operator_note="",
            confidence=0.8,
            escalation_required=False,
        )
    ]

    result = review_agent.run(classifications, actions)

    assert result.repair_triggered is True
    assert result.revision_rounds == 1
    assert result.repaired_record_ids == ["O-1"]
    assert result.repaired_actions[0].escalation_required is True
    assert len(result.repaired_actions[0].next_action) >= 20
    assert result.repaired_actions[0].reason


def test_review_agent_does_not_over_repair_reasonable_p2_action():
    review_agent = ReviewAgent()
    classifications = [
        ClassificationResult(
            record_id="O-2",
            priority_level=PriorityLevel.P2,
            score=68,
            risk_flags=["stale_activity"],
            intent_signals=["budget_confirmed"],
            evidence=["No recent seller activity in 10+ days.", "Buyer indicated budget alignment."],
        )
    ]
    actions = [
        RecommendedAction(
            record_id="O-2",
            priority_level=PriorityLevel.P2,
            score=68,
            recommended_owner="Marcus",
            next_action="Marcus should move the deal to a dated commercial next step, confirm buying process, and log the update in CRM by 2026-03-17.",
            reason="Prioritized because seller activity has gone stale, while budget has been confirmed shows the record is still commercially active.",
            business_rationale="Budget appears real, so the account should be advanced to a dated commercial next step instead of sitting in queue.",
            operator_note="Check that Marcus has a dated next step in CRM before 2026-03-17.",
            confidence=0.86,
            escalation_required=False,
        )
    ]

    result = review_agent.run(classifications, actions)

    assert result.repair_triggered is False
    assert result.repaired_record_ids == []
    assert result.repaired_actions[0].next_action == actions[0].next_action
