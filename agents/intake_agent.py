"""Intake Agent — Turns claim text + bill into a structured record.

Features: M1, M2
Writes to claim state: ``intake``, ``bill_items`` (and nothing else).
Tools: extract_claim_fields, llm_extract_claim_fields + reconcile_fields, parse_bill, validate_policy
(tools/intake_tools.py; the LLM goes through tools/llm_client.py).
Note: Halts (status stays 'intake') when policy id or claimed amount is missing — no downstream agent runs (scenario 7).
The rules read the message first and decide any halt; then, when the LLM path is on, an
open-weight model reads it too. The rules win every disagreement (logged); the LLM only fills
fields the rules could not read, and never the policy id or an amount. No key, a cap reached
or a provider error → the rule result is used and the reason is logged.

Agents never import each other; they communicate only through the claim-state
record (tools/state.py) and workflow.py. ``run_sync`` holds the agent's steps;
``run`` is the async entry point that this agent's Microsoft Agent Framework
executor in workflow.py awaits.
"""

from __future__ import annotations

import asyncio
from typing import Any

from tools.config import project_path
from tools.intake_tools import (
    IntakeHalt,
    extract_claim_fields,
    llm_extract_claim_fields,
    parse_bill,
    reconcile_fields,
    validate_policy,
)
from tools.llm_client import LlmUnavailable, budget_line, llm_enabled
from tools.logger import log_step
from tools.state import read_state, set_halt, write_state

AGENT_NAME = "Intake Agent"
AGENT_ID = "intake_agent"
STATE_SECTIONS = ('intake', 'bill_items')
TOOLS = [extract_claim_fields, llm_extract_claim_fields, reconcile_fields, parse_bill, validate_policy]


def _llm_cross_check(claim_id: str, text: str, fields: dict[str, Any]) -> dict[str, Any]:
    """Second reading by the open-weight model; returns the (rule-led) merged fields."""
    if not llm_enabled():
        log_step(claim_id, AGENT_ID, "llm_extract_claim_fields", "skipped — LLM path off, rules only")
        return fields
    try:
        result = llm_extract_claim_fields(text)
    except LlmUnavailable as exc:
        log_step(claim_id, AGENT_ID, "llm_extract_claim_fields", f"rules only — {exc}", llm_reasons=exc.reasons)
        return fields
    merged, report = reconcile_fields(fields, result["fields"])
    mism = report["mismatches"]
    summary = (f"{result['provider']} ({result['model']}): {len(report['agreed'])} fields agree"
               + (f", filled {', '.join(report['filled'])}" if report["filled"] else "")
               + (f", rules kept on {', '.join(mism)}" if mism else "")
               + f" · {budget_line(result['budget'])}")
    log_step(claim_id, AGENT_ID, "reconcile_fields", summary,
             llm={"provider": result["provider"], "model": result["model"], "tokens": result["tokens"],
                  "budget_left": result["budget"]["left"], **report})
    return merged


def run_sync(claim_id: str) -> dict[str, Any]:
    """Read ``data/claims/<id>/claim.txt`` (+ ``bill.csv``), write intake + bill_items, or halt."""
    folder = project_path("claims") / claim_id
    log_step(claim_id, AGENT_ID, "start", "reading claim message and bill")
    try:
        text = (folder / "claim.txt").read_text(encoding="utf-8")
        fields = extract_claim_fields(text)
        log_step(claim_id, AGENT_ID, "extract_claim_fields",
                 f"policy {fields['policy_id']}, claimed {fields['claimed']}, diagnosis: {fields['diagnosis']}")
        fields = _llm_cross_check(claim_id, text, fields)
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
