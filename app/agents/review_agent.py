from __future__ import annotations

from dataclasses import dataclass

from app.models.outputs import ClassificationResult, RecommendedAction, ReviewResult


@dataclass
class ReviewAgent:
    name: str = "review_agent"

    def run(
        self,
        classifications: list[ClassificationResult],
        actions: list[RecommendedAction],
    ) -> ReviewResult:
        issues: list[str] = []
        repaired_actions = list(actions)
        repaired_record_ids: list[str] = []
        class_by_id = {classification.record_id: classification for classification in classifications}

        for index, action in enumerate(repaired_actions):
            classification = class_by_id[action.record_id]
            if classification.priority_level != action.priority_level:
                issues.append(f"{action.record_id}: action priority does not match classification.")
                repaired_actions[index] = action.model_copy(
                    update={"priority_level": classification.priority_level, "score": classification.score}
                )
                repaired_record_ids.append(action.record_id)

            risk_summary = self._risk_summary(classification)

            if not self._is_concrete_action(repaired_actions[index].next_action):
                issues.append(f"{action.record_id}: next action is not concrete enough.")
                repaired_actions[index] = repaired_actions[index].model_copy(
                    update={
                        "next_action": (
                            f"{repaired_actions[index].recommended_owner} should update CRM with a dated next step, "
                            f"contact the buyer with a concrete follow-up, and close the loop within 24 hours."
                        ),
                        "operator_note": (
                            "Operator should confirm that the owner leaves a dated next step and a documented buyer response window."
                        ),
                    }
                )
                repaired_record_ids.append(action.record_id)

            if not repaired_actions[index].reason.strip():
                issues.append(f"{action.record_id}: missing reason.")
                repaired_actions[index] = repaired_actions[index].model_copy(
                    update={
                        "reason": "Reviewer inserted a reason because the original action omitted one.",
                        "business_rationale": "Reviewer repaired the rationale so the recommendation remains auditable.",
                    }
                )
                repaired_record_ids.append(action.record_id)

            elif classification.risk_flags and not self._reason_reflects_risks(repaired_actions[index].reason, classification):
                issues.append(f"{action.record_id}: reason does not reflect the primary risk profile.")
                repaired_actions[index] = repaired_actions[index].model_copy(
                    update={"reason": f"Priority is driven mainly by {risk_summary}."}
                )
                repaired_record_ids.append(action.record_id)

            if not self._business_rationale_is_specific(repaired_actions[index].business_rationale):
                issues.append(f"{action.record_id}: business rationale is too generic.")
                repaired_actions[index] = repaired_actions[index].model_copy(
                    update={"business_rationale": self._repair_business_rationale(classification)}
                )
                repaired_record_ids.append(action.record_id)

            if classification.risk_flags and not repaired_actions[index].escalation_required and classification.priority_level.value == "P1":
                issues.append(f"{action.record_id}: P1 risk record should explicitly mark escalation.")
                repaired_actions[index] = repaired_actions[index].model_copy(update={"escalation_required": True})
                repaired_record_ids.append(action.record_id)

            if classification.priority_level.value == "P1" and not self._strong_operator_note(repaired_actions[index].operator_note):
                issues.append(f"{action.record_id}: P1 record needs a stronger operator note.")
                repaired_actions[index] = repaired_actions[index].model_copy(
                    update={
                        "operator_note": (
                            f"Escalate in the manager pipeline review and confirm that {repaired_actions[index].recommended_owner} "
                            "logs a dated buyer-facing next step today."
                        )
                    }
                )
                repaired_record_ids.append(action.record_id)

        repaired_record_ids = sorted(set(repaired_record_ids))
        repair_triggered = bool(repaired_record_ids)
        review_summary = (
            f"Reviewer repaired {len(repaired_record_ids)} records after finding {len(issues)} issues."
            if repair_triggered
            else "Reviewer approved all actions without changes."
        )

        return ReviewResult(
            approved=not repair_triggered,
            issues=issues,
            repaired_actions=repaired_actions,
            repair_triggered=repair_triggered,
            repaired_record_ids=repaired_record_ids,
            revision_rounds=1 if repair_triggered else 0,
            review_summary=review_summary,
        )

    def _is_concrete_action(self, next_action: str) -> bool:
        lowered = next_action.lower()
        required_markers = ["should"]
        action_markers = ["call", "send", "book", "schedule", "confirm", "update", "log", "escalate", "identify"]
        system_markers = ["crm", "log", "document", "meeting", "agenda", "next step"]
        time_markers = ["today", "24 hours", "by ", "within "]
        return (
            len(next_action.strip()) >= 60
            and all(marker in lowered for marker in required_markers)
            and any(marker in lowered for marker in action_markers)
            and any(marker in lowered for marker in system_markers)
            and any(marker in lowered for marker in time_markers)
        )

    def _reason_reflects_risks(self, reason: str, classification: ClassificationResult) -> bool:
        lowered = reason.lower()
        keywords = {
            "champion_left": ["champion", "sponsor"],
            "competitive_pressure": ["competitive", "competitor"],
            "missing_next_step": ["next step"],
            "no_next_step_near_close": ["close", "next step", "deadline"],
            "stale_activity": ["stale", "inactive", "activity"],
            "stalled_stage": ["stage", "stalled", "momentum"],
            "unresponsive_buyer": ["buyer", "response", "responded"],
        }
        top_risks = classification.risk_flags[:2]
        return all(any(keyword in lowered for keyword in keywords.get(risk, [])) for risk in top_risks)

    def _business_rationale_is_specific(self, rationale: str) -> bool:
        lowered = rationale.lower()
        weak_phrases = ["score profile", "revenue risk or upside", "merits follow-up"]
        strong_markers = ["slippage", "high-acv", "close", "stalled", "manager attention", "next step", "buyer interest"]
        return not any(phrase in lowered for phrase in weak_phrases) and any(marker in lowered for marker in strong_markers)

    def _repair_business_rationale(self, classification: ClassificationResult) -> str:
        risks = set(classification.risk_flags)
        signals = set(classification.intent_signals)

        if "requested_demo" in signals and "budget_confirmed" in signals:
            return "Buyer interest is strong and budget appears real, so the operator should convert that demand into a scheduled next meeting."
        if "requested_demo" in signals:
            return "Buyer interest should be converted into a scheduled meeting rather than left in the queue without a concrete follow-up."
        if "budget_confirmed" in signals:
            return "Budget is confirmed, but execution discipline is lagging and the record needs a dated commercial next step."
        if "unresponsive_buyer" in risks:
            return "Unresponsive buyer behavior is increasing slippage risk, so the record should stay in the operator queue until response paths are clear."
        if "missing_next_step" in risks:
            return "Missing next-step discipline is reducing forecast clarity even though the record still has active pipeline value."
        return f"Stale follow-up is slowing pipeline progression because the record currently shows {self._risk_summary(classification)}."

    def _strong_operator_note(self, note: str) -> bool:
        lowered = note.lower()
        return "today" in lowered and ("manager" in lowered or "escalate" in lowered) and "next step" in lowered

    def _risk_summary(self, classification: ClassificationResult) -> str:
        labels = {
            "champion_left": "a lost champion",
            "competitive_pressure": "active competitive pressure",
            "missing_next_step": "a missing next step",
            "no_next_step_near_close": "near-close slippage risk",
            "stale_activity": "stale seller activity",
            "stalled_stage": "a stalled stage",
            "unresponsive_buyer": "an unresponsive buyer",
        }
        summary = [labels[risk] for risk in classification.risk_flags if risk in labels]
        if not summary:
            return "mixed commercial risk"
        if len(summary) == 1:
            return summary[0]
        return ", ".join(summary[:-1]) + f", and {summary[-1]}"
