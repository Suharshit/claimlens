"""Human Review Desk — Group-of-3 add-on: records the adjuster's verdict and closes the claim.

Features: M11
Writes to claim state: ``human`` (and nothing else).
Tools: create_review_ticket, record_human_verdict (tools/decision_tools.py).
Note: The final decision on any escalated or high-value claim belongs to a human.

Agents never import each other; they communicate only through the claim-state
record (tools/state.py) and workflow.py. The agent object itself is created
once the framework is chosen (open question in context/05-progress.md).
"""

from __future__ import annotations

from tools.decision_tools import (
    create_review_ticket,
    record_human_verdict,
)

AGENT_NAME = "Human Review Desk"
STATE_SECTIONS = ('human',)
TOOLS = [create_review_ticket, record_human_verdict]


async def run(claim_id: str) -> None:
    """Read the claim state, call this agent's tools, write its own section(s)."""
    raise NotImplementedError("Human Review Desk — see context/05-progress.md for the week")
