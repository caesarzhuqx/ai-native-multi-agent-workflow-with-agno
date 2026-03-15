from __future__ import annotations

from agno.os import AgentOS

from app.workflows.revops_agentos_workflow import create_agentos_workflow


agent_os = AgentOS(
    name="revops-triage-os",
    description="AgentOS wrapper for the RevOps triage take-home workflow.",
    workflows=[create_agentos_workflow()],
)

app = agent_os.get_app()
