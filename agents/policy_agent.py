"""Policy Retrieval Agent — RAG over policy wordings and IRDAI rules; returns governing clauses and limits.

Features: M3
Writes to claim state: ``policy`` (and nothing else).
Tools: search_policy_clauses, get_policy_limits, search_irdai_rules (tools/retrieval_tools.py).
Note: Runs in parallel with the Fraud Signal Agent. Posts limits first so Cost Assessment can start.

Agents never import each other; they communicate only through the claim-state
record (tools/state.py) and workflow.py. ``run_sync`` holds the agent's steps;
``run`` is the async entry point that this agent's Microsoft Agent Framework
executor in workflow.py awaits.
"""

from __future__ import annotations

import asyncio
import re
from typing import Any

from tools.logger import log_step
from tools.retrieval_tools import (
    get_policy_limits,
    search_irdai_rules,
    search_policy_clauses,
)
from tools.state import read_state, write_state

AGENT_NAME = "Policy Retrieval Agent"
AGENT_ID = "policy_agent"
STATE_SECTIONS = ('policy',)
TOOLS = [search_policy_clauses, get_policy_limits, search_irdai_rules]

# One plain query per limit or rule the Cost agent and the Manager may need to cite.
STANDARD_QUERIES = [
    "room rent boarding nursing expenses per day limit",
    "intensive care unit ICU expenses per day limit",
    "rates exceeding limits proportion other expenses",
    "co-payment admissible claim",
    "first thirty days waiting period illness",
    "pre-existing disease waiting period",
]
IRDAI_QUERIES = [
    "items for which coverage is not available",
    "items subsumed into room charges",
    "subsumed into procedure charges",
    "items subsumed into costs of treatment",
]


def plan_queries(intake: dict[str, Any], limits: dict[str, Any]) -> list[str]:
    """Standard limit queries plus condition-specific ones built from the policy's own terms."""
    diagnosis = intake.get("diagnosis", "").lower()
    queries = list(STANDARD_QUERIES)
    for terms in limits.get("condition_terms", {}).values():
        hit = next((t for t in terms if re.search(rf"\b{re.escape(t)}", diagnosis)), None)
        if hit:
            queries.append(f"waiting period {hit}")
    if any(re.search(rf"\b{re.escape(t)}", diagnosis) for t in limits.get("joint_replacement_terms", [])):
        queries.append("joint replacement waiting period")
    if "cataract" in diagnosis:
        queries.append("cataract treatment limit")
    return queries


def post_limits(claim_id: str) -> dict[str, Any]:
    """Step 1: post the structured limits so Cost Assessment can start."""
    intake = read_state(claim_id)["intake"]
    log_step(claim_id, AGENT_ID, "start", f"limits + clauses for {intake['policy_id']}")
    limits = get_policy_limits(intake["policy_id"])
    log_step(claim_id, AGENT_ID, "get_policy_limits",
             f"SI {limits['sum_insured']}, room cap {limits['room_cap_per_day']}/day, co-pay {limits['copay_pct']}%")
    return write_state(claim_id, "policy", {"limits": limits, "clauses": []}, agent=AGENT_ID)


def retrieve(claim_id: str) -> dict[str, Any]:
    """Step 2: retrieve the governing clauses (policy wording, filtered by policy id, + IRDAI lists)."""
    record = read_state(claim_id)
    intake, limits = record["intake"], record["policy"]["limits"]
    found: dict[str, dict[str, Any]] = {}
    for query in plan_queries(intake, limits):
        hits = search_policy_clauses(intake["policy_id"], query)
        log_step(claim_id, AGENT_ID, "search_policy_clauses", f"'{query}' -> {[h['clause_id'] for h in hits[:3]]}")
        for h in hits:
            if h["score"] > found.get(h["clause_id"], {}).get("score", -1):
                found[h["clause_id"]] = {"clause_id": h["clause_id"], "text": h["text"], "score": h["score"]}
    for query in IRDAI_QUERIES:
        hits = search_irdai_rules(query, k=1)
        log_step(claim_id, AGENT_ID, "search_irdai_rules", f"'{query}' -> {[h['clause_id'] for h in hits]}")
        for h in hits:
            found.setdefault(h["clause_id"], {"clause_id": h["clause_id"], "text": h["text"], "score": h["score"]})
    clauses = sorted(found.values(), key=lambda c: (-c["score"], c["clause_id"]))
    log_step(claim_id, AGENT_ID, "done", f"{len(clauses)} clauses above the similarity threshold")
    return write_state(claim_id, "policy", {"limits": limits, "clauses": clauses}, agent=AGENT_ID)


def run_sync(claim_id: str) -> dict[str, Any]:
    post_limits(claim_id)
    return retrieve(claim_id)


async def run(claim_id: str) -> dict[str, Any]:
    """Read the claim state, call this agent's tools, write its own section(s)."""
    return await asyncio.to_thread(run_sync, claim_id)
