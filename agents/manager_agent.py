"""Adjudication Manager — Fans in all signals, decides, cites clauses, routes to a human when needed.

Features: M7, M8, M9, M10
Writes to claim state: ``decision`` (and nothing else).
Tools: apply_decision_rules, verify_citations, write_decision (tools/decision_tools.py).
Note: A verdict may only cite clause ids that were actually retrieved (citation guard).

Agents never import each other; they communicate only through the claim-state
record (tools/state.py) and workflow.py. ``run_sync`` holds the agent's steps;
``run`` is the async entry point the workflow awaits. When the agent framework is
chosen (open question in context/05-progress.md), each ``run_sync`` becomes the
body of that framework's agent/executor — the tools and state contract stay the same.
"""

from __future__ import annotations

import asyncio
from typing import Any

from tools.decision_tools import (
    apply_decision_rules,
    verify_citations,
    write_decision,
)
from tools.logger import log_step
from tools.state import read_state

AGENT_NAME = "Adjudication Manager"
AGENT_ID = "manager_agent"
STATE_SECTIONS = ('decision',)
TOOLS = [apply_decision_rules, verify_citations, write_decision]


def run_sync(claim_id: str) -> dict[str, Any]:
    record = read_state(claim_id)
    missing = [s for s in ("intake", "policy", "fraud", "cost") if not record.get(s)]
    if missing:
        raise RuntimeError(f"{claim_id}: the Manager fans in after {missing} are written")
    log_step(claim_id, AGENT_ID, "start", "fan-in: policy, fraud and cost signals")
    decision = apply_decision_rules(record)
    log_step(claim_id, AGENT_ID, "apply_decision_rules",
             f"{decision['verdict']} payout {decision['payout']} {decision['escalation_reasons'] or ''}".strip())
    guard = verify_citations(decision["clauses"], [c["clause_id"] for c in record["policy"]["clauses"]])
    log_step(claim_id, AGENT_ID, "verify_citations",
             f"cited {decision['clauses']} — {'all retrieved' if guard['ok'] else 'missing ' + str(guard['missing'])}")
    out = write_decision(record, decision)
    log_step(claim_id, AGENT_ID, "write_decision", f"status {out['status']}")
    return out


async def run(claim_id: str) -> dict[str, Any]:
    """Read the claim state, call this agent's tools, write its own section(s)."""
    return await asyncio.to_thread(run_sync, claim_id)
