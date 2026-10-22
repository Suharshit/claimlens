"""Policy Retrieval Agent — RAG over policy wordings and IRDAI rules; returns governing clauses and limits.

Features: M3
Writes to claim state: ``policy`` (and nothing else).
Tools: search_policy_clauses, get_policy_limits, search_irdai_rules (tools/retrieval_tools.py).
Note: Runs in parallel with the Fraud Signal Agent. Posts limits first so Cost Assessment can start.

Agents never import each other; they communicate only through the claim-state
record (tools/state.py) and workflow.py. The agent object itself is created
once the framework is chosen (open question in context/05-progress.md).
"""

from __future__ import annotations

from tools.retrieval_tools import (
    search_policy_clauses,
    get_policy_limits,
    search_irdai_rules,
)

AGENT_NAME = "Policy Retrieval Agent"
STATE_SECTIONS = ('policy',)
TOOLS = [search_policy_clauses, get_policy_limits, search_irdai_rules]


async def run(claim_id: str) -> None:
    """Read the claim state, call this agent's tools, write its own section(s)."""
    raise NotImplementedError("Policy Retrieval Agent — see context/05-progress.md for the week")
