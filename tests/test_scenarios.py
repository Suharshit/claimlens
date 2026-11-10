"""Test layers 2 and 3: full-workflow scenario tests and the run-log test.

All seven scenarios from 03-features-and-scope. For each: assert verdict, payout
and that every cited clause id exists in the retrieved set. Expected values come
from the hand-worked data/claims/<id>/expected.json, never from the code under test.
Every run writes to a temporary runtime folder (CLAIMLENS_RUNTIME_DIR).
"""

from __future__ import annotations

import asyncio
import json

import pytest

from agents import human_desk
from tools.config import project_path
from tools.logger import read_log
from tools.schemas import ExpectedOutcome
from tools.state import read_state
from workflow import run_claim

SCENARIOS = [
    (1, "Clean approval", "approve"),
    (2, "Partial: room-rent breach", "partial"),
    (3, "Reject: waiting period", "reject"),
    (4, "High value → human", "escalate"),       # then human closes it
    (5, "Fraud signal", "escalate"),             # risk >= 60, both reasons
    (6, "Honest failure: no grounding", "escalate"),
    (7, "Missing data", "halt"),                 # intake halts, nothing downstream
]
CLAIM = {n: f"CLM-{n:04d}" for n, _, _ in SCENARIOS}
DOWNSTREAM = {"policy_agent", "fraud_agent", "cost_agent", "manager_agent"}


@pytest.fixture(autouse=True)
def runtime(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAIMLENS_RUNTIME_DIR", str(tmp_path))
    return tmp_path


def expected(claim_id: str) -> dict:
    raw = json.loads((project_path("claims") / claim_id / "expected.json").read_text(encoding="utf-8"))
    return ExpectedOutcome.model_validate(raw).model_dump(mode="json")      # fills the defaults


def run(claim_id: str) -> dict:
    return asyncio.run(run_claim(claim_id))


@pytest.mark.parametrize("number,title,expected_verdict", SCENARIOS)
def test_scenario(number, title, expected_verdict):
    cid = CLAIM[number]
    exp = expected(cid)
    rec = run(cid)

    if expected_verdict == "halt":
        assert rec["halt"]["reason"] == exp["halt"]
        assert rec["status"] == exp["final_status"] == "intake"
        assert rec["decision"] is None and rec["cost"] is None
        agents = {e["agent"] for e in read_log(cid)}
        assert not agents & DOWNSTREAM, "no downstream agent may run after an intake halt"
        return

    d = rec["decision"]
    assert d["verdict"] == exp["verdict"] == expected_verdict
    assert d["payout"] == exp["payable"]
    assert d["clauses"] == exp["clauses"]
    retrieved = {c["clause_id"] for c in rec["policy"]["clauses"]}
    assert set(d["clauses"]) <= retrieved, "citation guard: every cited clause must have been retrieved"
    assert d["escalation_reasons"] == exp["escalation_reasons"]
    assert set(exp["fraud_reasons"]) <= set(rec["fraud"]["reasons"])
    if exp.get("fraud_min_score") is not None:
        assert rec["fraud"]["score"] >= exp["fraud_min_score"]
    if exp["verdict"] != "reject":                         # a rejection's cost is bill-level only
        assert rec["cost"]["deductions"] == exp["deductions"]
        assert rec["cost"]["overclaim"] == exp["overclaim"]

    if exp.get("human_verdict"):                           # scenario 4: reviewer closes it
        assert rec["status"] == "escalated" and rec["human"]["ticket"]
        rec = human_desk.review(cid, exp["human_verdict"], "Invoices and angiography match; approve as recommended.",
                                reviewer="Test Reviewer")
        assert rec["human"]["verdict"] == exp["human_verdict"]
        assert rec["human"]["payout"] == exp["payable"]
    assert rec["status"] == exp["final_status"]


def test_scenario_6_says_no_grounding_clause_found():
    rec = run("CLM-0006")
    assert "no grounding clause found" in rec["decision"]["rationale"]
    assert not [c for c in rec["policy"]["clauses"] if c["clause_id"].startswith("GHC-01:")]


def test_policy_and_fraud_run_in_parallel_and_cost_waits_for_limits():
    run("CLM-0002")
    log = read_log("CLM-0002")
    first = {}
    for i, e in enumerate(log):
        first.setdefault((e["agent"], e.get("tool")), i)
    fan_out = first[("workflow", "fan-out")]
    limits_written = next(i for i, e in enumerate(log) if e.get("tool") == "write_state" and e.get("section") == "policy")
    assert first[("policy_agent", "start")] > fan_out and first[("fraud_agent", "start")] > fan_out
    assert first[("cost_agent", "start")] > limits_written        # Cost waits for the posted limits
    fan_in = first[("workflow", "fan-in")]
    assert all(first[(a, "start")] < fan_in for a in ("policy_agent", "fraud_agent", "cost_agent"))
    assert first[("manager_agent", "start")] > fan_in


def test_each_agent_writes_only_its_own_section():
    run("CLM-0004")
    owners = {"intake": "intake_agent", "bill_items": "intake_agent", "policy": "policy_agent",
              "fraud": "fraud_agent", "cost": "cost_agent", "decision": "manager_agent", "human": "human_desk"}
    writes = [e for e in read_log("CLM-0004") if e.get("tool") == "write_state"]
    assert writes and all(owners[e["section"]] == e["agent"] for e in writes)


def test_rerun_starts_afresh():
    run("CLM-0001")
    rec = run("CLM-0001")
    assert rec["status"] == "closed"
    assert rec["trace"][0]["action"] == "reset"
    assert sum(1 for t in rec["trace"] if t.get("section") == "decision") == 1


def test_run_log_is_append_only(runtime):
    log_file = runtime / "logs" / "run_log.jsonl"
    run("CLM-0001")
    before = log_file.read_text(encoding="utf-8").splitlines()
    run("CLM-0005")
    after = log_file.read_text(encoding="utf-8").splitlines()
    assert after[: len(before)] == before and len(after) > len(before)
    for cid, agents in {"CLM-0001": {"intake_agent", *DOWNSTREAM},
                        "CLM-0005": {"intake_agent", *DOWNSTREAM, "human_desk"}}.items():
        assert agents <= {e["agent"] for e in read_log(cid)}, f"every agent must appear in {cid}'s trace"
        assert {t["agent"] for t in read_state(cid)["trace"]} >= agents - {"human_desk"} | {"workflow"}


def test_rerun_of_an_escalated_claim_keeps_its_review_ticket():
    """A claim still waiting for a reviewer can be re-run (e.g. from the demo website) and reviewed."""
    first = run("CLM-0004")
    again = run("CLM-0004")
    assert again["status"] == "escalated"
    assert again["human"]["ticket"] == first["human"]["ticket"]       # same ticket, written back
    rec = human_desk.review("CLM-0004", "approve", "Re-run checked; approve.", reviewer="Test Reviewer")
    assert rec["status"] == "closed"
