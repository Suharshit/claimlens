"""Fraud Signal Agent — Scores the claim on risk rules and prior-claim memory.

Features: M6
Writes to claim state: ``fraud`` (and nothing else).
Tools: lookup_prior_claims, check_waiting_period, score_risk (tools/fraud_tools.py).
Note: Runs in parallel with the Policy Retrieval Agent; needs nothing from it.

Agents never import each other; they communicate only through the claim-state
record (tools/state.py) and workflow.py. ``run_sync`` holds the agent's steps;
``run`` is the async entry point that this agent's Microsoft Agent Framework
executor in workflow.py awaits.
"""

from __future__ import annotations

import asyncio
from typing import Any

from tools.fraud_tools import (
    check_waiting_period,
    lookup_prior_claims,
    score_risk,
)
from tools.intake_tools import load_policies
from tools.logger import log_step
from tools.state import read_state, write_state

AGENT_NAME = "Fraud Signal Agent"
AGENT_ID = "fraud_agent"
STATE_SECTIONS = ('fraud',)
TOOLS = [lookup_prior_claims, check_waiting_period, score_risk]


def run_sync(claim_id: str) -> dict[str, Any]:
    record = read_state(claim_id)
    intake = record["intake"]
    limits = load_policies()[intake["policy_id"]]     # structured data, not another agent's output
    log_step(claim_id, AGENT_ID, "start", "risk rules + prior-claim memory")

    prior = lookup_prior_claims(intake.get("policyholder_id") or "")
    log_step(claim_id, AGENT_ID, "lookup_prior_claims", f"{len(prior)} earlier claims by {intake.get('policyholder_id')}")
    wait = check_waiting_period(limits["inception_date"], intake["admit"], intake["diagnosis"],
                                limits=limits, accident=intake.get("accident", False))
    log_step(claim_id, AGENT_ID, "check_waiting_period",
             f"excluded under {wait['clause_id']} until {wait['waiting_ends']}" if wait["excluded"]
             else ("accident: waiting periods do not apply" if wait["accident"] else "no waiting period applies"))
    risk = score_risk(record, limits=limits)
    log_step(claim_id, AGENT_ID, "score_risk", f"score {risk['score']} {risk['reasons']}")

    details = list(risk["details"])
    if prior:
        details.append(f"{len(prior)} earlier claim(s) by this policyholder in the prior-claim store")
    return write_state(claim_id, "fraud", {**risk, "details": details, "waiting_period": wait}, agent=AGENT_ID)


async def run(claim_id: str) -> dict[str, Any]:
    """Read the claim state, call this agent's tools, write its own section(s)."""
    return await asyncio.to_thread(run_sync, claim_id)
