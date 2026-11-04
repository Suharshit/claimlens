"""Test layer 1: unit tests on deterministic tools with exact rupee assertions.

Targets (03-features-and-scope): room_rent_deduction, compute_payable, score_risk,
plus parse_bill (Week 1). Replace each skip with real tests as the tool lands.
Use hand-worked numbers from data/policies.json — never values computed by the code under test.
"""

import json

import pytest

from tools.config import project_path
from tools.intake_tools import IntakeHalt, parse_bill, validate_policy

# ---------- parse_bill (M1) ----------


def write(tmp_path, name, text):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def test_parse_bill_reads_line_items():
    items = parse_bill(project_path("claims") / "CLM-0001" / "bill.csv")
    assert len(items) == 11
    assert items[0] == {"desc": "Room charges (twin sharing)", "category": "room", "qty": 3, "amount": 12000}
    assert items[6]["desc"] == "Investigations (CBC, USG abdomen)"     # quoted comma kept
    assert sum(i["amount"] for i in items) == 85000
    assert all(isinstance(i["amount"], int) for i in items)


def test_parse_bill_accepts_indian_commas_rupee_sign_and_bom(tmp_path):
    path = tmp_path / "bill.csv"
    path.write_bytes("\ufeffdesc,category,qty,amount\nSurgery,professional,1,\"₹1,51,230\"\n".encode("utf-8"))
    assert parse_bill(path) == [{"desc": "Surgery", "category": "professional", "qty": 1, "amount": 151230}]


def test_parse_bill_reads_json(tmp_path):
    path = write(tmp_path, "bill.json", json.dumps([{"desc": "Room", "category": "Room", "qty": 2, "amount": 9000}]))
    assert parse_bill(path) == [{"desc": "Room", "category": "room", "qty": 2, "amount": 9000}]


@pytest.mark.parametrize("row,message", [
    ("Gloves,consumables,1,450.50", "whole rupees"),       # paise refused
    ("Gloves,consumables,1,-450", "whole rupees"),
    ("Gloves,consumables,one,450", "qty"),
    ("Gloves,consumables,0,450", "qty"),
    ("Gloves,spa,1,450", "category"),
    (",consumables,1,450", "desc"),
    ("Gloves,consumables,1", "incomplete"),
    ("Gloves, sterile,consumables,1,450", "too many columns"),   # unquoted comma
])
def test_parse_bill_halts_with_row_number(tmp_path, row, message):
    path = write(tmp_path, "bill.csv", f"desc,category,qty,amount\nRoom,room,1,4000\n{row}\n")
    with pytest.raises(IntakeHalt, match="row 2") as exc:
        parse_bill(path)
    assert message in str(exc.value)


@pytest.mark.parametrize("name,text,message", [
    ("bill.csv", "item,cost\nRoom,4000\n", "header"),
    ("bill.csv", "desc,category,qty,amount\n", "no line items"),
    ("bill.json", "{}", "list"),
    ("bill.txt", "Room 4000", ".csv or .json"),
])
def test_parse_bill_halts_on_bad_file(tmp_path, name, text, message):
    with pytest.raises(IntakeHalt, match=message):
        parse_bill(write(tmp_path, name, text))


def test_parse_bill_missing_file(tmp_path):
    with pytest.raises(IntakeHalt, match="not found"):
        parse_bill(tmp_path / "nope.csv")


# ---------- validate_policy (M1, M2) ----------


def test_validate_policy_returns_limits():
    limits = validate_policy("ASJ-01")
    assert limits["sum_insured"] == 500000
    assert limits["room_cap_per_day"] == 5000
    assert limits["copay_pct"] == 5


def test_validate_policy_is_case_and_space_tolerant():
    assert validate_policy(" asj-01 ")["policy_id"] == "ASJ-01"


@pytest.mark.parametrize("policy_id,message", [(None, "missing"), ("", "missing"), ("XYZ-99", "unknown policy")])
def test_validate_policy_halts(policy_id, message):
    with pytest.raises(IntakeHalt, match=message):
        validate_policy(policy_id)


@pytest.mark.skip(reason="Week 2 — Member A: room_rent_deduction (exact ₹)")
def test_room_rent_proportionate_deduction():
    ...


@pytest.mark.skip(reason="Week 2 — Member A: compute_payable (exact ₹)")
def test_compute_payable_copay_sublimits_and_cap():
    ...


@pytest.mark.skip(reason="Week 2 — Member C: score_risk")
def test_score_risk_reasons_and_threshold():
    ...
