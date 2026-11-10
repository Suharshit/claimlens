"""Demo website (S4): the page and the JSON routes it uses, end to end on the real scenarios.

Runs in a temporary runtime folder with the LLM off (tests/conftest.py), so nothing is written
into the repo and no API budget is spent.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import api
from tools.config import DISCLAIMER


@pytest.fixture(autouse=True)
def runtime(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAIMLENS_RUNTIME_DIR", str(tmp_path))
    return tmp_path


client = TestClient(api.app)


def test_page_is_served_with_the_disclaimer():
    res = client.get("/")
    assert res.status_code == 200 and res.headers["content-type"].startswith("text/html")
    assert DISCLAIMER in res.text
    assert client.get("/architecture.png").headers["content-type"] == "image/png"


def test_claim_list_has_all_seven_scenarios_not_run_yet():
    body = client.get("/api/claims").json()
    claims = body["claims"]
    assert [c["claim_id"] for c in claims] == [f"CLM-{n:04d}" for n in range(1, 8)]
    assert claims[3]["title"] == "High value → human" and claims[3]["expected"]["verdict"] == "escalate"
    assert all(c["current"] is None for c in claims)
    assert body["disclaimer"] == DISCLAIMER


def test_detail_shows_input_and_expected_before_a_run():
    d = client.get("/api/claims/CLM-0001").json()
    assert "policy ASJ-01" in d["claim_text"]
    assert sum(i["amount"] for i in d["bill"]) == 85000
    assert d["expected"]["payable"] == 79610 and "working" not in d["expected"]
    assert d["record"] is None and d["trace"] == []


def test_missing_bill_is_reported_not_an_error():
    d = client.get("/api/claims/CLM-0007").json()
    assert d["bill"] is None and d["bill_error"] == "no bill attached"


def test_run_then_detail_gives_record_and_only_the_last_runs_trace():
    client.post("/claims/CLM-0002/run")
    client.post("/claims/CLM-0002/run")                       # second run: log keeps both runs
    d = client.get("/api/claims/CLM-0002").json()
    assert d["summary"]["verdict"] == "partial" and d["summary"]["payout"] == 48925
    trace = d["trace"]
    assert trace[0]["tool"] == "reset_state"
    assert sum(1 for e in trace if e["tool"] == "reset_state") == 1
    assert {"intake_agent", "policy_agent", "fraud_agent", "cost_agent", "manager_agent"} <= {e["agent"] for e in trace}
    listed = next(c for c in client.get("/api/claims").json()["claims"] if c["claim_id"] == "CLM-0002")
    assert listed["current"]["verdict"] == "partial"


def test_review_closes_an_escalated_claim_once():
    client.post("/claims/CLM-0004/run")
    body = {"verdict": "approve", "note": "Invoices match; approve as recommended."}
    res = client.post("/api/claims/CLM-0004/review", json=body)
    assert res.status_code == 200
    rec = res.json()
    assert rec["status"] == "closed" and rec["human"]["payout"] == 426550 and rec["disclaimer"] == DISCLAIMER
    again = client.post("/api/claims/CLM-0004/review", json=body)
    assert again.status_code == 409 and "not waiting for a reviewer" in again.json()["detail"]["error"]


def test_review_validates_input():
    client.post("/claims/CLM-0005/run")
    assert client.post("/api/claims/CLM-0005/review", json={"verdict": "maybe", "note": "x"}).status_code == 422
    assert client.post("/api/claims/CLM-0005/review", json={"verdict": "approve", "note": ""}).status_code == 422
    over = client.post("/api/claims/CLM-0005/review", json={"verdict": "partial", "note": "too much", "payout": 10**7})
    assert over.status_code == 409


def test_review_of_a_claim_that_was_never_escalated_is_409():
    client.post("/claims/CLM-0001/run")
    assert client.post("/api/claims/CLM-0001/review", json={"verdict": "approve", "note": "x"}).status_code == 409


@pytest.mark.parametrize("path,code", [
    ("/api/claims/CLM-1", 400), ("/api/claims/CLM-9999", 404), ("/api/claims/..%2Fsecrets", 404),
    ("/api/clauses/not-a-clause", 400), ("/api/clauses/ASJ-01:99.z", 404),
])
def test_bad_ids_are_refused(path, code):
    assert client.get(path).status_code == code


def test_clause_text_is_served_from_the_corpus():
    c = client.get("/api/clauses/ASJ-01:4.1.i").json()
    assert "Room Rent" in c["text"] and c["clause_id"] == "ASJ-01:4.1.i"
    assert "AMBULANCE" in client.get("/api/clauses/IRDAI:List-I").json()["text"].upper()
