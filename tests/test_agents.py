"""Tests for the offline claim extractor (M1/M2) and the agents' own logic (query plan, sub-limit choice)."""

from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

import api
from agents import cost_agent, intake_agent, policy_agent
from tools.config import DISCLAIMER, project_path
from tools.intake_tools import IntakeHalt, extract_claim_fields, load_policies
from tools.schemas import ClaimIntake

ASJ = load_policies()["ASJ-01"]


def claim_text(n: int) -> str:
    return (project_path("claims") / f"CLM-{n:04d}" / "claim.txt").read_text(encoding="utf-8")


# ---------- extract_claim_fields (offline path) ----------

@pytest.mark.parametrize("n,fields", [
    (1, {"policy_id": "ASJ-01", "policyholder_id": "PH-1001", "patient": "Ravi Kumar", "admit": "2026-09-02",
         "discharge": "2026-09-05", "claimed": 85000, "bill_number": "SMH/26/04417", "accident": False}),
    (3, {"admit": "2026-07-14", "claimed": 77000, "room_type": "twin-sharing room"}),
    (4, {"claimed": 450000, "discharge": "2026-10-10", "bill_number": "HCC/26/00562"}),
    (5, {"admit": "2026-01-21", "discharge": "2026-01-23", "accident": True, "bill_number": "CGH/25/07731"}),
    (6, {"policy_id": "GHC-01", "room_type": "general ward", "diagnosis": "dengue fever"}),
])
def test_extract_scenario_claims(n, fields):
    out = extract_claim_fields(claim_text(n))
    assert {k: out[k] for k in fields} == fields
    ClaimIntake.model_validate(out)                       # always a valid intake section


def test_extract_keeps_the_procedure_with_the_diagnosis():
    assert "hernia" in extract_claim_fields(claim_text(3))["diagnosis"]
    assert extract_claim_fields(claim_text(1))["diagnosis"] == "acute appendicitis; laparoscopic appendectomy"


def test_missing_amount_halts_scenario_7():
    with pytest.raises(IntakeHalt) as exc:
        extract_claim_fields(claim_text(7))
    assert exc.value.reason == "missing_claimed_amount" and "amount" in str(exc.value)


def test_missing_policy_id_halts():
    with pytest.raises(IntakeHalt) as exc:
        extract_claim_fields("Patient: A. Admitted on 2 September 2026. Total amount claimed: Rs 10,000.")
    assert exc.value.reason == "missing_policy_id"


def test_amount_formats():
    base = "Claim under policy ASJ-01. Admitted on 1 March 2026. Total amount claimed: {}."
    assert extract_claim_fields(base.format("Rs 4,50,000"))["claimed"] == 450000
    assert extract_claim_fields(base.format("₹12500"))["claimed"] == 12500
    assert extract_claim_fields(base.format("Rs. 85,000"))["claimed"] == 85000


# ---------- intake agent halts ----------

def test_unknown_policy_halts(tmp_path, monkeypatch):
    claims = tmp_path / "claims" / "CLM-0099"
    claims.mkdir(parents=True)
    (claims / "claim.txt").write_text("Claim under policy XYZ-99. Admitted on 1 March 2026. "
                                      "Total amount claimed: Rs 10,000.", encoding="utf-8")
    monkeypatch.setenv("CLAIMLENS_RUNTIME_DIR", str(tmp_path / "run"))
    monkeypatch.setattr(intake_agent, "project_path", lambda key: tmp_path / "claims")
    rec = intake_agent.run_sync("CLM-0099")
    assert rec["halt"]["reason"] == "unknown_policy" and rec["intake"] is None


# ---------- policy agent: query plan ----------

def test_query_plan_adds_condition_specific_queries():
    plan = policy_agent.plan_queries({"diagnosis": "right inguinal hernia repair"}, ASJ)
    assert "waiting period hernia" in plan and plan[:6] == policy_agent.STANDARD_QUERIES
    assert "cataract treatment limit" in policy_agent.plan_queries({"diagnosis": "senile cataract, left eye"}, ASJ)
    assert "joint replacement waiting period" in policy_agent.plan_queries({"diagnosis": "total knee replacement"}, ASJ)
    assert policy_agent.plan_queries({"diagnosis": "acute appendicitis"}, ASJ) == policy_agent.STANDARD_QUERIES


# ---------- cost agent: sub-limit choice ----------

@pytest.mark.parametrize("diagnosis,sub", [
    ("senile cataract; phacoemulsification", "cataract_per_eye"),
    ("carcinoma prostate; robotic prostatectomy", "modern_treatments"),
    ("acute appendicitis", None),
])
def test_choose_sub_limit(diagnosis, sub):
    assert cost_agent.choose_sub_limit(diagnosis, ASJ) == sub


def test_cost_agent_waits_for_limits(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAIMLENS_RUNTIME_DIR", str(tmp_path))
    from tools.state import write_state
    write_state("CLM-0001", "intake", extract_claim_fields(claim_text(1)), agent="intake_agent")
    with pytest.raises(RuntimeError, match="limits"):
        cost_agent.run_sync("CLM-0001")


# ---------- the API now runs the real workflow ----------

def test_api_runs_a_claim_end_to_end(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAIMLENS_RUNTIME_DIR", str(tmp_path))
    res = TestClient(api.app).post("/claims/CLM-0001/run")
    assert res.status_code == 200
    body = res.json()
    assert body["decision"]["verdict"] == "approve" and body["decision"]["payout"] == 79610
    assert body["disclaimer"] == DISCLAIMER


def test_workflow_is_importable_without_running():
    import workflow
    assert asyncio.iscoroutinefunction(workflow.run_claim)
