from __future__ import annotations

import importlib
import os
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from pydantic import BaseModel

from app.models.outputs import ActionGenerationResult, ClassificationResult, PriorityLevel, RecommendedAction
from app.models.records import PipelineRecord


class ActionBatch(BaseModel):
    actions: list[RecommendedAction]


@dataclass
class ActionAgent:
    name: str = "action_agent"
    retries: int = 2

    def run(
        self,
        records: list[PipelineRecord],
        classifications: list[ClassificationResult],
    ) -> ActionGenerationResult:
        if self._can_use_agno():
            try:
                return self._run_with_agno(records, classifications)
            except Exception:  # noqa: BLE001
                return self._run_with_rules(records, classifications)
        return self._run_with_rules(records, classifications)

    def revise_actions(
        self,
        records: list[PipelineRecord],
        classifications: list[ClassificationResult],
        current_actions: list[RecommendedAction],
        review_issues: list[str],
    ) -> ActionGenerationResult:
        revised = self._run_with_rules(records, classifications)
        issue_map: dict[str, list[str]] = {}
        for issue in review_issues:
            record_id = issue.split(":", 1)[0]
            issue_map.setdefault(record_id, []).append(issue)

        revised_actions: list[RecommendedAction] = []
        for action in revised.actions:
            issues = issue_map.get(action.record_id, [])
            if not issues:
                current = next((item for item in current_actions if item.record_id == action.record_id), action)
                revised_actions.append(current)
                continue

            updated = action
            if any("reason does not reflect" in issue for issue in issues):
                updated = updated.model_copy(
                    update={"reason": f"{updated.reason} Reviewer requested that the primary risk be called out explicitly."}
                )
            if any("business rationale is too generic" in issue for issue in issues):
                updated = updated.model_copy(
                    update={"business_rationale": f"{updated.business_rationale} This was refreshed in a review-driven correction pass."}
                )
            revised_actions.append(updated)

        return revised.model_copy(update={"actions": revised_actions})

    def _can_use_agno(self) -> bool:
        return bool(os.getenv("OPENAI_API_KEY")) and self._load_agno_openai_classes() is not None

    def _load_agno_openai_classes(self) -> tuple[type[Any], type[Any]] | None:
        try:
            agent_module = importlib.import_module("agno.agent")
            openai_module = importlib.import_module("agno.models.openai")
        except Exception:  # noqa: BLE001
            return None

        agent_cls = getattr(agent_module, "Agent", None)
        openai_chat_cls = getattr(openai_module, "OpenAIChat", None)
        if agent_cls is None or openai_chat_cls is None:
            return None
        return agent_cls, openai_chat_cls

    def _run_with_rules(
        self,
        records: list[PipelineRecord],
        classifications: list[ClassificationResult],
    ) -> ActionGenerationResult:
        record_by_id = {record.record_id: record for record in records}
        actions: list[RecommendedAction] = []

        for classification in classifications:
            record = record_by_id[classification.record_id]
            is_p1 = classification.priority_level == PriorityLevel.P1
            due_date = date.today() + timedelta(days=1 if is_p1 else 3 if classification.priority_level == PriorityLevel.P2 else 5)
            escalation_required = self._should_escalate(classification)
            next_action = self._build_next_action(record, classification, due_date, escalation_required)
            reason = self._build_reason(classification)
            business_rationale = self._build_business_rationale(record, classification, escalation_required)
            operator_note = self._build_operator_note(record, classification, due_date, escalation_required)
            confidence = min(0.55 + (classification.score / 200), 0.95)

            actions.append(
                RecommendedAction(
                    record_id=record.record_id,
                    priority_level=classification.priority_level,
                    score=classification.score,
                    recommended_owner=record.owner,
                    due_date=due_date,
                    next_action=next_action,
                    reason=reason,
                    business_rationale=business_rationale,
                    operator_note=operator_note,
                    confidence=confidence,
                    escalation_required=escalation_required,
                )
            )

        return ActionGenerationResult(
            actions=actions,
            generation_mode="rules",
        )

    def _run_with_agno(
        self,
        records: list[PipelineRecord],
        classifications: list[ClassificationResult],
    ) -> ActionGenerationResult:
        loaded_classes = self._load_agno_openai_classes()
        if loaded_classes is None:
            raise RuntimeError("Agno OpenAI classes are unavailable.")

        agent_cls, openai_chat_cls = loaded_classes
        agent = agent_cls(
            name="RevOps Action Agent",
            model=openai_chat_cls(id=os.getenv("OPENAI_MODEL", "gpt-4.1-mini")),
            response_model=ActionBatch,
            instructions=[
                "You are a Revenue Operations action planner.",
                "Turn validated pipeline classifications into concrete, operator-friendly next actions.",
                "Return JSON only and strictly satisfy the schema.",
                "Every high-risk or near-close record must have a clear next action and explicit reason.",
            ],
        )
        payload = {
            "records": [record.model_dump(mode="json") for record in records],
            "classifications": [classification.model_dump(mode="json") for classification in classifications],
        }
        response = agent.run(payload)
        token_input, token_output = self._extract_token_usage(response)
        content = getattr(response, "content", response)
        if isinstance(content, ActionBatch):
            actions = content.actions
        elif isinstance(content, dict):
            actions = ActionBatch.model_validate(content).actions
        elif isinstance(content, (str, bytes, bytearray)):
            actions = ActionBatch.model_validate_json(content).actions
        else:
            raise TypeError("Agno action response content did not match the expected schema.")

        return ActionGenerationResult(
            actions=actions,
            generation_mode="agno",
            model_name=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
            token_input=token_input,
            token_output=token_output,
        )

    def _extract_token_usage(self, response: Any) -> tuple[int | None, int | None]:
        metrics = getattr(response, "metrics", None)
        if metrics is None:
            return None, None

        token_input = getattr(metrics, "input_tokens", None)
        token_output = getattr(metrics, "output_tokens", None)

        if token_input is None:
            token_input = getattr(metrics, "prompt_tokens", None)
        if token_output is None:
            token_output = getattr(metrics, "completion_tokens", None)

        return token_input, token_output

    def _should_escalate(self, classification: ClassificationResult) -> bool:
        escalation_signals = {
            "champion_left",
            "no_next_step_near_close",
            "stalled_stage",
            "competitive_pressure",
        }
        return classification.priority_level == PriorityLevel.P1 and bool(
            escalation_signals.intersection(classification.risk_flags)
        )

    def _build_next_action(
        self,
        record: PipelineRecord,
        classification: ClassificationResult,
        due_date: date,
        escalation_required: bool,
    ) -> str:
        owner = record.owner
        company = record.company_name
        due_text = due_date.isoformat()
        risks = set(classification.risk_flags)
        signals = set(classification.intent_signals)

        if "champion_left" in risks:
            return (
                f"{owner} should identify a new champion at {company}, send a same-day follow-up to confirm decision ownership, "
                f"and log a replacement contact plus next meeting by {due_text}."
            )
        if "no_next_step_near_close" in risks:
            return (
                f"{owner} should lock the next buyer meeting for {company} today, add the dated meeting and owner in CRM immediately, "
                f"and confirm buyer commitments before the close window slips."
            )
        if "competitive_pressure" in risks and "stalled_stage" in risks:
            return (
                f"{owner} should clarify decision criteria and blocker with {company}, schedule a buyer touchpoint within 24 hours, "
                f"and document competitive next steps plus timeline in CRM by {due_text}."
            )
        if "competitive_pressure" in risks:
            return (
                f"{owner} should ask {company} for current decision criteria and timeline, schedule a buyer follow-up within 24 hours, "
                f"and capture the competitive blocker plus next step in CRM by {due_text}."
            )
        if "stalled_stage" in risks:
            return (
                f"{owner} should reopen momentum on {company} by booking the next buyer meeting within 24 hours and attaching a dated mutual action plan in CRM."
            )
        if "stale_activity" in risks and "unresponsive_buyer" in risks:
            return (
                f"{owner} should send a concrete follow-up to {company} with two meeting slots, call the main contact, "
                f"and close the loop in CRM if there is still no response by {due_text}."
            )
        if "requested_demo" in signals:
            return (
                f"{owner} should send a demo confirmation to {company}, lock attendees and agenda, "
                f"and convert this interest into a scheduled meeting by {due_text}."
            )
        if "budget_confirmed" in signals:
            if "messy" in (record.notes or "").lower() or "quiet" in (record.notes or "").lower() or "tbd" in ((record.next_step or "").lower()):
                return (
                    f"{owner} should clean up the open items on {company}, confirm whether legal, pricing, or process is blocking the deal, "
                    f"and replace the vague next step with a dated commercial action in CRM by {due_text}."
                )
            return (
                f"{owner} should move {company} to the next commercial step, confirm buying process, "
                f"and document a dated next action in CRM by {due_text}."
            )
        if escalation_required:
            return (
                f"{owner} should bring this deal to manager review today, document the blocker in CRM, "
                f"and leave the account with a dated next external step by {due_text}."
            )
        return (
            f"{owner} should contact {company}, confirm the buyer's next milestone, "
            f"and leave a dated follow-up step in CRM by {due_text}."
        )

    def _build_reason(self, classification: ClassificationResult) -> str:
        risk_text = self._describe_risks(classification.risk_flags)
        signal_text = self._describe_signals(classification.intent_signals)
        if classification.priority_level == PriorityLevel.P1:
            return f"Highest priority because {risk_text}."
        if classification.priority_level == PriorityLevel.P2:
            if signal_text:
                return f"Prioritized because {risk_text}, while {signal_text} shows the record is still commercially active."
            return f"Prioritized because {risk_text} and the deal still has meaningful pipeline value."
        if signal_text:
            return f"Lower priority for now, but still worth operator attention because {risk_text} and {signal_text}."
        return f"Lower priority for now, but still worth operator attention because {risk_text}."

    def _build_business_rationale(
        self,
        record: PipelineRecord,
        classification: ClassificationResult,
        escalation_required: bool,
    ) -> str:
        risks = set(classification.risk_flags)
        signals = set(classification.intent_signals)

        if "no_next_step_near_close" in risks:
            return f"Near-close slippage risk on an active deal: {record.company_name} is close to deadline without a committed next step."
        if "champion_left" in risks:
            return f"Manager attention is warranted because {record.company_name} may have lost its internal sponsor on a live opportunity."
        if "competitive_pressure" in risks and record.annual_contract_value >= 50000:
            return f"High-ACV opportunity under competitive pressure: the deal needs immediate intervention to protect pipeline value."
        if "competitive_pressure" in risks:
            return f"Competitive risk is active on {record.company_name}; operator follow-up should clarify blocker, decision criteria, and timing before the deal slips."
        if "stalled_stage" in risks and record.annual_contract_value >= 50000:
            return f"Stalled high-ACV opportunity: delay in-stage creates avoidable pipeline slippage if momentum is not restored quickly."
        if "requested_demo" in signals and "budget_confirmed" in signals:
            return f"Buyer intent is strong: the account requested a demo and signaled budget, so delay would waste active demand."
        if "requested_demo" in signals:
            return f"Requested-demo signal is already present, so the operator should convert that interest into a scheduled meeting quickly."
        if "budget_confirmed" in signals:
            if "messy" in (record.notes or "").lower() or "quiet" in (record.notes or "").lower() or "tbd" in ((record.next_step or "").lower()):
                return f"Budget is likely real, but weak process discipline is reducing forecast clarity and needs cleanup before the deal can progress."
            return f"Budget appears real, so the account should be advanced to a dated commercial next step instead of sitting in queue."
        if "stale_activity" in risks:
            return f"Pipeline hygiene risk: the record is active enough to matter, but recent inactivity suggests it could drift without operator intervention."
        if "unresponsive_buyer" in risks:
            return f"Buyer silence is increasing slippage risk, so the record belongs in the operator queue until a clear response path is established."
        if "missing_next_step" in risks:
            return f"Missing next-step discipline is reducing forecast clarity even though the record is still active."
        if escalation_required:
            return f"Escalation risk is high enough that manager visibility should be added before the opportunity slips further."
        return f"This record is active but not urgent, so it belongs in the operator queue rather than manager escalation."

    def _build_operator_note(
        self,
        record: PipelineRecord,
        classification: ClassificationResult,
        due_date: date,
        escalation_required: bool,
    ) -> str:
        if classification.priority_level == PriorityLevel.P1:
            note = f"Review with {record.owner} today and confirm the CRM next step before {due_date.isoformat()}."
            if escalation_required:
                return f"{note} Add manager visibility on this record in the same update."
            return note
        if classification.priority_level == PriorityLevel.P2:
            return f"Check that {record.owner} has a dated next step in CRM before {due_date.isoformat()}."
        return f"Keep this in the operator queue and verify follow-up by {due_date.isoformat()}."

    def _describe_risks(self, risk_flags: list[str]) -> str:
        ordered_descriptions: list[str] = []
        mapping = {
            "champion_left": "the deal may have lost its champion",
            "no_next_step_near_close": "the close window is near without a committed next step",
            "missing_next_step": "the record has no clear next step",
            "stale_activity": "seller activity has gone stale",
            "stalled_stage": "the deal has been sitting in stage too long",
            "unresponsive_buyer": "the buyer has not responded to follow-up",
            "competitive_pressure": "competitive pressure is active",
        }
        for key in [
            "champion_left",
            "no_next_step_near_close",
            "stalled_stage",
            "competitive_pressure",
            "stale_activity",
            "unresponsive_buyer",
            "missing_next_step",
        ]:
            if key in risk_flags:
                ordered_descriptions.append(mapping[key])

        if not ordered_descriptions:
            return "the record shows enough commercial signal to warrant follow-up"
        if len(ordered_descriptions) == 1:
            return ordered_descriptions[0]
        return ", ".join(ordered_descriptions[:-1]) + f", and {ordered_descriptions[-1]}"

    def _describe_signals(self, intent_signals: list[str]) -> str:
        descriptions: list[str] = []
        mapping = {
            "budget_confirmed": "budget has been confirmed",
            "requested_demo": "the buyer has already requested a demo",
        }
        for key in ["budget_confirmed", "requested_demo"]:
            if key in intent_signals:
                descriptions.append(mapping[key])

        if not descriptions:
            return ""
        if len(descriptions) == 1:
            return descriptions[0]
        return ", ".join(descriptions[:-1]) + f", and {descriptions[-1]}"
