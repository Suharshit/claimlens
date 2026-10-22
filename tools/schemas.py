"""Pydantic v2 models for the shared claim-state record.

Week 1 · Member A (supports M1, M12). Fields come from the claim-state example
in context/02-architecture-brief.md. Conventions (04-ui-and-stack-brief):
- every money value is an ``int`` in rupees;
- clause ids follow ``<POLICY_ID>:<section>`` or ``IRDAI:<list>``.

TODO (Week 1): add the fields to each model below, then make
``ClaimState`` the single type that ``read_state`` / ``write_state`` validate.
"""

from __future__ import annotations

from pydantic import BaseModel


class ClaimIntake(BaseModel):
    """``intake`` section: policy_id, patient, admit, discharge, diagnosis,
    room_type, claimed (int ₹). Written by the Intake Agent."""
    # TODO(M1)


class BillItem(BaseModel):
    """One ``bill_items`` row: desc, category, qty, amount (int ₹)."""
    # TODO(M1)


class PolicyLimits(BaseModel):
    """Structured limits from ``policies.json``: sum_insured, room_cap_per_day,
    ICU cap, copay_pct, sub-limits, waiting periods."""
    # TODO(M3/M4)


class Clause(BaseModel):
    """A retrieved clause: clause_id, text, score."""
    # TODO(M3)


class PolicySection(BaseModel):
    """``policy`` section: limits + retrieved clauses. Written by the Policy Retrieval Agent."""
    # TODO(M3)


class FraudSection(BaseModel):
    """``fraud`` section: score (0–100) and reasons. Written by the Fraud Signal Agent."""
    # TODO(M6)


class Deduction(BaseModel):
    """One deduction row: item, amount (int ₹), reason, clause_id."""
    # TODO(M4/S1)


class CostSection(BaseModel):
    """``cost`` section: deductions + payable (int ₹) + over-claim flag. Written by the Cost Assessment Agent."""
    # TODO(M4/M5)


class DecisionSection(BaseModel):
    """``decision`` section: verdict (approve | partial | reject | escalate),
    payout, clauses, rationale, confidence. Written by the Adjudication Manager."""
    # TODO(M8)


class HumanSection(BaseModel):
    """``human`` section: ticket, reviewer, verdict, note. Written by the Human Review Desk."""
    # TODO(M11)


class ClaimState(BaseModel):
    """The whole ``state/<claim_id>.json`` record: claim_id, status
    (intake | assessing | decided | escalated | closed), one section per agent, trace."""
    # TODO(M12)
