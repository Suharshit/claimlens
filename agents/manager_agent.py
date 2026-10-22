"""Adjudication Manager — Fans in all signals, decides, cites clauses, routes to a human when needed.

Features: M7, M8, M9, M10
Writes to claim state: ``decision`` (and nothing else).
Tools: apply_decision_rules, verify_citations, write_decision (tools/decision_tools.py).
Note: A verdict may only cite clause ids that were actually retrieved (citation guard).

Agents never import each other; they communicate only through the claim-state
record (tools/state.py) and workflow.py. The agent object itself is created
once the framework is chosen (open question in context/05-progress.md).
"""

from __future__ import annotations

from tools.decision_tools import (
    apply_decision_rules,
    verify_citations,
    write_decision,
)

AGENT_NAME = "Adjudication Manager"
STATE_SECTIONS = ('decision',)
TOOLS = [apply_decision_rules, verify_citations, write_decision]


async def run(claim_id: str) -> None:
    """Read the claim state, call this agent's tools, write its own section(s)."""
    raise NotImplementedError("Adjudication Manager — see context/05-progress.md for the week")
