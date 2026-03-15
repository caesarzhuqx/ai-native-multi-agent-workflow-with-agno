from __future__ import annotations

from pathlib import Path

from app.workflows.revops_workflow import run_workflow


def main() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    input_path = repo_root / "data" / "sample_pipeline.csv"
    output_dir = repo_root / "demo"
    run_workflow(input_path=str(input_path), output_dir=str(output_dir))


if __name__ == "__main__":
    main()
