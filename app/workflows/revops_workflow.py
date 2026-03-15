from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter
from typing import Any, Callable, TypeVar
from uuid import uuid4

from agno.workflow import Step, Workflow
from agno.workflow.types import StepInput, StepOutput

from app.agents.action_agent import ActionAgent
from app.agents.classification_agent import ClassificationAgent
from app.agents.intake_agent import IntakeAgent
from app.agents.review_agent import ReviewAgent
from app.models.metrics import AgentTrace, WorkflowMetrics
from app.models.outputs import ActionGenerationResult, OperatorSummary, ReviewResult
from app.models.state import RevOpsWorkflowState
from app.tools.evaluation import evaluate_workflow_output
from app.tools.formatting import write_outputs
from app.tools.logging import print_trace_table, utc_now, write_run_log
from app.tools.retry import with_retry

T = TypeVar("T")


@dataclass
class RevOpsTriageWorkflow:
    intake_agent: IntakeAgent = field(default_factory=IntakeAgent)
    classification_agent: ClassificationAgent = field(default_factory=ClassificationAgent)
    action_agent: ActionAgent = field(default_factory=ActionAgent)
    review_agent: ReviewAgent = field(default_factory=ReviewAgent)

    def run(self, input_path: str, output_dir: str = "demo", print_logs: bool = True) -> RevOpsWorkflowState:
        metrics = WorkflowMetrics(run_started_at=utc_now())
        state = RevOpsWorkflowState(
            run_id=uuid4().hex[:8],
            input_path=input_path,
            output_dir=output_dir,
            metrics=metrics,
        )
        workflow = self._build_agno_workflow()
        workflow_output = workflow.run(input=state)
        state = self._coerce_state(workflow_output.content)

        state.metrics.run_ended_at = utc_now()
        state.metrics.total_latency_ms = int(
            (state.metrics.run_ended_at - state.metrics.run_started_at).total_seconds() * 1000
        )
        state.metrics.success = True
        write_run_log(state)
        if print_logs:
            print_trace_table(state.metrics.traces)
        return state

    def _build_agno_workflow(self) -> Workflow:
        return Workflow(
            name="revops_triage_workflow",
            description="Agno-based RevOps pipeline triage workflow",
            steps=[
                Step(name=self.intake_agent.name, executor=self._intake_step),
                Step(name=self.classification_agent.name, executor=self._classification_step),
                Step(name=self.action_agent.name, executor=self._action_step),
                Step(name=self.review_agent.name, executor=self._review_step),
            ],
        )

    def _intake_step(self, step_input: StepInput) -> StepOutput:
        state = self._require_state(step_input)
        state.validated_records, state.validation_issues = self._timed_step(
            state,
            self.intake_agent.name,
            lambda: self.intake_agent.run(state.input_path),
        )
        state.input_records = list(state.validated_records)
        return StepOutput(step_name=self.intake_agent.name, content=state)

    def _classification_step(self, step_input: StepInput) -> StepOutput:
        state = self._require_state(step_input)
        state.classifications = self._timed_step(
            state,
            self.classification_agent.name,
            lambda: self.classification_agent.run(state.validated_records),
        )
        return StepOutput(step_name=self.classification_agent.name, content=state)

    def _action_step(self, step_input: StepInput) -> StepOutput:
        state = self._require_state(step_input)
        action_result = self._timed_step(
            state,
            self.action_agent.name,
            lambda: with_retry(
                lambda: self.action_agent.run(state.validated_records, state.classifications),
                attempts=self.action_agent.retries,
            ),
            returns_retry_count=True,
            result_inspector=self._action_result_trace,
        )
        state.action_generation = action_result
        state.actions = action_result.actions
        return StepOutput(step_name=self.action_agent.name, content=state)

    def _review_step(self, step_input: StepInput) -> StepOutput:
        state = self._require_state(step_input)
        state.review = self._timed_step(
            state,
            self.review_agent.name,
            lambda: self.review_agent.run(state.classifications, state.actions),
            result_inspector=self._review_result_trace,
        )
        if state.review and state.review.repair_triggered:
            revision_result = self._timed_step(
                state,
                f"{self.action_agent.name}_revision",
                lambda: self.action_agent.revise_actions(
                    state.validated_records,
                    state.classifications,
                    state.actions,
                    state.review.issues,
                ),
                result_inspector=self._action_result_trace,
            )
            state.action_generation = revision_result
            state.actions = revision_result.actions
            state.review = self._timed_step(
                state,
                f"{self.review_agent.name}_revision",
                lambda: self.review_agent.run(state.classifications, state.actions),
                result_inspector=self._review_result_trace,
            )
            if state.review.repaired_actions:
                state.actions = state.review.repaired_actions
        elif state.review and state.review.repaired_actions:
            state.actions = state.review.repaired_actions
        state.actions = self._sort_actions(state.actions)

        state.summary = self._build_summary(state)
        state.evaluation = evaluate_workflow_output(state)
        write_outputs(state)
        return StepOutput(step_name=self.review_agent.name, content=state)

    def _require_state(self, step_input: StepInput) -> RevOpsWorkflowState:
        content = step_input.previous_step_content or step_input.input
        return self._coerce_state(content)

    def _coerce_state(self, content: Any) -> RevOpsWorkflowState:
        if isinstance(content, RevOpsWorkflowState):
            return content
        if isinstance(content, dict):
            return RevOpsWorkflowState.model_validate(content)
        raise TypeError("Workflow steps require RevOpsWorkflowState input.")

    def _timed_step(
        self,
        state: RevOpsWorkflowState,
        agent_name: str,
        func: Callable[[], T | tuple[T, int]],
        returns_retry_count: bool = False,
        result_inspector: Callable[[T], dict[str, Any]] | None = None,
    ) -> T:
        started_at = utc_now()
        started_perf = perf_counter()
        retries = 0
        try:
            result = func()
            if returns_retry_count:
                result, retries = result
            trace_details = result_inspector(result) if result_inspector else {}
            trace = AgentTrace(
                agent_name=agent_name,
                started_at=started_at,
                ended_at=utc_now(),
                latency_ms=int((perf_counter() - started_perf) * 1000),
                success=True,
                retries=retries,
                generation_mode=trace_details.get("generation_mode"),
                model_name=trace_details.get("model_name"),
                token_input=trace_details.get("token_input"),
                token_output=trace_details.get("token_output"),
                repair_triggered=trace_details.get("repair_triggered", False),
            )
            state.metrics.traces.append(trace)
            return result
        except Exception as exc:  # noqa: BLE001
            trace = AgentTrace(
                agent_name=agent_name,
                started_at=started_at,
                ended_at=utc_now(),
                latency_ms=int((perf_counter() - started_perf) * 1000),
                success=False,
                retries=retries,
                error_message=str(exc),
            )
            state.metrics.traces.append(trace)
            state.metrics.run_ended_at = utc_now()
            state.metrics.total_latency_ms = int(
                (state.metrics.run_ended_at - state.metrics.run_started_at).total_seconds() * 1000
            )
            state.metrics.success = False
            write_run_log(state)
            raise

    def _action_result_trace(self, result: ActionGenerationResult) -> dict[str, Any]:
        return {
            "generation_mode": result.generation_mode,
            "model_name": result.model_name,
            "token_input": result.token_input,
            "token_output": result.token_output,
        }

    def _review_result_trace(self, result: ReviewResult) -> dict[str, Any]:
        return {
            "repair_triggered": result.repair_triggered,
        }

    def _build_summary(self, state: RevOpsWorkflowState) -> OperatorSummary:
        sorted_actions = self._sort_actions(state.actions)
        validation_notes = [issue.message for issue in state.validation_issues] or ["No validation issues."]

        return OperatorSummary(
            headline="RevOps Daily Pipeline Triage",
            top_actions=[
                f"{action.record_id}: {action.next_action} ({action.priority_level.value}, score={action.score}, owner={action.recommended_owner})"
                for action in sorted_actions[:5]
            ],
            risks=[
                f"{classification.record_id}: {', '.join(classification.risk_flags)}"
                for classification in state.classifications
                if classification.risk_flags
            ][:5],
            data_quality_notes=validation_notes[:5],
            manager_notes=[
                f"{action.record_id}: escalation recommended for {action.recommended_owner}"
                for action in sorted_actions
                if action.escalation_required
            ][:5]
            or ["No manager escalations required."],
        )

    def _sort_actions(self, actions):
        priority_rank = {"P1": 0, "P2": 1, "P3": 2}
        return sorted(
            actions,
            key=lambda action: (
                priority_rank[action.priority_level.value],
                -action.score,
                -action.confidence,
                action.record_id,
            ),
        )


def run_workflow(input_path: str, output_dir: str = "demo") -> RevOpsWorkflowState:
    workflow = RevOpsTriageWorkflow()
    return workflow.run(input_path=input_path, output_dir=output_dir)
