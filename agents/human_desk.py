"""Human Review Desk — Group-of-3 add-on: records the adjuster's verdict and closes the claim.

Features: M11
Writes to claim state: ``human`` (and nothing else).
Tools: create_review_ticket, record_human_verdict (tools/decision_tools.py).
Note: The final decision on any escalated or high-value claim belongs to a human.

Agents never import each other; they communicate only through the claim-state
record (tools/state.py) and workflow.py. ``run_sync`` holds the agent's steps;
``run`` is the async entry point that this agent's Microsoft Agent Framework
executor in workflow.py awaits.
"""

from __future__ import annotations

import asyncio
from typing import Any

from tools.decision_tools import (
    create_review_ticket,
    format_inr,
    record_human_verdict,
)
from tools.logger import log_step
from tools.state import read_state

AGENT_NAME = "Human Review Desk"
AGENT_ID = "human_desk"
STATE_SECTIONS = ('human',)
TOOLS = [create_review_ticket, record_human_verdict]


def summarise(record: dict[str, Any]) -> str:
    """One paragraph for the reviewer: who, what, how much, why it is here."""
    i, d = record["intake"], record["decision"]
    return (f"{record['claim_id']} · {i['patient']} · {i['diagnosis']} · claimed ₹{format_inr(i['claimed'])}, "
            f"recommended ₹{format_inr(d['payout'])}. Escalated for: {', '.join(d['escalation_reasons'])}. "
            f"Fraud score {record['fraud']['score']}.")


def run_sync(claim_id: str) -> dict[str, Any]:
    """Open a review ticket for an escalated claim (the human verdict comes later via ``review``)."""
    record = read_state(claim_id)
    if record["status"] != "escalated":
        return record
    ticket = create_review_ticket(claim_id, summarise(record))
    log_step(claim_id, AGENT_ID, "create_review_ticket", f"{ticket['ticket']} waiting for a reviewer")
    return read_state(claim_id)


def review(claim_id: str, verdict: str, note: str, *, reviewer: str = "reviewer",
           payout: int | None = None) -> dict[str, Any]:
    """The reviewer's decision: approve / partial / reject with a note → closes the claim."""
    out = record_human_verdict(claim_id, verdict, note, reviewer=reviewer, payout=payout)
    log_step(claim_id, AGENT_ID, "record_human_verdict", f"{verdict} by {reviewer}, payout {out['human']['payout']}")
    return out


async def run(claim_id: str) -> dict[str, Any]:
    """Read the claim state, call this agent's tools, write its own section(s)."""
    return await asyncio.to_thread(run_sync, claim_id)
