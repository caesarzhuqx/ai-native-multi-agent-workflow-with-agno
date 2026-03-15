from __future__ import annotations

import argparse

from dotenv import load_dotenv

from app.workflows.revops_workflow import run_workflow


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Agno RevOps triage workflow.")
    parser.add_argument("--input", default="data/sample_pipeline.csv", help="Path to pipeline CSV input.")
    parser.add_argument("--output-dir", default="demo", help="Directory for generated artifacts.")
    return parser.parse_args()


def main() -> None:
    load_dotenv()
    args = parse_args()
    run_workflow(input_path=args.input, output_dir=args.output_dir)


if __name__ == "__main__":
    main()
