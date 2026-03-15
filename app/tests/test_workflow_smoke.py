from pathlib import Path

from app.workflows.revops_workflow import RevOpsTriageWorkflow


def test_workflow_smoke(tmp_path: Path):
    workflow = RevOpsTriageWorkflow()
    state = workflow.run("data/sample_pipeline.csv", output_dir=str(tmp_path), print_logs=False)

    assert state.metrics.success is True
    assert len(state.validated_records) >= 5
    assert len(state.actions) == len(state.validated_records)
    assert (tmp_path / "prioritized_actions.json").exists()
    assert (tmp_path / "operator_summary.md").exists()
    assert (tmp_path / "evaluation_report.md").exists()
    assert state.evaluation is not None
