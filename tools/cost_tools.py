"""Tools for the Cost Assessment Agent (M4, M5, S1).

ALL rupee maths lives here, never in the LLM. Every money value is an ``int``
in rupees; rounding happens only inside ``compute_payable``. Each function gets
exact-rupee unit tests in tests/test_tools.py.
"""

from __future__ import annotations

from typing import Any


def classify_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Mark each bill line payable, non-payable or subsumed using the IRDAI lists."""
    raise NotImplementedError("M4 — Week 2, Member A")


def room_rent_deduction(items: list[dict[str, Any]], limits: dict[str, Any]) -> list[dict[str, Any]]:
    """Apply proportionate deduction when the room exceeds the daily cap (scenario 2)."""
    raise NotImplementedError("M4 — Week 2, Member A")


def compute_payable(items: list[dict[str, Any]], limits: dict[str, Any]) -> dict[str, Any]:
    """Apply sub-limits, co-pay and sum-insured cap.

    Returns {"payable": int, "deductions": [{item, amount, reason, clause_id}, ...]}.
    """
    raise NotImplementedError("M4 — Week 2, Member A")
