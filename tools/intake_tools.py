"""Tools for the Intake Agent (M1, M2)."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def extract_claim_fields(text: str) -> dict[str, Any]:
    """LLM call with a Pydantic schema → patient, admit/discharge dates, diagnosis,
    room type, claimed amount, policy id. Temperature 0.

    M2: if policy id or claimed amount is missing, halt with a clear message
    rather than guessing (scenario 7).
    """
    raise NotImplementedError("M1/M2 — Week 2 (needs framework + model lane)")


def parse_bill(path: str | Path) -> list[dict[str, Any]]:
    """Read a bill CSV/JSON into line items: desc, category, qty, amount (int ₹)."""
    raise NotImplementedError("M1 — Week 1, Member A")


def validate_policy(policy_id: str) -> dict[str, Any]:
    """Confirm the policy exists in ``policies.json``; halt with a clear error if not."""
    raise NotImplementedError("M1/M2 — Member A")
