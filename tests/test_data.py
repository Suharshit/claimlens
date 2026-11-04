"""Checks on the hand-typed data files: policies.json, prior_claims.json and the scenario claims.

These test the data, not the code: each expected.json must be internally consistent
(its own working adds up), so later code is checked against numbers a person worked out.
"""

from __future__ import annotations

import json

import pytest

from tools.config import load_config, project_path
from tools.intake_tools import load_policies, parse_bill
from tools.schemas import ExpectedOutcome, PriorClaim

CLAIMS = sorted(p.name for p in project_path("claims").iterdir() if p.is_dir())


def inr(amount: int) -> str:
    """Indian digit grouping: 450000 -> '4,50,000'."""
    s = str(amount)
    if len(s) <= 3:
        return s
    head, tail = s[:-3], s[-3:]
    groups = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    return ",".join([head, *groups, tail]) if head else ",".join([*groups, tail])


def expected(claim_id: str) -> ExpectedOutcome:
    path = project_path("claims") / claim_id / "expected.json"
    return ExpectedOutcome.model_validate(json.loads(path.read_text(encoding="utf-8")))


def prior_claims() -> list[PriorClaim]:
    raw = json.loads(project_path("prior_claims").read_text(encoding="utf-8"))
    return [PriorClaim.model_validate(c) for c in raw]


@pytest.mark.parametrize("amount,text", [(850, "850"), (85000, "85,000"), (450000, "4,50,000"), (15123000, "1,51,23,000")])
def test_inr_helper(amount, text):
    assert inr(amount) == text


# ---------- policies.json ----------

def test_policies_json_validates():
    assert {"ASJ-01", "GHC-01"} <= set(load_policies())


def test_asj01_caps_follow_the_standard_formula():
    p = load_policies()["ASJ-01"]
    si = p["sum_insured"]
    assert p["room_cap_per_day"] == min(si * 2 // 100, 5000)      # 2% of SI, max ₹5,000
    assert p["icu_cap_per_day"] == min(si * 5 // 100, 10000)      # 5% of SI, max ₹10,000
    assert p["sub_limits"]["cataract_per_eye"] == min(si * 25 // 100, 40000)
    assert p["sub_limits"]["modern_treatments"] == si // 2


def test_clause_refs_belong_to_their_policy():
    for pid, p in load_policies().items():
        for ref in p["clause_refs"].values():
            assert ref.startswith(f"{pid}:") or ref.startswith("IRDAI:")


def test_ghc01_has_no_clauses_for_scenario_6():
    assert load_policies()["GHC-01"]["clause_refs"] == {}


# ---------- prior_claims.json ----------

def test_prior_claims_validate_and_are_unique():
    claims = prior_claims()
    assert 30 <= len(claims) <= 50
    assert len({c.claim_id for c in claims}) == len(claims)
    assert len({c.bill_number for c in claims}) == len(claims)
    for c in claims:
        assert c.discharge >= c.admit
        assert c.paid <= c.claimed
        assert (c.paid == 0) == (c.outcome == "rejected")


def test_only_scenario_5_reuses_a_prior_bill_number():
    prior_bills = {c.bill_number for c in prior_claims()}
    reused = {cid for cid in CLAIMS
              if any(b in (project_path("claims") / cid / "claim.txt").read_text(encoding="utf-8") for b in prior_bills)}
    assert reused == {"CLM-0005"}


# ---------- scenario claims ----------

def test_all_seven_scenarios_are_present():
    assert sorted(expected(cid).scenario for cid in CLAIMS) == [1, 2, 3, 4, 5, 6, 7]


@pytest.mark.parametrize("claim_id", CLAIMS)
def test_claim_folder_is_complete(claim_id):
    folder = project_path("claims") / claim_id
    assert (folder / "claim.txt").is_file()
    assert (folder / "expected.json").is_file()
    if expected(claim_id).halt is None:
        assert (folder / "bill.csv").is_file(), f"{claim_id} is missing bill.csv"


@pytest.mark.parametrize("claim_id", CLAIMS)
def test_expected_outcome_is_consistent(claim_id):
    folder = project_path("claims") / claim_id
    exp = expected(claim_id)
    text = (folder / "claim.txt").read_text(encoding="utf-8")
    if exp.halt:
        assert "Total amount claimed" not in text
        return

    items = parse_bill(folder / "bill.csv")
    assert sum(i["amount"] for i in items) == exp.claimed
    assert exp.claimed - sum(d.amount for d in exp.deductions) == exp.payable
    assert f"Rs {inr(exp.claimed)}" in text
    assert exp.payable <= load_policies()[text.split("policy ")[1].split(",")[0]]["sum_insured"]

    margin = load_config()["thresholds"]["overclaim_margin_pct"]
    flag = exp.payable > 0 and (exp.claimed - exp.payable) * 100 > margin * exp.payable
    assert exp.overclaim == flag

    assert {d.clause_id for d in exp.deductions if d.clause_id} == set(exp.clauses)


@pytest.mark.parametrize("claim_id", CLAIMS)
def test_cited_clauses_exist_in_policy_refs(claim_id):
    """Every clause a scenario expects must be one policies.json knows, so retrieval can return it."""
    known = {ref for p in load_policies().values() for ref in p["clause_refs"].values()}
    assert set(expected(claim_id).clauses) <= known


def test_high_value_threshold_matches_scenario_4():
    limit = load_config()["thresholds"]["human_review_amount_inr"]
    by_scenario = {expected(c).scenario: expected(c) for c in CLAIMS}
    assert by_scenario[4].claimed > limit
    assert all(e.claimed <= limit for s, e in by_scenario.items() if s not in (4, 7))
