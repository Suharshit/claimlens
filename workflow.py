"""ClaimLens workflow — fan-out / fan-in orchestration with human routing (M7, M10, M11).

    Intake
      │
      ├── fan-out ──► Policy Retrieval ──(limits)──► Cost Assessment ─┐
      │                                                               ├─ fan-in ─► Adjudication Manager
      └── fan-out ──► Fraud Signal ───────────────────────────────────┘                 │
                                                                       auto ◄───────────┴───► escalate
                                                                         │                      │
                                                                  Auto decision        Human Review Desk
                                                                         └──────► Claim closed ◄┘

Concurrency: asyncio — each agent's steps run in a worker thread (``asyncio.to_thread``), so the
Policy and Fraud agents really do run at the same time; ``tools.state`` serialises their writes.
Cost starts as soon as Policy has posted the limits (an ``asyncio.Event``), while Policy keeps
retrieving clauses. The Manager waits for all three. When the agent framework is chosen, its
concurrent orchestration replaces this function; the agents' ``run_sync`` bodies stay as they are.
"""

from __future__ import annotations

import asyncio
import sys
from typing import Any

from agents import cost_agent, fraud_agent, human_desk, intake_agent, manager_agent, policy_agent
from tools.config import DISCLAIMER
from tools.logger import log_step
from tools.state import read_state, reset_state, set_status

AGENTS = [intake_agent, policy_agent, fraud_agent, cost_agent, manager_agent, human_desk]


async def run_claim(claim_id: str) -> dict:
    """Run one claim end to end and return the final claim-state record.

    Order: intake → (policy ∥ fraud) → cost after limits → manager → auto or human desk.
    If intake halts (missing policy id / amount, scenario 7), no downstream agent runs.
    An escalated claim comes back with status ``escalated`` and an open review ticket;
    ``human_desk.review(...)`` records the reviewer's verdict and closes it.
    """
    reset_state(claim_id)
    log_step(claim_id, "workflow", "start", "intake")
    record = await intake_agent.run(claim_id)
    if record.get("halt"):
        log_step(claim_id, "workflow", "stop", f"intake halted: {record['halt']['reason']}")
        return read_state(claim_id)

    set_status(claim_id, "assessing", agent="workflow")
    limits_posted = asyncio.Event()

    async def policy_branch() -> None:
        await asyncio.to_thread(policy_agent.post_limits, claim_id)
        limits_posted.set()
        await asyncio.to_thread(policy_agent.retrieve, claim_id)

    async def cost_branch() -> None:
        await limits_posted.wait()
        await cost_agent.run(claim_id)

    log_step(claim_id, "workflow", "fan-out", "Policy Retrieval and Fraud Signal start together")
    await asyncio.gather(policy_branch(), fraud_agent.run(claim_id), cost_branch())
    log_step(claim_id, "workflow", "fan-in", "policy, fraud and cost signals in; Manager decides")

    record = await manager_agent.run(claim_id)
    if record["status"] == "escalated":
        record = await human_desk.run(claim_id)
    log_step(claim_id, "workflow", "done", f"status {record['status']}")
    return read_state(claim_id)


def summary(record: dict[str, Any]) -> dict[str, Any]:
    """One line per claim for tables: verdict, payout, status, reasons."""
    d, h = record.get("decision") or {}, record.get("human") or {}
    return {
        "claim_id": record["claim_id"],
        "status": record["status"],
        "verdict": d.get("verdict") or ("halt" if record.get("halt") else None),
        "payout": h.get("payout") if h.get("payout") is not None else d.get("payout"),
        "clauses": d.get("clauses", []),
        "escalation": d.get("escalation_reasons", []),
        "fraud_score": (record.get("fraud") or {}).get("score"),
        "halt": (record.get("halt") or {}).get("reason"),
    }


if __name__ == "__main__":
    print(DISCLAIMER)
    for cid in sys.argv[1:] or ["CLM-0001"]:
        print(summary(asyncio.run(run_claim(cid))))
