"""Tests for corpus building (M3): the clause splitter and the committed chunks.jsonl."""

from __future__ import annotations

import json

import pytest
from pydantic import TypeAdapter

from tools.config import project_path
from tools.intake_tools import load_policies
from tools.retrieval_tools import build_index, chunk_wording, load_chunks, split_clauses
from tools.schemas import ClauseId

HEADER = "Policy Wording – Example Policy"
FOOTER = "UIN: EX123 Page {n} of 3"

PAGES = [
    f"""{HEADER}
1. PREAMBLE
This policy is a contract.
2. COVERAGE
2.1. Hospitalization
The Company shall indemnify:
i. Room Rent, Boarding, Nursing up to Rs.5000/- per day.
ii. ICU up to Rs.10,000/- per day.
2.1.1.Other expenses
i. Ambulance up to Rs.2000/-.
Note:
1. Minimum 24 hours.
2. Above the limits, other expenses except medicines are cut in proportion.
{FOOTER.format(n=1)}""",
    f"""{HEADER}
3 Waiting Period
3.1. Specific Waiting Period
a) Listed conditions are excluded.
i. 24 Months waiting period
1. Hernia of all types
2. Cataract
ii. 48 Months waiting period
1. Joint replacement
{FOOTER.format(n=2)}""",
    f"""{HEADER}
Annexure-A
List I – Items for which coverage is not available in the policy
1 GLOVES
2 MASK
List II – Items that are to be subsumed into Room Charges
1 BED CHARGES
Annexure – B
Grievance offices
{FOOTER.format(n=3)}""",
]


@pytest.fixture(scope="module")
def chunks():
    return {c["clause_id"]: c for c in split_clauses(PAGES, "EX-01")}


def test_ids_follow_the_wording_layout(chunks):
    assert list(chunks) == [
        "EX-01:1", "EX-01:2.1", "EX-01:2.1.i", "EX-01:2.1.ii",
        "EX-01:2.1.1.i", "EX-01:2.1.1.note1", "EX-01:2.1.1.note2",
        "EX-01:3.1", "EX-01:3.1.i", "EX-01:3.1.ii",
        "IRDAI:List-I", "IRDAI:List-II", "EX-01:annex-b",
    ]


def test_heading_only_sections_are_dropped(chunks):
    assert "EX-01:2" not in chunks          # "2. COVERAGE" has no text of its own
    assert "EX-01:3" not in chunks
    assert "EX-01:annex-a" not in chunks    # its lists are their own chunks


def test_numbered_list_items_stay_inside_their_clause(chunks):
    text = chunks["EX-01:3.1.i"]["text"]
    assert "Hernia of all types" in text and "Cataract" in text
    assert "Joint replacement" not in text
    assert "EX-01:1" in chunks and "Hernia" not in chunks["EX-01:1"]["text"]


def test_headers_and_footers_are_removed(chunks):
    for c in chunks.values():
        assert HEADER not in c["text"]
        assert "UIN: EX123" not in c["text"]


def test_metadata(chunks):
    c = chunks["EX-01:2.1.1.note2"]
    assert c["policy_id"] == "EX-01" and c["section"] == "2.1.1.note2" and c["page"] == 1
    assert "except medicines" in c["text"]
    lst = chunks["IRDAI:List-I"]
    assert lst["policy_id"] == "IRDAI" and lst["page"] == 3
    assert "GLOVES" in lst["text"] and "BED CHARGES" not in lst["text"]


# ---------- the committed corpus (data/corpus/chunks.jsonl) ----------

CLAUSE_ID = TypeAdapter(ClauseId)


def test_chunks_file_is_valid():
    chunks = load_chunks()
    assert len(chunks) > 100
    ids = [c["clause_id"] for c in chunks]
    assert len(ids) == len(set(ids))
    for c in chunks:
        CLAUSE_ID.validate_python(c["clause_id"])
        assert c["text"].strip() and c["page"] >= 1
        assert c["clause_id"].startswith(f'{c["policy_id"]}:')


def test_every_referenced_clause_is_in_the_corpus():
    ids = {c["clause_id"] for c in load_chunks()}
    refs = {ref for p in load_policies().values() for ref in p["clause_refs"].values()}
    for folder in (p for p in project_path("claims").iterdir() if p.is_dir()):
        exp = json.loads((folder / "expected.json").read_text(encoding="utf-8"))
        refs |= set(exp.get("clauses", []))
    missing = refs - ids
    assert not missing, f"clause ids not in chunks.jsonl: {sorted(missing)}"


@pytest.mark.parametrize("clause_id,phrases", [
    ("ASJ-01:4.1.i", ["Nursing", "2% of the sum insured", "5000"]),
    ("ASJ-01:4.1.ii", ["5% of sum insured", "10,000"]),
    ("ASJ-01:4.1.1.note2", ["exception of cost of medicines", "same proportion"]),
    ("ASJ-01:4.3", ["25% of Sum", "40,000"]),
    ("ASJ-01:6.1", ["36 months"]),
    ("ASJ-01:6.2.i", ["30 days", "accident"]),
    ("ASJ-01:6.3.i", ["24 Months", "Hernia of all types"]),
    ("ASJ-01:6.3.ii", ["48 Months", "joint replacement"]),
    ("ASJ-01:9.3", ["Co-payment of 5%"]),
    ("IRDAI:List-I", ["GLOVES", "MASK", "LAUNDRY CHARGES", "TELEPHONE CHARGES"]),
])
def test_clause_text_says_what_the_maths_assumes(clause_id, phrases):
    text = {c["clause_id"]: c["text"] for c in load_chunks()}[clause_id]
    for phrase in phrases:
        assert phrase in text, f"{clause_id} should mention {phrase!r}"


def test_ghc01_has_no_wording_for_scenario_6():
    assert load_chunks("GHC-01") == []


def test_committed_chunks_match_the_pdf(tmp_path, monkeypatch):
    """Only where the (git-ignored) PDF is present: rebuilding gives exactly the committed file."""
    pytest.importorskip("pdfplumber")
    pdf = project_path("corpus") / "policies" / "ASJ-01" / "wording.pdf"
    if not pdf.exists():
        pytest.skip("ASJ-01 wording PDF not downloaded (see data/corpus/SOURCES.md)")
    committed = load_chunks()
    import tools.retrieval_tools as rt
    real = rt.project_path
    monkeypatch.setattr(rt, "project_path", lambda key: tmp_path / "chunks.jsonl" if key == "chunks" else real(key))
    assert build_index() == committed
    assert [c["clause_id"] for c in chunk_wording(pdf, "ASJ-01")][:3] == ["ASJ-01:1", "ASJ-01:2", "ASJ-01:3"]
