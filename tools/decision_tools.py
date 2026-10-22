"""Tools for the Adjudication Manager (M8–M10), the Human Review Desk (M11)
and the Grievance Drafter (S2, should-have)."""

from __future__ import annotations

from typing import Any


# --- Adjudication Manager ----------------------------------------------------

def apply_decision_rules(state: dict[str, Any]) -> dict[str, Any]:
    """Thresholds from config → approve, partial, reject or escalate (+ escalation reason).

    Escalate when: claimed > human_review_amount_inr; fraud score >= fraud_escalate_score;
    no clause above min_similarity; citation guard fails; confidence < min_confidence.
    """
    raise NotImplementedError("M8/M10 — Week 3, Member C")


def verify_citations(clause_ids: list[str], retrieved_ids: list[str]) -> dict[str, Any]:
    """Citation guard (M9): every cited clause id must be in the retrieved set.
    Any miss forces escalation."""
    raise NotImplementedError("M9 — Week 3, Member B")


def write_decision(state: dict[str, Any]) -> dict[str, Any]:
    """Write verdict, payout, clauses and rationale to the ``decision`` section."""
    raise NotImplementedError("M8 — Week 3, Member C")


# --- Human Review Desk (group-of-3 add-on) -----------------------------------

def create_review_ticket(claim_id: str, summary: str) -> dict[str, Any]:
    """Add the claim to ``review_queue.json`` with a one-paragraph summary."""
    raise NotImplementedError("M11 — Week 3, Member C")


def record_human_verdict(claim_id: str, verdict: str, note: str) -> dict[str, Any]:
    """Write the human verdict back into the record and set status to closed."""
    raise NotImplementedError("M11 — Week 3, Member C")


# --- Grievance Drafter (should-have S2 — only after all 7 scenarios pass) ----

def list_contestable(state: dict[str, Any]) -> list[dict[str, Any]]:
    """Pick deductions that look wrong against the cited clauses."""
    raise NotImplementedError("S2 — should-have")


def render_letter(template: str, items: list[dict[str, Any]]) -> str:
    """Fill a Jinja letter template with items, amounts and clauses."""
    raise NotImplementedError("S2 — should-have")
