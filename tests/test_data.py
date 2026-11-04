"""Checks on the hand-typed data files: policies.json and the scenario claims.

These test the data, not the code: each expected.json must be internally consistent
(its own working adds up), so later code is checked against numbers a person worked out.
"""

from __future__ import annotations

import json

import pytest

from tools.config import load_config, project_path
from tools.intake_tools import load_policies, parse_bill
from tools.schemas import ExpectedOutcome

CLAIMS = sorted(p.name for p in project_path("claims").iterdir() if p.is_dir())


def test_policies_json_validates():
    policies = load_policies()
    assert "ASJ-01" in policies


def test_asj01_caps_follow_the_standard_formula():
    p = load_policies()["ASJ-01"]
    si = p["sum_insured"]
    assert p["room_cap_per_day"] == min(si * 2 // 100, 5000)      # 2% of SI, max ₹5,000
    assert p["icu_cap_per_day"] == min(si * 5 // 100, 10000)      # 5% of SI, max ₹10,000
    assert p["sub_limits"]["cataract_per_eye"] == min(si * 25 // 100, 40000)


def test_clause_refs_belong_to_their_policy():
    for pid, p in load_policies().items():
        for ref in p["clause_refs"].values():
            assert ref.startswith(f"{pid}:") or ref.startswith("IRDAI:")


def test_there_are_scenario_claims():
    assert {"CLM-0001", "CLM-0002"} <= set(CLAIMS)


@pytest.mark.parametrize("claim_id", CLAIMS)
def test_claim_folder_is_complete(claim_id):
    folder = project_path("claims") / claim_id
    for name in ("claim.txt", "bill.csv", "expected.json"):
        assert (folder / name).is_file(), f"{claim_id} is missing {name}"


@pytest.mark.parametrize("claim_id", CLAIMS)
def test_expected_outcome_is_consistent(claim_id):
    folder = project_path("claims") / claim_id
    expected = ExpectedOutcome.model_validate(json.loads((folder / "expected.json").read_text(encoding="utf-8")))
    items = parse_bill(folder / "bill.csv")

    assert sum(i["amount"] for i in items) == expected.claimed
    assert expected.claimed - sum(d.amount for d in expected.deductions) == expected.payable
    assert f"Rs {expected.claimed:,}" in (folder / "claim.txt").read_text(encoding="utf-8")
    margin = load_config()["thresholds"]["overclaim_margin_pct"]
    assert expected.overclaim == ((expected.claimed - expected.payable) * 100 > margin * expected.payable)
    for d in expected.deductions:
        assert d.clause_id in expected.clauses
