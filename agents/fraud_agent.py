"""Fraud Signal Agent — Scores the claim on risk rules and prior-claim memory.

Features: M6
Writes to claim state: ``fraud`` (and nothing else).
Tools: lookup_prior_claims, check_waiting_period, score_risk (tools/fraud_tools.py).
Note: Runs in parallel with the Policy Retrieval Agent; needs nothing from it.

Agents never import each other; they communicate only through the claim-state
record (tools/state.py) and workflow.py. The agent object itself is created
once the framework is chosen (open question in context/05-progress.md).
"""

from __future__ import annotations

from tools.fraud_tools import (
    lookup_prior_claims,
    check_waiting_period,
    score_risk,
)

AGENT_NAME = "Fraud Signal Agent"
STATE_SECTIONS = ('fraud',)
TOOLS = [lookup_prior_claims, check_waiting_period, score_risk]


async def run(claim_id: str) -> None:
    """Read the claim state, call this agent's tools, write its own section(s)."""
    raise NotImplementedError("Fraud Signal Agent — see context/05-progress.md for the week")
