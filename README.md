# AI-Native RevOps Triage Workflow with Agno

This repository is a take-home submission for a small, clean multi-agent workflow built with Agno. It solves one narrow Revenue Operations problem: reviewing a small set of pipeline records, prioritizing operator attention, and producing concrete next actions.

The project is intentionally scoped to be easy to run, inspect, and defend. It is not a CRM integration or a product surface. It is a typed workflow submission.

## Which Track I Chose

- **Track:** Option D, Operators Team
- **Vertical:** Revenue Operations / Sales Operations
- **Use case:** Daily pipeline triage

I chose this problem because it is operationally realistic, naturally structured, and well suited to a multi-agent workflow. It has a clear input, a clear output, and meaningful business tradeoffs without requiring a large system.

## Agent Architecture

The workflow uses a `coordinator -> specialists -> reviewer` pattern:

1. `IntakeAgent`
2. `ClassificationAgent`
3. `ActionAgent`
4. `ReviewAgent`

Orchestration is implemented as an Agno `Workflow` with `Step` executors in [app/workflows/revops_workflow.py](./app/workflows/revops_workflow.py).

This is intentionally multi-agent rather than one long prompt. Each step performs a different type of work, and the handoffs are typed and explicit. That keeps the workflow more auditable and more defensible than a single prompt that tries to classify, recommend, and review in one pass.

## What Each Agent Does

### `IntakeAgent`

- loads CSV input from `data/sample_pipeline.csv`
- validates required fields
- converts rows into typed `PipelineRecord` objects
- records malformed rows as structured validation issues

### `ClassificationAgent`

- scores each record using structured business signals
- assigns a priority and numeric score
- identifies risk flags such as stale activity, stalled stage, missing next step, and close-date pressure
- extracts a small set of lightweight note signals such as `budget_confirmed`, `requested_demo`, and `champion_left`

### `ActionAgent`

- converts classifications into typed `RecommendedAction` outputs
- produces owner, due date, next action, rationale, and escalation recommendation
- uses Agno + OpenAI if live model access is available
- falls back to deterministic rules if no model is configured

### `ReviewAgent`

- checks whether actions are concrete enough
- verifies that reasons reflect the actual risk profile
- ensures escalation is aligned with truly urgent cases
- repairs weak or incomplete actions in one focused review pass
- can trigger one bounded correction loop before final output

## Tools Used

The tool layer is intentionally small.

Core tools:

1. [app/tools/validators.py](./app/tools/validators.py)
   Validates and normalizes input rows.
2. [app/tools/scoring.py](./app/tools/scoring.py)
   Applies deterministic scoring and lightweight note-signal extraction.
3. [app/tools/retry.py](./app/tools/retry.py)
   Wraps action generation with basic retry logic.
4. [app/tools/logging.py](./app/tools/logging.py)
   Captures per-agent traces, latency, status, and repair metadata.

Supporting utility:

- [app/tools/formatting.py](./app/tools/formatting.py)
  Writes final JSON and Markdown artifacts.
- [app/tools/evaluation.py](./app/tools/evaluation.py)
  Runs a lightweight post-run rubric over the final output.

## Where AI-Assisted Coding Helped

AI-assisted coding helped accelerate:

- the initial repository scaffold
- the first pass of typed models and workflow wiring
- exploration of agent boundaries before narrowing the scope
- the first implementation of retries, logging, and README structure

The important point is not that AI wrote a large system. The useful part was speeding up iteration while keeping design ownership, reducing scope, and tightening weak outputs.

## Tradeoffs and Known Limitations

The project makes deliberate scope choices:

- It uses one normalized `PipelineRecord` model instead of separate lead, account, and opportunity flows.
- The classifier is intentionally rules-first rather than deeply semantic.
- Notes are treated as supplementary signals, not the primary source of truth.
- The reviewer performs one focused repair pass, not a deep iterative critic loop.
- The demo is CLI-first rather than Agent OS UI or a web application.
- There is no CRM, email, or database integration.
- Token usage is only populated when the live Agno/OpenAI path is active.

These are intentional tradeoffs to keep the submission small, runnable, and easy to explain.

## Deterministic vs AI-Assisted Logic

Deterministic logic is used for:

- input validation
- typed schema enforcement
- scoring based on structured fields
- fallback action generation
- reviewer repair rules

AI-assisted logic is used for:

- optional action generation through Agno + OpenAI
- richer phrasing when live model access is enabled
- token-aware instrumentation on the model path

This split was deliberate. RevOps prioritization should mostly come from stable structured signals, while AI is more useful for generation and cleanup.

## Setup Instructions

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e .[dev]
```

Optional environment variables:

```bash
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-4.1-mini
```

If no API key is provided, the workflow still runs locally through the deterministic fallback path.

## Run Instructions

Run the demo:

```bash
python demo/run_demo.py
```

Or run the workflow directly:

```bash
python -m app.main --input data/sample_pipeline.csv --output-dir demo
```

Run tests:

```bash
pytest app/tests
```

Optional Agent OS runtime:

```bash
fastapi dev app/agent_os_app.py
```

This keeps the existing CLI workflow unchanged, but also exposes a minimal AgentOS-compatible runtime for UI-based inspection if you want to connect it to Agno Agent OS / AgentUI locally.

## Demo Input and Example Output

Sample input:

- [data/sample_pipeline.csv](./data/sample_pipeline.csv)

Representative output artifacts:

- [demo/prioritized_actions.json](./demo/prioritized_actions.json)
- [demo/operator_summary.md](./demo/operator_summary.md)
- [demo/evaluation_report.md](./demo/evaluation_report.md)

The JSON artifact is the structured action list. The Markdown artifact is the operator-facing summary.

## Brief build notes

I used Codex as the main AI coding assistant for repository scaffolding, file organization, and fast iteration on typed workflow components. It helped accelerate the initial setup of the Agno workflow, agent modules, Pydantic-style models, and CLI/demo structure.

AI sped me up most on boilerplate-heavy work: creating the repo layout, drafting the first pass of agent files, wiring the workflow entry points, and generating initial test skeletons, logging utilities, and README sections.

Early AI-generated output was often too generic. In particular, the first action recommendations sounded templated and operationally weak, so I repeatedly redirected the implementation toward more concrete RevOps language with owner, step, timing, and escalation context.

The first scoring behavior was also too aggressive. After expanding the sample dataset, some commercially promising but non-urgent opportunities were incorrectly pushed into P1. I corrected this by tightening the priority logic so stale activity alone would not trigger top-tier escalation.

AI also produced inconsistent final artifacts at one point: the JSON output ordering did not match the operator summary ordering. I explicitly caught that during debugging and had the workflow corrected so both outputs use the same final sorted order.

The review step needed refinement. The initial reviewer mainly repaired missing fields, but I pushed it to do more meaningful QA: checking action concreteness, alignment between risk signals and rationale, and whether escalation behavior matched truly urgent cases.

I personally guided the dataset design rather than treating sample data as an afterthought. I iterated on the synthetic CSV to better cover realistic RevOps scenarios such as champion loss, competitive pressure, missing next steps near close, stale activity, requested demos, budget-confirmed deals, weak/vague next steps, and healthy lower-urgency records.

I also directed several rounds of output-quality debugging by manually inspecting the generated Markdown and JSON artifacts, comparing whether the priorities, reasons, business rationale, and escalation flags actually matched the intended business logic.

On testing, AI helped draft the initial test files, but I strengthened them by adding more representative checks: malformed input validation, normalization of slightly messy but valid rows, reviewer repair behavior for broken P1 actions, and non-overrepair behavior for already reasonable P2 actions.

I added and kept a deterministic fallback path as an intentional engineering choice. This was important because I wanted the workflow to remain runnable locally even without live model access, rather than depending entirely on an external API during evaluation.

I also added a lightweight evaluation harness late in the process to make the project more defensible. It checks output ordering, P1 escalation alignment, action concreteness, review completion, and the presence of both structured and operator-facing artifacts.

Overall, AI was most valuable as a fast implementation partner, but the quality of the final submission depended on repeated human correction: tightening scope, improving business realism, calibrating scoring, upgrading tests, and debugging the final outputs until they matched the intended workflow behavior.
