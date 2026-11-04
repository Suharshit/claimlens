"""Unit tests for the Fraud Signal tools (M6). Scores worked by hand from config fraud_rules:
soon_after_inception 35 · amount_near_sum_insured 25 · duplicate_bill_number 40 · short_stay 20.
"""

from __future__ import annotations

from datetime import date

import pytest

from tools.config import load_config
from tools.fraud_tools import (
    add_months,
    check_waiting_period,
    find_bill_number,
    lookup_prior_claims,
    score_risk,
)
from tools.intake_tools import load_policies

ASJ = load_policies()["ASJ-01"]          # cover starts 2026-01-01, SI 5,00,000
START = date(2026, 1, 1)


def intake(**kw):
    base = {"policy_id": "ASJ-01", "policyholder_id": "PH-9999", "patient": "Test", "admit": "2026-09-02",
            "discharge": "2026-09-05", "diagnosis": "acute appendicitis", "room_type": "twin",
            "claimed": 85000, "bill_number": "ZZZ/26/00001", "accident": False}
    return {"intake": {**base, **kw}}


# ---------- prior-claim memory ----------

def test_lookup_prior_claims_filters_by_policyholder():
    claims = lookup_prior_claims("PH-2017")
    assert [c["claim_id"] for c in claims] == ["PC-0017"]
    assert claims[0]["bill_number"] == "CGH/25/07731"
    assert lookup_prior_claims("PH-0000") == []


def test_find_bill_number_is_case_insensitive():
    assert [c["claim_id"] for c in find_bill_number("cgh/25/07731")] == ["PC-0017"]
    assert find_bill_number("SMH/26/04417") == []


def test_lookup_returns_copies():
    lookup_prior_claims("PH-2017")[0]["paid"] = 0
    assert lookup_prior_claims("PH-2017")[0]["paid"] == 80370


# ---------- waiting periods ----------

@pytest.mark.parametrize("start,months,ends", [
    (date(2026, 1, 1), 24, date(2028, 1, 1)),
    (date(2026, 1, 31), 1, date(2026, 2, 28)),
    (date(2027, 12, 31), 2, date(2028, 2, 29)),   # leap year
])
def test_add_months(start, months, ends):
    assert add_months(start, months) == ends


def test_scenario_3_hernia_is_inside_the_24_month_wait():
    check = check_waiting_period(START, date(2026, 7, 14), "right inguinal hernia, laparoscopic repair", limits=ASJ)
    assert check == {"excluded": True, "rule": "specific_conditions", "condition": "hernia of all types",
                     "clause_id": "ASJ-01:6.3.i", "waiting_ends": "2028-01-01", "accident": False}


def test_hernia_after_24_months_is_covered():
    assert check_waiting_period(START, date(2028, 1, 1), "inguinal hernia", limits=ASJ)["excluded"] is False


def test_first_30_days_exclude_illness():
    check = check_waiting_period(START, date(2026, 1, 21), "dengue fever", limits=ASJ)
    assert (check["rule"], check["clause_id"], check["waiting_ends"]) == ("initial", "ASJ-01:6.2.i", "2026-01-31")
    assert check_waiting_period(START, date(2026, 1, 31), "dengue fever", limits=ASJ)["excluded"] is False


def test_scenario_5_accident_skips_the_waits():
    check = check_waiting_period(START, date(2026, 1, 21), "fracture of right distal radius", limits=ASJ, accident=True)
    assert check["excluded"] is False and check["accident"] is True


def test_joint_replacement_waits_48_months():
    check = check_waiting_period(START, date(2029, 6, 1), "total knee replacement", limits=ASJ)
    assert (check["rule"], check["clause_id"], check["waiting_ends"]) == ("joint_replacement", "ASJ-01:6.3.ii", "2030-01-01")


@pytest.mark.parametrize("diagnosis", ["acute appendicitis", "acute pancreatitis", "dengue fever",
                                       "acute cystitis", "acute coronary syndrome, PTCA"])
def test_unlisted_conditions_are_not_excluded(diagnosis):
    # "cystitis" must not match the "cyst" term; pancreatitis is not a listed condition
    assert check_waiting_period(START, date(2026, 9, 2), diagnosis, limits=ASJ)["excluded"] is False


def test_policy_without_condition_list_only_has_the_initial_wait():
    ghc = load_policies()["GHC-01"]
    assert check_waiting_period(START, date(2026, 8, 18), "hernia", limits=ghc)["excluded"] is False


# ---------- score_risk ----------

def test_clean_claim_scores_zero():
    assert score_risk(intake()) == {"score": 0, "reasons": [], "details": [], "waiting_period": None}


def test_scenario_5_two_rules_cross_the_threshold():
    # admitted day 20 (35) + bill reused from PC-0017 (40) = 75 >= 60
    result = score_risk(intake(admit="2026-01-21", discharge="2026-01-23", claimed=99300, bill_number="CGH/25/07731"))
    assert result["score"] == 75
    assert result["reasons"] == ["soon_after_inception", "duplicate_bill_number"]
    assert result["score"] >= load_config()["thresholds"]["fraud_escalate_score"]
    assert "PC-0017" in result["details"][1]


def test_scenario_4_near_sum_insured_alone_stays_below_threshold():
    # 4,50,000 is 90% of 5,00,000 (>= 80%) → 25 only
    result = score_risk(intake(admit="2026-10-05", discharge="2026-10-10", claimed=450000))
    assert (result["score"], result["reasons"]) == (25, ["amount_near_sum_insured"])


def test_same_day_discharge_flags_short_stay_unless_day_care():
    assert score_risk(intake(discharge="2026-09-02"))["reasons"] == ["short_stay_non_daycare"]
    assert score_risk(intake(discharge="2026-09-02", diagnosis="cataract (day care)"))["reasons"] == []


def test_score_is_capped_at_100():
    result = score_risk(intake(admit="2026-01-10", discharge="2026-01-10", claimed=490000, bill_number="CGH/25/07731"))
    assert result["reasons"] == ["soon_after_inception", "amount_near_sum_insured",
                                 "duplicate_bill_number", "short_stay_non_daycare"]
    assert result["score"] == 100                       # 35 + 25 + 40 + 20 = 120 → 100


def test_admission_before_cover_start_is_not_soon_after_inception():
    assert score_risk(intake(admit="2025-12-20", discharge="2025-12-22"))["reasons"] == []
