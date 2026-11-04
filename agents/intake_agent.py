"""Intake Agent — Turns claim text + bill into a structured record.

Features: M1, M2
Writes to claim state: ``intake``, ``bill_items`` (and nothing else).
Tools: extract_claim_fields, parse_bill, validate_policy (tools/intake_tools.py).
Note: Halts (status stays 'intake') when policy id or claimed amount is missing — no downstream agent runs (scenario 7).

Agents never import each other; they communicate only through the claim-state
record (tools/state.py) and workflow.py. ``run_sync`` holds the agent's steps;
``run`` is the async entry point the workflow awaits. When the agent framework is
chosen (open question in context/05-progress.md), each ``run_sync`` becomes the
body of that framework's agent/executor — the tools and state contract stay the same.
"""

from __future__ import annotations

import asyncio
from typing import Any

from tools.config import project_path
from tools.intake_tools import (
    IntakeHalt,
    extract_claim_fields,
    parse_bill,
    validate_policy,
)
from tools.logger import log_step
from tools.state import read_state, set_halt, write_state

AGENT_NAME = "Intake Agent"
AGENT_ID = "intake_agent"
STATE_SECTIONS = ('intake', 'bill_items')
TOOLS = [extract_claim_fields, parse_bill, validate_policy]


def run_sync(claim_id: str) -> dict[str, Any]:
    """Read ``data/claims/<id>/claim.txt`` (+ ``bill.csv``), write intake + bill_items, or halt."""
    folder = project_path("claims") / claim_id
    log_step(claim_id, AGENT_ID, "start", "reading claim message and bill")
    try:
        fields = extract_claim_fields((folder / "claim.txt").read_text(encoding="utf-8"))
        log_step(claim_id, AGENT_ID, "extract_claim_fields",
                 f"policy {fields['policy_id']}, claimed {fields['claimed']}, diagnosis: {fields['diagnosis']}")
        validate_policy(fields["policy_id"])
        log_step(claim_id, AGENT_ID, "validate_policy", f"{fields['policy_id']} found in policies.json")
        bill = next((folder / n for n in ("bill.csv", "bill.json") if (folder / n).exists()), None)
        if bill is None:
            raise IntakeHalt("final bill is missing — ask the claimant for the itemised final bill",
                             reason="missing_bill")
        items = parse_bill(bill)
        log_step(claim_id, AGENT_ID, "parse_bill", f"{len(items)} line items, total {sum(i['amount'] for i in items)}")
    except IntakeHalt as halt:
        log_step(claim_id, AGENT_ID, "halt", str(halt))
        return set_halt(claim_id, halt.reason or "invalid_bill", str(halt), agent=AGENT_ID)
    write_state(claim_id, "intake", fields, agent=AGENT_ID)
    write_state(claim_id, "bill_items", items, agent=AGENT_ID)
    return read_state(claim_id)


async def run(claim_id: str) -> dict[str, Any]:
    """Read the claim state, call this agent's tools, write its own section(s)."""
    return await asyncio.to_thread(run_sync, claim_id)
