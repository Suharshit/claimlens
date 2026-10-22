"""Test layers 2 and 3: full-workflow scenario tests and the run-log test.

All seven scenarios from 03-features-and-scope. For each: assert verdict, payout
and that every cited clause id exists in the retrieved set. Set expected payouts
from the limits typed into data/policies.json.
"""

import pytest

SCENARIOS = [
    (1, "Clean approval", "approve"),
    (2, "Partial: room-rent breach", "partial"),
    (3, "Reject: waiting period", "reject"),
    (4, "High value → human", "escalate"),       # then human closes it
    (5, "Fraud signal", "escalate"),             # risk >= 60, both reasons
    (6, "Honest failure: no grounding", "escalate"),
    (7, "Missing data", "halt"),                 # intake halts, nothing downstream
]


@pytest.mark.skip(reason="Week 3 — needs the full workflow")
@pytest.mark.parametrize("number,title,expected_verdict", SCENARIOS)
def test_scenario(number, title, expected_verdict):
    ...


@pytest.mark.skip(reason="Week 3 — run log only grows and every agent appears in each trace")
def test_run_log_is_append_only():
    ...
