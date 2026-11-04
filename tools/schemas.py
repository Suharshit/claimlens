"""Pydantic v2 models for the shared claim-state record and the data files.

Week 1 · M1, M12. Fields follow the claim-state example in
context/02-architecture-brief.md. Conventions (04-ui-and-stack-brief):
- every money value is a strict ``int`` in rupees (floats and bools are rejected);
- clause ids follow ``<POLICY_ID>:<section>`` or ``IRDAI:<list>``.

``tools.state.write_state`` validates each section against ``SECTION_MODELS``
and the whole record against ``ClaimState`` before saving.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator

# ---- shared field types ----

Rupees = Annotated[int, Field(strict=True, ge=0)]
"""Whole rupees, never negative, never a float."""

PolicyId = Annotated[str, Field(pattern=r"^[A-Z][A-Z0-9]*-\d{2}$")]
"""e.g. ``ASJ-01``."""

ClaimId = Annotated[str, Field(pattern=r"^CLM-\d{4}$")]

ClauseId = Annotated[str, Field(pattern=r"^([A-Z][A-Z0-9]*-\d{2}|IRDAI):[A-Za-z0-9][A-Za-z0-9.\-]*$")]
"""``ASJ-01:5.a.i`` or ``IRDAI:List-I``."""

BillCategory = Literal[
    "room", "icu", "nursing", "professional", "ot",
    "pharmacy", "diagnostics", "consumables", "implants", "misc",
]
"""Bill line categories. pharmacy / diagnostics / consumables / implants are not
subject to proportionate room-rent deduction (IRDAI); see context/05-progress.md."""

Verdict = Literal["approve", "partial", "reject", "escalate"]
Status = Literal["intake", "assessing", "decided", "escalated", "closed"]


class _Model(BaseModel):
    """Base: unknown fields are errors, so a typo in a data file fails loudly."""
    model_config = ConfigDict(extra="forbid")


# ---- intake ----

class ClaimIntake(_Model):
    """``intake`` section. Written by the Intake Agent."""
    policy_id: PolicyId
    policyholder_id: str | None = None   # Fraud Signal: lookup_prior_claims (scenario 5)
    patient: str = Field(min_length=1)
    admit: date
    discharge: date
    diagnosis: str = Field(min_length=1)
    room_type: str = Field(min_length=1)
    claimed: Rupees
    bill_number: str | None = None       # Fraud Signal: duplicate bill check (scenario 5)

    @model_validator(mode="after")
    def _discharge_not_before_admit(self) -> ClaimIntake:
        if self.discharge < self.admit:
            raise ValueError("discharge date is before admit date")
        return self


class BillItem(_Model):
    """One ``bill_items`` row. ``amount`` is the line total; for room/ICU/nursing ``qty`` is days."""
    desc: str = Field(min_length=1)
    category: BillCategory
    qty: Annotated[int, Field(strict=True, ge=1)]
    amount: Rupees


# ---- policy ----

class WaitingPeriods(_Model):
    initial_days: Annotated[int, Field(ge=0)]
    specific_conditions_months: Annotated[int, Field(ge=0)]
    pre_existing_months: Annotated[int, Field(ge=0)]
    joint_replacement_months: Annotated[int, Field(ge=0)] = 0


class PolicyLimits(_Model):
    """One ``policies.json`` entry: hand-typed from the wording; ground truth for all money maths."""
    policy_id: PolicyId
    name: str
    source: str                          # which wording + version the numbers came from
    inception_date: date
    sum_insured: Rupees
    room_cap_per_day: Rupees
    icu_cap_per_day: Rupees
    copay_pct: Annotated[int, Field(ge=0, le=100)]
    sub_limits: dict[str, Rupees] = Field(default_factory=dict)
    waiting_periods: WaitingPeriods
    specific_conditions: list[str] = Field(default_factory=list)
    pre_hospitalisation_days: Annotated[int, Field(ge=0)] = 0
    post_hospitalisation_days: Annotated[int, Field(ge=0)] = 0
    clause_refs: dict[str, ClauseId] = Field(default_factory=dict)


class Clause(_Model):
    """A retrieved clause."""
    clause_id: ClauseId
    text: str
    score: Annotated[float, Field(ge=0)]


class PolicySection(_Model):
    """``policy`` section. Written by the Policy Retrieval Agent."""
    limits: PolicyLimits | None = None
    clauses: list[Clause] = Field(default_factory=list)


# ---- fraud ----

class FraudSection(_Model):
    """``fraud`` section. Written by the Fraud Signal Agent."""
    score: Annotated[int, Field(strict=True, ge=0, le=100)]
    reasons: list[str] = Field(default_factory=list)


# ---- cost ----

class Deduction(_Model):
    """One deduction-table row (S1)."""
    item: str
    amount: Rupees
    reason: str
    clause_id: ClauseId | None = None


class CostSection(_Model):
    """``cost`` section. Written by the Cost Assessment Agent."""
    deductions: list[Deduction] = Field(default_factory=list)
    payable: Rupees
    overclaim: bool = False


# ---- decision / human / letters ----

class DecisionSection(_Model):
    """``decision`` section. Written by the Adjudication Manager."""
    verdict: Verdict
    payout: Rupees
    clauses: list[ClauseId] = Field(default_factory=list)
    rationale: str
    confidence: Annotated[float, Field(ge=0, le=1)]


class HumanSection(_Model):
    """``human`` section. Written by the Human Review Desk."""
    ticket: str | None = None
    reviewer: str | None = None
    verdict: Verdict | None = None
    note: str | None = None


class Letter(_Model):
    """One ``letters`` entry (S2). Written by the Grievance Drafter."""
    kind: Literal["query_reply", "grievance"]
    body: str
    clauses: list[ClauseId] = Field(default_factory=list)


# ---- whole record ----

class ClaimState(_Model):
    """The whole ``state/<claim_id>.json`` record."""
    claim_id: ClaimId
    status: Status
    intake: ClaimIntake | None = None
    bill_items: list[BillItem] = Field(default_factory=list)
    policy: PolicySection | None = None
    fraud: FraudSection | None = None
    cost: CostSection | None = None
    decision: DecisionSection | None = None
    human: HumanSection = Field(default_factory=HumanSection)
    letters: list[Letter] | None = None
    trace: list[dict[str, Any]] = Field(default_factory=list)


# Validator per writable section (keys match tools.state.SECTIONS).
SECTION_MODELS: dict[str, TypeAdapter[Any]] = {
    "intake": TypeAdapter(ClaimIntake),
    "bill_items": TypeAdapter(list[BillItem]),
    "policy": TypeAdapter(PolicySection),
    "fraud": TypeAdapter(FraudSection),
    "cost": TypeAdapter(CostSection),
    "decision": TypeAdapter(DecisionSection),
    "human": TypeAdapter(HumanSection),
    "letters": TypeAdapter(list[Letter]),
}


# ---- scenario test data (data/claims/<id>/expected.json) ----

class ExpectedOutcome(_Model):
    """Hand-worked expected result for one scenario claim."""
    scenario: Annotated[int, Field(ge=1, le=7)]
    verdict: Verdict
    claimed: Rupees
    payable: Rupees
    overclaim: bool
    clauses: list[ClauseId]
    deductions: list[Deduction]
    working: list[str]                   # the hand calculation, line by line
