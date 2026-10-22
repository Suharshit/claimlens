"""Intake Agent — Turns claim text + bill into a structured record.

Features: M1, M2
Writes to claim state: ``intake``, ``bill_items`` (and nothing else).
Tools: extract_claim_fields, parse_bill, validate_policy (tools/intake_tools.py).
Note: Halts (status stays 'intake') when policy id or claimed amount is missing — no downstream agent runs (scenario 7).

Agents never import each other; they communicate only through the claim-state
record (tools/state.py) and workflow.py. The agent object itself is created
once the framework is chosen (open question in context/05-progress.md).
"""

from __future__ import annotations

from tools.intake_tools import (
    extract_claim_fields,
    parse_bill,
    validate_policy,
)

AGENT_NAME = "Intake Agent"
STATE_SECTIONS = ('intake', 'bill_items')
TOOLS = [extract_claim_fields, parse_bill, validate_policy]


async def run(claim_id: str) -> None:
    """Read the claim state, call this agent's tools, write its own section(s)."""
    raise NotImplementedError("Intake Agent — see context/05-progress.md for the week")
