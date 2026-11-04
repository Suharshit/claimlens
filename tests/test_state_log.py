"""Unit tests for the shared claim-state record (M12) and the append-only run log (M13).

Every test runs against a temporary state dir and log file, never the real ones.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest
from pydantic import BaseModel

import tools.logger as logger
import tools.state as state


@pytest.fixture()
def tmp_paths(tmp_path, monkeypatch):
    paths = {"state_dir": tmp_path / "state", "run_log": tmp_path / "logs" / "run_log.jsonl"}

    def fake_project_path(key: str) -> Path:
        return paths[key]

    monkeypatch.setattr(state, "project_path", fake_project_path)
    monkeypatch.setattr(logger, "project_path", fake_project_path)
    return paths


def log_lines(paths) -> list[str]:
    return paths["run_log"].read_text(encoding="utf-8").splitlines()


# ---------- M13: run log ----------

def test_append_log_adds_utc_timestamp(tmp_paths):
    logger.append_log({"claim_id": "CLM-0001", "agent": "intake_agent", "tool": "parse_bill", "summary": "3 items"})
    (event,) = logger.read_log()
    assert event["ts"].endswith("Z")
    assert event["agent"] == "intake_agent"


def test_append_log_keeps_given_timestamp(tmp_paths):
    logger.append_log({"ts": "2026-11-04T00:00:00.000Z", "summary": "x"})
    assert logger.read_log()[0]["ts"] == "2026-11-04T00:00:00.000Z"


def test_log_only_grows(tmp_paths):
    logger.append_log({"claim_id": "CLM-0001", "summary": "first"})
    before = log_lines(tmp_paths)
    logger.append_log({"claim_id": "CLM-0002", "summary": "second"})
    after = log_lines(tmp_paths)
    assert len(after) == len(before) + 1
    assert after[: len(before)] == before  # earlier lines untouched


def test_log_is_one_json_object_per_line_with_rupee_symbol(tmp_paths):
    logger.append_log({"summary": "payable ₹1,51,230"})
    (line,) = log_lines(tmp_paths)
    assert json.loads(line)["summary"] == "payable ₹1,51,230"


@pytest.mark.parametrize("bad", ["text", ["list"], None])
def test_append_log_rejects_non_dict(tmp_paths, bad):
    with pytest.raises(TypeError):
        logger.append_log(bad)


def test_append_log_rejects_unserialisable_and_writes_nothing(tmp_paths):
    with pytest.raises(TypeError):
        logger.append_log({"summary": object()})
    assert logger.read_log() == []


def test_read_log_filters_by_claim(tmp_paths):
    logger.append_log({"claim_id": "CLM-0001", "summary": "a"})
    logger.append_log({"claim_id": "CLM-0002", "summary": "b"})
    assert [e["summary"] for e in logger.read_log("CLM-0002")] == ["b"]


# ---------- M12: shared claim-state record ----------

INTAKE = {"policy_id": "ASJ-01", "patient": "Test Patient", "admit": "2026-09-02",
          "discharge": "2026-09-05", "diagnosis": "appendicitis", "room_type": "single", "claimed": 85000}
# Optional intake fields are filled with None once validated.
INTAKE_STORED = {**INTAKE, "policyholder_id": None, "bill_number": None, "accident": False}


def test_first_write_creates_record_in_brief_shape(tmp_paths):
    record = state.write_state("CLM-0001", "intake", INTAKE, agent="intake_agent")
    assert record["claim_id"] == "CLM-0001"
    assert record["status"] == "intake"
    assert record["intake"] == INTAKE_STORED
    assert record["bill_items"] == []
    assert record["human"] == {"ticket": None, "reviewer": None, "verdict": None, "note": None, "payout": None}
    assert set(state.SECTIONS) <= set(record)
    assert state.read_state("CLM-0001") == record


def test_write_touches_only_its_own_section(tmp_paths):
    state.write_state("CLM-0001", "intake", INTAKE)
    state.write_state("CLM-0001", "fraud", {"score": 22, "reasons": ["soon_after_inception"]})
    record = state.read_state("CLM-0001")
    assert record["intake"] == INTAKE_STORED
    assert record["fraud"]["score"] == 22
    assert record["policy"] is None


def test_unknown_section_is_rejected(tmp_paths):
    with pytest.raises(ValueError, match="unknown section"):
        state.write_state("CLM-0001", "status", "closed")
    assert not state.state_path("CLM-0001").exists()


def test_agent_cannot_write_another_agents_section(tmp_paths):
    with pytest.raises(PermissionError):
        state.write_state("CLM-0001", "decision", {"verdict": "approve"}, agent="fraud_agent")


def test_every_write_is_logged_and_traced(tmp_paths):
    state.write_state("CLM-0001", "intake", INTAKE)
    state.write_state("CLM-0001", "bill_items", [{"desc": "Room", "category": "room", "qty": 3, "amount": 15000}])
    events = logger.read_log("CLM-0001")
    assert [(e["agent"], e["section"]) for e in events] == [
        ("intake_agent", "intake"), ("intake_agent", "bill_items")]
    trace = state.read_state("CLM-0001")["trace"]
    assert [t["section"] for t in trace] == ["intake", "bill_items"]
    assert [t["ts"] for t in trace] == [e["ts"] for e in events]


def test_read_missing_record_raises(tmp_paths):
    with pytest.raises(FileNotFoundError):
        state.read_state("CLM-0404")


@pytest.mark.parametrize("bad_id", ["../etc", "CLM-1", "clm-0001", "CLM-0001.json", ""])
def test_malformed_claim_id_rejected(tmp_paths, bad_id):
    with pytest.raises(ValueError):
        state.write_state(bad_id, "intake", INTAKE)


def test_unserialisable_data_leaves_record_unchanged(tmp_paths):
    state.write_state("CLM-0001", "intake", INTAKE)
    before = state.read_state("CLM-0001")
    with pytest.raises(ValueError):
        state.write_state("CLM-0001", "fraud", {"score": object()})
    with pytest.raises(ValueError):
        state.write_state("CLM-0001", "fraud", {"score": 150, "reasons": []})
    assert state.read_state("CLM-0001") == before
    assert len(logger.read_log("CLM-0001")) == 1


def test_pydantic_models_are_accepted(tmp_paths):
    class Fraud(BaseModel):
        score: int
        reasons: list[str]

    state.write_state("CLM-0001", "fraud", Fraud(score=65, reasons=["duplicate_bill_number"]))
    assert state.read_state("CLM-0001")["fraud"] == {
        "score": 65, "reasons": ["duplicate_bill_number"], "details": [], "waiting_period": None}


def test_caller_mutation_does_not_leak_into_record(tmp_paths):
    data = {"score": 10, "reasons": []}
    state.write_state("CLM-0001", "fraud", data)
    data["reasons"].append("short_stay_non_daycare")
    assert state.read_state("CLM-0001")["fraud"]["reasons"] == []


def test_set_status_moves_and_logs(tmp_paths):
    state.write_state("CLM-0001", "intake", INTAKE)
    record = state.set_status("CLM-0001", "assessing", agent="workflow")
    assert record["status"] == "assessing"
    assert record["trace"][-1] == {**record["trace"][-1], "action": "status", "from": "intake", "to": "assessing"}
    assert logger.read_log("CLM-0001")[-1]["summary"] == "status intake -> assessing"
    with pytest.raises(ValueError):
        state.set_status("CLM-0001", "done", agent="workflow")


def test_parallel_policy_and_fraud_writes_both_survive(tmp_paths):
    """Fan-out: Policy and Fraud write at the same time; neither update may be lost."""
    state.write_state("CLM-0001", "intake", INTAKE)
    errors: list[BaseException] = []

    def writer(section: str, agent: str) -> None:
        try:
            for i in range(25):
                data = ({"clauses": [{"clause_id": "ASJ-01:4.1.i", "text": "room rent", "score": i / 100}]}
                        if section == "policy" else {"score": i, "reasons": []})
                state.write_state("CLM-0001", section, data, agent=agent)
        except BaseException as exc:  # pragma: no cover - surfaced below
            errors.append(exc)

    threads = [threading.Thread(target=writer, args=("policy", "policy_agent")),
               threading.Thread(target=writer, args=("fraud", "fraud_agent"))]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []
    record = state.read_state("CLM-0001")
    assert record["policy"]["clauses"][0]["score"] == 0.24
    assert record["fraud"] == {"score": 24, "reasons": [], "details": [], "waiting_period": None}
    assert len(record["trace"]) == 51
    assert len(logger.read_log("CLM-0001")) == 51
    assert list(tmp_paths["state_dir"].glob("*.tmp")) == []  # no temp files left behind


# ---------- section validation against tools.schemas ----------

@pytest.mark.parametrize("section,bad", [
    ("intake", {**INTAKE, "claimed": 85000.5}),                      # money must be int rupees
    ("intake", {**INTAKE, "claimed": -1}),
    ("intake", {**INTAKE, "discharge": "2026-09-01"}),               # before admit
    ("intake", {**INTAKE, "surprise": 1}),                           # unknown field
    ("bill_items", [{"desc": "Room", "category": "spa", "qty": 1, "amount": 100}]),
    ("cost", {"deductions": [], "payable": "79610"}),                # string, not int
    ("decision", {"verdict": "maybe", "payout": 0, "rationale": "", "confidence": 0.5}),
    ("decision", {"verdict": "approve", "payout": 0, "clauses": ["4.3"], "rationale": "", "confidence": 0.5}),
])
def test_invalid_section_is_rejected_and_nothing_written(tmp_paths, section, bad):
    with pytest.raises(ValueError):
        state.write_state("CLM-0001", section, bad)
    assert not state.state_path("CLM-0001").exists()
    assert logger.read_log() == []


def test_dates_are_stored_as_iso_strings(tmp_paths):
    from datetime import date
    state.write_state("CLM-0001", "intake", {**INTAKE, "admit": date(2026, 9, 2)})
    assert state.read_state("CLM-0001")["intake"]["admit"] == "2026-09-02"
