"""Test layer 1: unit tests on deterministic tools with exact rupee assertions.

Targets (03-features-and-scope): room_rent_deduction, compute_payable, score_risk,
plus parse_bill (Week 1). Replace each skip with real tests as the tool lands.
Use hand-worked numbers from data/policies.json — never values computed by the code under test.
"""

import pytest


@pytest.mark.skip(reason="Week 1 — Member A: parse_bill")
def test_parse_bill_reads_line_items():
    ...


@pytest.mark.skip(reason="Week 2 — Member A: room_rent_deduction (exact ₹)")
def test_room_rent_proportionate_deduction():
    ...


@pytest.mark.skip(reason="Week 2 — Member A: compute_payable (exact ₹)")
def test_compute_payable_copay_sublimits_and_cap():
    ...


@pytest.mark.skip(reason="Week 2 — Member C: score_risk")
def test_score_risk_reasons_and_threshold():
    ...
