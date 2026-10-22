"""Grievance Drafter — Should-have: drafts a query reply or grievance letter for contestable deductions.

Features: S2 (should-have)
Writes to claim state: ``letters`` (and nothing else).
Tools: list_contestable, render_letter (tools/decision_tools.py).
Note: Build only after all seven scenarios pass.

Agents never import each other; they communicate only through the claim-state
record (tools/state.py) and workflow.py. The agent object itself is created
once the framework is chosen (open question in context/05-progress.md).
"""

from __future__ import annotations

from tools.decision_tools import (
    list_contestable,
    render_letter,
)

AGENT_NAME = "Grievance Drafter"
STATE_SECTIONS = ('letters',)
TOOLS = [list_contestable, render_letter]


async def run(claim_id: str) -> None:
    """Read the claim state, call this agent's tools, write its own section(s)."""
    raise NotImplementedError("Grievance Drafter — see context/05-progress.md for the week")
