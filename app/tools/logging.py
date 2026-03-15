from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from rich.console import Console
from rich.table import Table

from app.models.metrics import AgentTrace
from app.models.state import RevOpsWorkflowState


console = Console()


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def print_trace_table(traces: list[AgentTrace]) -> None:
    table = Table(title="Workflow Execution")
    table.add_column("Agent")
    table.add_column("Latency (ms)", justify="right")
    table.add_column("Success")
    table.add_column("Retries", justify="right")
    table.add_column("Mode")
    table.add_column("Tokens In", justify="right")
    table.add_column("Tokens Out", justify="right")
    table.add_column("Repair")
    table.add_column("Error")

    for trace in traces:
        table.add_row(
            trace.agent_name,
            str(trace.latency_ms),
            "yes" if trace.success else "no",
            str(trace.retries),
            trace.generation_mode or "-",
            str(trace.token_input) if trace.token_input is not None else "-",
            str(trace.token_output) if trace.token_output is not None else "-",
            "yes" if trace.repair_triggered else "no",
            trace.error_message or "-",
        )

    console.print(table)


def write_run_log(state: RevOpsWorkflowState) -> Path:
    log_dir = Path("logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    output_path = log_dir / f"run_{state.run_id}.json"
    output_path.write_text(state.model_dump_json(indent=2), encoding="utf-8")
    return output_path
