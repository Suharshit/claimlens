"""Tools for the Fraud Signal Agent (M6). Deterministic rules — no LLM scoring."""

from __future__ import annotations

from datetime import date
from typing import Any


def lookup_prior_claims(policyholder_id: str) -> list[dict[str, Any]]:
    """Read the prior-claim memory store (config ``paths.prior_claims``)."""
    raise NotImplementedError("M6 — Week 2, Member C")


def check_waiting_period(start: date, admit: date, condition: str) -> dict[str, Any]:
    """Flag claims inside the initial or condition-specific waiting period (scenario 3)."""
    raise NotImplementedError("M6 — Week 2, Member C")


def score_risk(record: dict[str, Any]) -> dict[str, Any]:
    """Weighted rules → {"score": 0–100, "reasons": [...]}.

    Rules: claim soon after inception, amount near sum insured, duplicate bill
    number, stay under 24 h for a non-daycare procedure. Score >= config
    ``thresholds.fraud_escalate_score`` escalates (scenario 5).
    """
    raise NotImplementedError("M6 — Week 2, Member C")
