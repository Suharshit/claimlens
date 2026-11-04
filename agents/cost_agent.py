"""Cost Assessment Agent — Computes the payable amount line by line; flags over-claiming.

Features: M4, M5, S1
Writes to claim state: ``cost`` (and nothing else).
Tools: classify_items, room_rent_deduction, compute_payable (tools/cost_tools.py).
Note: Waits for policy limits — the one ordered step. The LLM never does arithmetic here.

Agents never import each other; they communicate only through the claim-state
record (tools/state.py) and workflow.py. ``run_sync`` holds the agent's steps;
``run`` is the async entry point the workflow awaits. When the agent framework is
chosen (open question in context/05-progress.md), each ``run_sync`` becomes the
body of that framework's agent/executor — the tools and state contract stay the same.
"""

from __future__ import annotations

import asyncio
from typing import Any

from tools.cost_tools import (
    classify_items,
    compute_payable,
    room_rent_deduction,
)
from tools.logger import log_step
from tools.state import read_state, write_state

AGENT_NAME = "Cost Assessment Agent"
AGENT_ID = "cost_agent"
STATE_SECTIONS = ('cost',)
TOOLS = [classify_items, room_rent_deduction, compute_payable]

# Treatments that carry a sub-limit in ASJ-01 (4.3 cataract, 4.6 listed modern treatments).
MODERN_TREATMENT_TERMS = ("uterine artery embolization", "hifu", "balloon sinuplasty", "deep brain stimulation",
                          "oral chemotherapy", "immunotherapy", "intra vitreal", "intravitreal", "robotic",
                          "stereotactic", "bronchial thermoplasty", "vaporisation of the prostate", "ionm",
                          "stem cell")


def choose_sub_limit(diagnosis: str, limits: dict[str, Any]) -> str | None:
    text = diagnosis.lower()
    subs = limits.get("sub_limits", {})
    if "cataract" in text and "cataract_per_eye" in subs:
        return "cataract_per_eye"
    if any(t in text for t in MODERN_TREATMENT_TERMS) and "modern_treatments" in subs:
        return "modern_treatments"
    return None


def run_sync(claim_id: str) -> dict[str, Any]:
    record = read_state(claim_id)
    limits = (record.get("policy") or {}).get("limits")
    if not limits:
        raise RuntimeError(f"{claim_id}: Cost Assessment needs the policy limits first")
    items = record["bill_items"]
    log_step(claim_id, AGENT_ID, "start", f"{len(items)} bill lines against {limits['policy_id']} limits")

    classified = classify_items(items)
    excluded = [i["desc"] for i in classified if i["status"] != "payable"]
    log_step(claim_id, AGENT_ID, "classify_items", f"not payable: {excluded or 'none'}")
    cuts = [c["item"] for r in room_rent_deduction(classified, limits) for c in r["cuts"]]
    log_step(claim_id, AGENT_ID, "room_rent_deduction", f"cuts: {cuts or 'none'}")
    sub_limit = choose_sub_limit(record["intake"]["diagnosis"], limits)
    cost = compute_payable(classified, limits, sub_limit=sub_limit)
    log_step(claim_id, AGENT_ID, "compute_payable",
             f"payable {cost['payable']} of {sum(i['amount'] for i in items)}; over-claim {cost['overclaim']}")
    return write_state(claim_id, "cost", cost, agent=AGENT_ID)


async def run(claim_id: str) -> dict[str, Any]:
    """Read the claim state, call this agent's tools, write its own section(s)."""
    return await asyncio.to_thread(run_sync, claim_id)
