"""Tests for the Adjudication Manager tools (M8–M10) and the Human Review Desk tools (M11)."""

from __future__ import annotations

from pathlib import Path

import pytest

import tools.decision_tools as dt
import tools.logger as logger
import tools.state as state
from tools.decision_tools import (
    apply_decision_rules,
    create_review_ticket,
    format_inr,
    record_human_verdict,
    review_queue,
    verify_citations,
    write_decision,
)
from tools.intake_tools import load_policies

ASJ = load_policies()["ASJ-01"]
GOOD = {"IRDAI:List-I": 1.0, "ASJ-01:9.3": 1.0, "ASJ-01:4.1.i": 0.87, "ASJ-01:4.1.1.note2": 1.0, "ASJ-01:6.3.i": 0.5}


def record(claimed=85000, deductions=None, payable=79610, fraud=0, waiting=None, retrieved=GOOD, limits=ASJ):
    deductions = [{"item": "Gloves", "amount": 450, "reason": "non-payable item", "clause_id": "IRDAI:List-I"},
                  {"item": "Co-payment 5%", "amount": 4190, "reason": "co-pay", "clause_id": "ASJ-01:9.3"}] \
        if deductions is None else deductions
    return {"claim_id": "CLM-0001", "status": "assessing",
            "intake": {"policy_id": limits["policy_id"], "claimed": claimed},
            "policy": {"limits": limits, "clauses": [{"clause_id": c, "text": "…", "score": s} for c, s in retrieved.items()]},
            "fraud": {"score": fraud, "reasons": [], "details": [], "waiting_period": waiting},
            "cost": {"deductions": deductions, "payable": payable, "overclaim": False}}


@pytest.mark.parametrize("amount,text", [(850, "850"), (79610, "79,610"), (426550, "4,26,550"), (15123000, "1,51,23,000")])
def test_format_inr(amount, text):
    assert format_inr(amount) == text


# ---------- verify_citations (M9) ----------

def test_citation_guard():
    assert verify_citations(["A:1", "A:2"], ["A:1", "A:2", "A:3"]) == {"ok": True, "missing": []}
    assert verify_citations(["A:1", "A:9", "A:9"], ["A:1"]) == {"ok": False, "missing": ["A:9"]}
    assert verify_citations([], []) == {"ok": True, "missing": []}


# ---------- apply_decision_rules (M8, M10) ----------

def test_scenario_1_shape_routine_deductions_approve():
    d = apply_decision_rules(record())
    assert (d["verdict"], d["payout"], d["clauses"], d["escalation_reasons"]) == (
        "approve", 79610, ["IRDAI:List-I", "ASJ-01:9.3"], [])
    assert d["confidence"] == 1.0
    assert "₹79,610 of ₹85,000" in d["rationale"]


def test_scenario_2_shape_room_cap_is_partial():
    ded = [{"item": "Room + nursing (4 days)", "amount": 12000, "reason": "cap", "clause_id": "ASJ-01:4.1.i"},
           {"item": "Consultant visits", "amount": 4500, "reason": "prop", "clause_id": "ASJ-01:4.1.1.note2"},
           {"item": "Co-payment 5%", "amount": 2575, "reason": "co-pay", "clause_id": "ASJ-01:9.3"}]
    d = apply_decision_rules(record(claimed=72000, deductions=ded, payable=48925))
    assert (d["verdict"], d["payout"]) == ("partial", 48925)
    assert d["clauses"] == ["ASJ-01:4.1.i", "ASJ-01:4.1.1.note2", "ASJ-01:9.3"]
    assert d["confidence"] == 0.87                     # weakest cited clause


def test_scenario_3_shape_waiting_period_rejects():
    wait = {"excluded": True, "rule": "specific_conditions", "condition": "hernia of all types",
            "clause_id": "ASJ-01:6.3.i", "waiting_ends": "2028-01-01", "accident": False}
    d = apply_decision_rules(record(claimed=77000, payable=73150, waiting=wait,
                                    retrieved={**GOOD, "ASJ-01:6.3.i": 0.6}))
    assert (d["verdict"], d["payout"], d["clauses"]) == ("reject", 0, ["ASJ-01:6.3.i"])
    assert "hernia of all types" in d["rationale"] and "2028-01-01" in d["rationale"]


def test_scenario_4_shape_high_value_escalates_with_recommendation():
    d = apply_decision_rules(record(claimed=450000, payable=426550))
    assert (d["verdict"], d["payout"], d["escalation_reasons"]) == ("escalate", 426550, ["high_value"])
    assert d["rationale"].startswith("Escalated to a human reviewer")


def test_scenario_5_shape_fraud_score_escalates():
    d = apply_decision_rules(record(claimed=99300, payable=94050, fraud=75))
    assert d["escalation_reasons"] == ["fraud_risk"]


def test_threshold_edges():
    assert apply_decision_rules(record(claimed=200000))["verdict"] == "approve"      # not above ₹2,00,000
    assert apply_decision_rules(record(fraud=59))["verdict"] == "approve"
    assert apply_decision_rules(record(fraud=60))["escalation_reasons"] == ["fraud_risk"]


def test_scenario_6_shape_no_grounding_never_auto_decides():
    d = apply_decision_rules(record(claimed=42000, deductions=[], payable=42000,
                                    retrieved={}, limits=load_policies()["GHC-01"]))
    assert (d["verdict"], d["escalation_reasons"], d["clauses"], d["confidence"]) == (
        "escalate", ["no_grounding"], [], 0.0)
    assert "no grounding clause found" in d["rationale"]


def test_citing_an_unretrieved_clause_escalates():
    d = apply_decision_rules(record(retrieved={"IRDAI:List-I": 1.0}))       # 9.3 never retrieved
    assert d["escalation_reasons"] == ["citation_failed", "low_confidence"]
    assert "ASJ-01:9.3" in d["rationale"]


def test_weak_grounding_escalates_on_confidence():
    d = apply_decision_rules(record(retrieved={"IRDAI:List-I": 1.0, "ASJ-01:9.3": 0.5}))
    assert d["escalation_reasons"] == ["low_confidence"] and d["confidence"] == 0.5


def test_reasons_accumulate_in_a_fixed_order():
    d = apply_decision_rules(record(claimed=450000, fraud=80))
    assert d["escalation_reasons"] == ["high_value", "fraud_risk"]


# ---------- write_decision + Human Review Desk (temp state) ----------

@pytest.fixture()
def tmp_paths(tmp_path, monkeypatch):
    paths = {"state_dir": tmp_path / "state", "run_log": tmp_path / "logs" / "run_log.jsonl",
             "review_queue": tmp_path / "state" / "review_queue.json"}

    def fake(key: str) -> Path:
        return paths[key]

    for mod in (state, logger, dt):
        monkeypatch.setattr(mod, "project_path", fake)
    return paths


def seed(claim_id="CLM-0004", claimed=450000):
    state.write_state(claim_id, "intake", {"policy_id": "ASJ-01", "patient": "Test", "admit": "2026-10-05",
                                           "discharge": "2026-10-10", "diagnosis": "PTCA", "room_type": "twin",
                                           "claimed": claimed}, agent="intake_agent")
    state.set_status(claim_id, "assessing", agent="workflow")


def test_auto_decision_closes_the_claim(tmp_paths):
    seed("CLM-0001", 85000)
    rec = record()
    rec["claim_id"] = "CLM-0001"
    out = write_decision(rec)
    assert out["status"] == "closed" and out["decision"]["verdict"] == "approve"
    assert [t.get("to") for t in out["trace"] if t["action"] == "status"] == ["assessing", "decided", "closed"]


def test_escalation_then_human_approval_closes_scenario_4(tmp_paths):
    seed()
    rec = record(claimed=450000, payable=426550)
    rec["claim_id"] = "CLM-0004"
    assert write_decision(rec)["status"] == "escalated"

    ticket = create_review_ticket("CLM-0004", "PTCA, ₹4,50,000 claimed, recommended ₹4,26,550")
    assert ticket["ticket"] == "RV-0001" and [t["claim_id"] for t in review_queue()] == ["CLM-0004"]
    assert create_review_ticket("CLM-0004", "again")["ticket"] == "RV-0001"      # one open ticket per claim
    assert state.read_state("CLM-0004")["human"]["ticket"] == "RV-0001"

    closed = record_human_verdict("CLM-0004", "approve", "Stent invoices match; approve as recommended.",
                                  reviewer="Dr. Reviewer")
    assert closed["status"] == "closed"
    assert closed["human"] == {"ticket": "RV-0001", "reviewer": "Dr. Reviewer", "verdict": "approve",
                               "note": "Stent invoices match; approve as recommended.", "payout": 426550}
    assert review_queue() == [] and review_queue(open_only=False)[0]["status"] == "closed"
    agents = [e["agent"] for e in logger.read_log("CLM-0004")]
    assert "human_desk" in agents and "manager_agent" in agents


def test_human_reject_and_partial_payouts(tmp_paths):
    for cid in ("CLM-0005", "CLM-0006"):
        seed(cid, 99300)
        rec = record(claimed=99300, payable=94050, fraud=75)
        rec["claim_id"] = cid
        write_decision(rec)
        create_review_ticket(cid, "fraud check")
    assert record_human_verdict("CLM-0005", "reject", "Bill reused from PC-0017.")["human"]["payout"] == 0
    with pytest.raises(ValueError):
        record_human_verdict("CLM-0006", "partial", "half", payout=200000)          # above recommendation
    assert record_human_verdict("CLM-0006", "partial", "Pay surgery only.", payout=50000)["human"]["payout"] == 50000


def test_human_verdict_needs_an_escalated_claim_and_a_note(tmp_paths):
    seed()
    with pytest.raises(ValueError, match="not waiting"):
        record_human_verdict("CLM-0004", "approve", "ok")
    rec = record(claimed=450000, payable=426550)
    rec["claim_id"] = "CLM-0004"
    write_decision(rec)
    create_review_ticket("CLM-0004", "s")
    with pytest.raises(ValueError, match="note"):
        record_human_verdict("CLM-0004", "approve", "  ")
    with pytest.raises(ValueError, match="verdict"):
        record_human_verdict("CLM-0004", "escalate", "again")
