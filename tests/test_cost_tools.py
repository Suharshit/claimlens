"""Exact-rupee unit tests for the cost tools (M4, M5, S1).

Every expected number is worked by hand (in the comment or in the scenario's expected.json),
never produced by the code under test.
"""

from __future__ import annotations

import copy
import json
from fractions import Fraction

import pytest

from tools.config import project_path
from tools.cost_tools import (
    _round,
    classify_items,
    compute_payable,
    irdai_lists,
    overclaim_flag,
    room_rent_deduction,
)
from tools.intake_tools import load_policies, parse_bill

ASJ = load_policies()["ASJ-01"]          # SI 5,00,000 · room cap 5,000 · ICU cap 10,000 · co-pay 5%


def line(desc, category, qty, amount):
    return {"desc": desc, "category": category, "qty": qty, "amount": amount}


# ---------- classify_items ----------

def test_irdai_lists_are_read_from_the_corpus():
    lists = irdai_lists()
    assert set(lists) == {"IRDAI:List-I", "IRDAI:List-II", "IRDAI:List-III", "IRDAI:List-IV"}
    assert {"gloves", "mask", "laundry charges", "telephone charges"} <= lists["IRDAI:List-I"]
    assert "hot pack" in lists["IRDAI:List-I"]                       # "COLD PACK/HOT PACK" alternative
    assert "admission registration charges" in lists["IRDAI:List-IV"]


@pytest.mark.parametrize("desc,status,clause", [
    ("Gloves", "non_payable", "IRDAI:List-I"),
    ("MASK", "non_payable", "IRDAI:List-I"),
    ("Laundry charges", "non_payable", "IRDAI:List-I"),
    ("Bed pan", "subsumed", "IRDAI:List-II"),
    ("Gauze", "subsumed", "IRDAI:List-III"),
    ("Urine bag", "subsumed", "IRDAI:List-IV"),
    ("Gloves (sterile)", "non_payable", "IRDAI:List-I"),             # bracketed detail ignored
    ("Nursing charges", "payable", None),
    ("Medicines and consumables", "payable", None),                  # no partial-word matches
    ("Food charges", "payable", None),                               # list entry is qualified
    ("Oxygen mask", "non_payable", "IRDAI:List-I"),
])
def test_classify_items(desc, status, clause):
    (item,) = classify_items([line(desc, "misc", 1, 100)])
    assert (item["status"], item["list_clause"]) == (status, clause)


def test_classify_items_does_not_change_its_input():
    items = [line("Gloves", "consumables", 1, 450)]
    before = copy.deepcopy(items)
    classify_items(items)
    assert items == before


# ---------- room_rent_deduction ----------

def cuts(rows):
    return [(c["item"], c["amount"]) for r in rows for c in r["cuts"]]


def test_room_within_cap_cuts_nothing():
    rows = room_rent_deduction(classify_items([
        line("Room", "room", 3, 12000), line("Nursing", "nursing", 3, 3000),   # 5,000/day = cap
        line("Surgeon", "professional", 1, 25000)]), ASJ)
    assert cuts(rows) == []
    assert [r["admissible"] for r in rows] == [12000, 3000, 25000]


def test_room_above_cap_pools_nursing_and_proportions_all_but_medicines():
    # room 7,000 + nursing 1,000 = 8,000/day vs cap 5,000; ratio 5,000/8,000 = 0.625
    rows = room_rent_deduction(classify_items([
        line("Room", "room", 4, 28000), line("Nursing", "nursing", 4, 4000),
        line("Consultant", "professional", 8, 12000), line("Medicines", "pharmacy", 1, 18000),
        line("Lab", "diagnostics", 1, 9600), line("Mesh", "implants", 1, 8000)]), ASJ)
    assert cuts(rows) == [("Room + nursing (4 days)", 12000),     # 32,000 − 4 × 5,000
                          ("Consultant", 4500),                   # 12,000 × 0.375
                          ("Lab", 3600),                          # 9,600 × 0.375
                          ("Mesh", 3000)]                         # 8,000 × 0.375
    assert [r["admissible"] for r in rows] == [16000, 4000, 7500, 18000, 6000, 5000]


def test_icu_above_cap_sets_the_ratio():
    # ICU 15,000/day vs cap 10,000: cut 2 × 5,000 = 10,000; ratio 10,000/15,000 = 2/3
    rows = room_rent_deduction(classify_items([
        line("ICU", "icu", 2, 30000), line("OT", "ot", 1, 9000), line("Drugs", "pharmacy", 1, 5000)]), ASJ)
    assert cuts(rows) == [("ICU charges (2 days)", 10000), ("OT", 3000)]   # 9,000 × 1/3


def test_fractions_are_kept_exact():
    # rate 9,600/day → ratio 5,000/9,600; 10,000 × 4,600/9,600 = 4,791 2/3 (not rounded here)
    rows = room_rent_deduction(classify_items([
        line("Room", "room", 1, 8000), line("Nursing", "nursing", 1, 1600),
        line("Consultant", "professional", 1, 10000)]), ASJ)
    assert rows[2]["cuts"][0]["amount"] == Fraction(14375, 3)


def test_non_payable_lines_are_not_proportioned():
    rows = room_rent_deduction(classify_items([
        line("Room", "room", 1, 10000), line("Gloves", "consumables", 1, 400)]), ASJ)
    assert cuts(rows) == [("Room charges (1 days)", 5000)]
    assert rows[1]["admissible"] == 0


# ---------- compute_payable: the hand-worked scenarios ----------

SCENARIOS = {"CLM-0001": "ASJ-01", "CLM-0002": "ASJ-01", "CLM-0004": "ASJ-01",
             "CLM-0005": "ASJ-01", "CLM-0006": "GHC-01"}


@pytest.mark.parametrize("claim_id,policy_id", SCENARIOS.items())
def test_compute_payable_matches_the_hand_worked_scenario(claim_id, policy_id):
    folder = project_path("claims") / claim_id
    expected = json.loads((folder / "expected.json").read_text(encoding="utf-8"))
    cost = compute_payable(parse_bill(folder / "bill.csv"), load_policies()[policy_id])
    assert cost == {"deductions": expected["deductions"], "payable": expected["payable"],
                    "overclaim": expected["overclaim"]}


def test_scenario_3_cost_ignores_the_waiting_period():
    # Bill 77,000, room + nursing 5,000/day = cap, nothing non-payable; co-pay 5% = 3,850.
    # The rejection (6.3.i) is the Manager's call, not a cost deduction.
    folder = project_path("claims") / "CLM-0003"
    cost = compute_payable(parse_bill(folder / "bill.csv"), ASJ)
    assert cost["payable"] == 73150
    assert [d["item"] for d in cost["deductions"]] == ["Co-payment 5%"]


# ---------- compute_payable: rules ----------

def test_rounding_is_half_up_and_only_in_compute_payable():
    assert [_round(Fraction(x, 2)) for x in (1, 3, 5)] == [1, 2, 3]
    # 10,000 × 4,600/9,600 = 4,791.67 → 4,792; room cut 9,600 − 5,000 = 4,600
    # admissible = 19,600 − 4,600 − 4,792 = 10,208; co-pay 5% = 510.4 → 510; payable 9,698
    cost = compute_payable([line("Room", "room", 1, 8000), line("Nursing", "nursing", 1, 1600),
                            line("Consultant", "professional", 1, 10000)], ASJ)
    assert [d["amount"] for d in cost["deductions"]] == [4600, 4792, 510]
    assert cost["payable"] == 9698
    assert all(isinstance(d["amount"], int) for d in cost["deductions"])


def test_sub_limit_applies_before_co_pay():
    # cataract bill 60,000 → sub-limit 40,000 (cut 20,000) → co-pay 2,000 → 38,000
    cost = compute_payable([line("Cataract surgery package", "professional", 1, 60000)], ASJ,
                           sub_limit="cataract_per_eye")
    assert [(d["amount"], d["clause_id"]) for d in cost["deductions"]] == [(20000, "ASJ-01:4.3"), (2000, "ASJ-01:9.3")]
    assert cost["payable"] == 38000


def test_sum_insured_caps_the_payout():
    small = {**ASJ, "sum_insured": 100000, "room_cap_per_day": 2000, "icu_cap_per_day": 5000}
    # 2,00,000 surgery, co-pay 10,000 → 1,90,000 → capped at SI 1,00,000 (cut 90,000)
    cost = compute_payable([line("Surgery", "professional", 1, 200000)], small)
    assert [d["amount"] for d in cost["deductions"]] == [10000, 90000]
    assert cost["payable"] == 100000


def test_deduction_table_always_adds_up():
    items = parse_bill(project_path("claims") / "CLM-0002" / "bill.csv")
    cost = compute_payable(items, ASJ)
    assert sum(i["amount"] for i in items) - sum(d["amount"] for d in cost["deductions"]) == cost["payable"]


def test_compute_payable_does_not_change_its_input():
    items = parse_bill(project_path("claims") / "CLM-0002" / "bill.csv")
    before = copy.deepcopy(items)
    compute_payable(items, ASJ)
    assert items == before


# ---------- M5: over-claiming flag ----------

@pytest.mark.parametrize("claimed,payable,flag", [
    (85000, 79610, False),     # 6.8 %
    (72000, 48925, True),      # 47.2 %
    (110000, 100000, False),   # exactly 10 % is not over
    (110001, 100000, True),
    (77000, 0, False),         # a rejection isn't over-claiming
])
def test_overclaim_flag(claimed, payable, flag):
    assert overclaim_flag(claimed, payable, 10) is flag


def test_margin_comes_from_config_unless_given():
    items = parse_bill(project_path("claims") / "CLM-0001" / "bill.csv")    # 6.8 % over
    assert compute_payable(items, ASJ)["overclaim"] is False
    assert compute_payable(items, ASJ, margin_pct=5)["overclaim"] is True
