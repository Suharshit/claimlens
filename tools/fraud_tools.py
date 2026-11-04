"""Tools for the Fraud Signal Agent (M6). Deterministic rules — no LLM scoring.

Weights and windows come from config ``fraud_rules``; policy data (cover start, sum insured,
waiting periods, condition terms) from ``policies.json``; earlier claims from ``prior_claims.json``.
The Fraud agent runs in parallel with Policy Retrieval, so it reads ``policies.json`` itself
rather than waiting for the ``policy`` section.
"""

from __future__ import annotations

import calendar
import json
import re
from datetime import date, timedelta
from functools import lru_cache
from typing import Any

from tools.config import load_config, project_path
from tools.schemas import FraudSection, PriorClaim, WaitingPeriodCheck


# --- prior-claim memory -------------------------------------------------------

@lru_cache(maxsize=1)
def load_prior_claims() -> tuple[dict[str, Any], ...]:
    """Every earlier claim in ``prior_claims.json`` (validated), oldest first."""
    raw = json.loads(project_path("prior_claims").read_text(encoding="utf-8"))
    claims = [PriorClaim.model_validate(c).model_dump(mode="json") for c in raw]
    return tuple(sorted(claims, key=lambda c: c["admit"]))


def lookup_prior_claims(policyholder_id: str) -> list[dict[str, Any]]:
    """Read the prior-claim memory store (config ``paths.prior_claims``) for one policyholder."""
    return [dict(c) for c in load_prior_claims() if c["policyholder_id"] == policyholder_id]


def find_bill_number(bill_number: str) -> list[dict[str, Any]]:
    """Earlier claims (any policyholder) that used this hospital bill number."""
    key = bill_number.strip().upper()
    return [dict(c) for c in load_prior_claims() if c["bill_number"].upper() == key]


# --- waiting periods ----------------------------------------------------------

def add_months(start: date, months: int) -> date:
    """Calendar months later, clamped to the month's last day (31 Jan + 1 month = 28/29 Feb)."""
    y, m = divmod(start.month - 1 + months, 12)
    year, month = start.year + y, m + 1
    return date(year, month, min(start.day, calendar.monthrange(year, month)[1]))


def _mentions(text: str, term: str) -> bool:
    """Whole-word match, plural allowed: 'polyp' matches 'polyps', 'cyst' does not match 'cystitis'."""
    return re.search(rf"\b{re.escape(term.lower())}(s|es)?\b", text.lower()) is not None


def check_waiting_period(
    start: date, admit: date, condition: str, *, limits: dict[str, Any], accident: bool = False,
) -> dict[str, Any]:
    """Flag claims inside the initial or condition-specific waiting period (scenario 3).

    ``start`` is the cover start, ``condition`` the diagnosis / procedure text, ``limits`` the
    policy's ``policies.json`` entry. Accidents skip both the 30-day wait (6.2.i) and the
    specified-condition waits (6.3 a). Pre-existing diseases (6.1) need a declared-PED record,
    which the synthetic data doesn't carry, so they are not checked here.
    Returns a ``WaitingPeriodCheck`` dict.
    """
    start, admit = date.fromisoformat(str(start)), date.fromisoformat(str(admit))
    waits, refs = limits["waiting_periods"], limits.get("clause_refs", {})
    if accident:
        return WaitingPeriodCheck(excluded=False, accident=True).model_dump(mode="json")

    ends = start + timedelta(days=waits["initial_days"])
    if admit < ends:
        return WaitingPeriodCheck(excluded=True, rule="initial", condition="any illness in the first 30 days",
                                  clause_id=refs.get("initial_waiting"), waiting_ends=ends).model_dump(mode="json")

    if any(_mentions(condition, t) for t in limits.get("joint_replacement_terms", [])):
        ends = add_months(start, waits["joint_replacement_months"])
        if admit < ends:
            return WaitingPeriodCheck(excluded=True, rule="joint_replacement",
                                      condition="joint replacement / age-related osteoarthritis or osteoporosis",
                                      clause_id=refs.get("joint_replacement"), waiting_ends=ends).model_dump(mode="json")

    for entry, terms in limits.get("condition_terms", {}).items():
        if any(_mentions(condition, t) for t in terms):
            ends = add_months(start, waits["specific_conditions_months"])
            if admit < ends:
                return WaitingPeriodCheck(excluded=True, rule="specific_conditions", condition=entry,
                                          clause_id=refs.get("specific_conditions"),
                                          waiting_ends=ends).model_dump(mode="json")
    return WaitingPeriodCheck(excluded=False).model_dump(mode="json")


# --- risk score -----------------------------------------------------------------

def score_risk(
    record: dict[str, Any], *, limits: dict[str, Any] | None = None,
    prior_claims: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Weighted rules → {"score": 0–100, "reasons": [...]}.

    Rules: claim soon after inception, amount near sum insured, duplicate bill
    number, stay under 24 h for a non-daycare procedure. Score >= config
    ``thresholds.fraud_escalate_score`` escalates (scenario 5).

    ``record`` is the claim-state record (its ``intake`` section is used). ``limits`` defaults to
    the policy's ``policies.json`` entry, ``prior_claims`` to the whole memory store.
    Returns ``{"score", "reasons", "details"}`` — reasons are ``FraudReason`` codes.
    """
    from tools.intake_tools import load_policies

    cfg = load_config()["fraud_rules"]
    weights = cfg["weights"]
    intake = record["intake"]
    limits = limits or load_policies()[intake["policy_id"]]
    prior = list(load_prior_claims()) if prior_claims is None else prior_claims

    admit = date.fromisoformat(str(intake["admit"]))
    discharge = date.fromisoformat(str(intake["discharge"]))
    start = date.fromisoformat(str(limits["inception_date"]))
    reasons: list[str] = []
    details: list[str] = []

    days_in = (admit - start).days
    if 0 <= days_in < cfg["soon_after_inception_days"]:
        reasons.append("soon_after_inception")
        details.append(f"admitted {days_in} days after cover started ({start.isoformat()})")

    claimed, si = intake["claimed"], limits["sum_insured"]
    if claimed * 100 >= cfg["near_sum_insured_pct"] * si:
        reasons.append("amount_near_sum_insured")
        details.append(f"claimed {claimed} is {claimed * 100 // si}% of the sum insured {si}")

    bill = (intake.get("bill_number") or "").strip().upper()
    if bill:
        hits = [c for c in prior if c["bill_number"].upper() == bill]
        if hits:
            reasons.append("duplicate_bill_number")
            details.append(f"bill number {bill} already used by prior claim {hits[0]['claim_id']}")

    if discharge == admit and "day care" not in intake.get("diagnosis", "").lower():
        reasons.append("short_stay_non_daycare")
        details.append("admitted and discharged the same day for a procedure that is not day care")

    score = min(100, sum(weights[r] for r in reasons))
    return FraudSection(score=score, reasons=reasons, details=details).model_dump(mode="json")
