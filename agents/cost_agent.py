"""Cost Assessment Agent — Computes the payable amount line by line; flags over-claiming.

Features: M4, M5, S1
Writes to claim state: ``cost`` (and nothing else).
Tools: classify_items, room_rent_deduction, compute_payable (tools/cost_tools.py).
Note: Waits for policy limits — the one ordered step. The LLM never does arithmetic here.

Agents never import each other; they communicate only through the claim-state
record (tools/state.py) and workflow.py. The agent object itself is created
once the framework is chosen (open question in context/05-progress.md).
"""

from __future__ import annotations

from tools.cost_tools import (
    classify_items,
    room_rent_deduction,
    compute_payable,
)

AGENT_NAME = "Cost Assessment Agent"
STATE_SECTIONS = ('cost',)
TOOLS = [classify_items, room_rent_deduction, compute_payable]


async def run(claim_id: str) -> None:
    """Read the claim state, call this agent's tools, write its own section(s)."""
    raise NotImplementedError("Cost Assessment Agent — see context/05-progress.md for the week")
