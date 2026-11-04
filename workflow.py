"""ClaimLens workflow — fan-out / fan-in orchestration with human routing (M7, M10, M11).

Built on **Microsoft Agent Framework** workflows (``agent-framework-core``): each agent is an
executor, the graph below is a ``WorkflowBuilder`` with fan-out and fan-in edge groups, and the
framework runs ready executors concurrently (synchronous agent steps run in its thread pool).

    intake ──fan-out──► policy_limits ──fan-out──► policy_retrieve ─┐
       │                                     └───► cost ────────────┼─ fan-in ─► manager ──► human_desk
       └────────fan-out──► fraud ──────────────────────────────────┘              │ (escalated)
                                                                              (auto: closed)

- Policy Retrieval and Fraud Signal start together after intake.
- Cost starts as soon as Policy has posted the limits, while Policy keeps retrieving clauses.
- The Manager runs once all three branches have delivered (fan-in).
- An intake halt (scenario 7) or an auto decision ends the run; an escalation opens a review
  ticket and the run ends with status ``escalated``; ``human_desk.review(...)`` closes it.

Agents never message each other's data: the only message on the edges is the claim id. Everything
else goes through the shared claim-state record (``tools.state``).
"""

from __future__ import annotations

import asyncio
import sys
from typing import Any

from agent_framework import Workflow, WorkflowBuilder, WorkflowContext, executor

from agents import cost_agent, fraud_agent, human_desk, intake_agent, manager_agent, policy_agent
from tools.config import DISCLAIMER
from tools.logger import log_step
from tools.state import read_state, reset_state, set_status

AGENTS = [intake_agent, policy_agent, fraud_agent, cost_agent, manager_agent, human_desk]


def build_workflow() -> Workflow:
    """The ClaimLens graph as a Microsoft Agent Framework workflow. Message on every edge: the claim id."""

    @executor(id="intake")
    async def intake(claim_id: str, ctx: WorkflowContext[str, str]) -> None:
        log_step(claim_id, "workflow", "start", "intake")
        record = await intake_agent.run(claim_id)
        if record.get("halt"):
            log_step(claim_id, "workflow", "stop", f"intake halted: {record['halt']['reason']}")
            await ctx.yield_output(claim_id)               # nothing downstream runs
            return
        set_status(claim_id, "assessing", agent="workflow")
        log_step(claim_id, "workflow", "fan-out", "Policy Retrieval and Fraud Signal start together")
        await ctx.send_message(claim_id)

    @executor(id="policy_limits")
    async def policy_limits(claim_id: str, ctx: WorkflowContext[str]) -> None:
        await asyncio.to_thread(policy_agent.post_limits, claim_id)
        await ctx.send_message(claim_id)                   # → retrieval and Cost, in parallel

    @executor(id="policy_retrieve")
    async def policy_retrieve(claim_id: str, ctx: WorkflowContext[str]) -> None:
        await asyncio.to_thread(policy_agent.retrieve, claim_id)
        await ctx.send_message(claim_id)

    @executor(id="fraud")
    async def fraud(claim_id: str, ctx: WorkflowContext[str]) -> None:
        await fraud_agent.run(claim_id)
        await ctx.send_message(claim_id)

    @executor(id="cost")
    async def cost(claim_id: str, ctx: WorkflowContext[str]) -> None:
        await cost_agent.run(claim_id)
        await ctx.send_message(claim_id)

    @executor(id="manager")
    async def manager(claim_ids: list[str], ctx: WorkflowContext[str, str]) -> None:
        claim_id = claim_ids[0]
        log_step(claim_id, "workflow", "fan-in", "policy, fraud and cost signals in; Manager decides")
        record = await manager_agent.run(claim_id)
        if record["status"] == "escalated":
            await ctx.send_message(claim_id)
        else:
            log_step(claim_id, "workflow", "done", f"status {record['status']}")
            await ctx.yield_output(claim_id)

    @executor(id="human_desk")
    async def desk(claim_id: str, ctx: WorkflowContext[str, str]) -> None:
        record = await human_desk.run(claim_id)
        log_step(claim_id, "workflow", "done", f"status {record['status']} — waiting for a reviewer")
        await ctx.yield_output(claim_id)

    return (
        WorkflowBuilder(name="claimlens", description="Health-claim adjudication: fan-out / fan-in with human routing",
                        start_executor=intake)
        .add_fan_out_edges(intake, [policy_limits, fraud])
        .add_fan_out_edges(policy_limits, [policy_retrieve, cost])
        .add_fan_in_edges([policy_retrieve, cost, fraud], manager)
        .add_edge(manager, desk)
        .build()
    )


async def run_claim(claim_id: str) -> dict:
    """Run one claim end to end and return the final claim-state record.

    Order: intake → (policy ∥ fraud) → cost after limits → manager → auto or human desk.
    If intake halts (missing policy id / amount, scenario 7), no downstream agent runs.
    An escalated claim comes back with status ``escalated`` and an open review ticket;
    ``human_desk.review(...)`` records the reviewer's verdict and closes it.
    """
    reset_state(claim_id)
    await build_workflow().run(claim_id)
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
