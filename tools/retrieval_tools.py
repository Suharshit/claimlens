"""Tools for the Policy Retrieval Agent (M3, M9 support, S5).

Corpus: policy wordings + IRDAI excerpts in ``data/corpus/``, chunked by clause.
Chunk metadata: policy_id, section, clause_id, page.
Retrieval: hybrid BM25 (rank_bm25) + vector search (sentence-transformers, e.g.
bge-small-en, in Chroma/FAISS). ALWAYS filter by policy_id so one policy's clause
is never cited for another.

Limits come from ``policies.json`` (structured), never from retrieval, so the
maths never depends on retrieval luck.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from tools.config import project_path

# --- Corpus building (Week 1 · Member B) -----------------------------------
#
# A wording is split by its own numbering into clause-level chunks:
#   numbered headings      "4.1. Hospitalization"      -> ASJ-01:4.1
#   roman items inside one  "i. Room Rent ..."          -> ASJ-01:4.1.i
#   numbered notes          "Note: ... 2. In case ..."  -> ASJ-01:4.1.1.note2
#   Annexure-A lists        "List I – Items ..."        -> IRDAI:List-I  (policy_id "IRDAI")
# Section ids are dotted lowercase, matching data/corpus/SOURCES.md and policies.json clause_refs.

_TOP = re.compile(r"^(\d{1,2})\.?\s+([A-Z][^\d].*)$")                 # "6 Waiting Period", "4. COVERAGE"
_SUB = re.compile(r"^(\d{1,2}(?:\.\d{1,2}){1,3})\.?\s*([A-Z(][^\n]*)$")  # "4.1. Hospitalization", "4.1.1.Other"
_ROMAN = re.compile(r"^(i{1,3}|iv|v|vi{1,3}|ix|x)\.\s+(\S.*)$")         # "ii. Intensive Care Unit ..."
_NOTE_START = re.compile(r"^Notes?\s*:?\s*$", re.IGNORECASE)
_NOTE_ITEM = re.compile(r"^(\d)\.\s+(\S.*)$")
_ANNEX = re.compile(r"^Annexure[\s\-–:]*([A-Z])\b", re.IGNORECASE)
_LIST = re.compile(r"^List\s+(IV|III|II|I)\b\s*[–-]?\s*(.*)$")


def _strip_running_lines(pages: list[str]) -> list[list[str]]:
    """Drop headers/footers: lines (digits ignored) that repeat on more than half the pages."""
    split = [[ln.strip() for ln in (p or "").splitlines() if ln.strip()] for p in pages]
    norm = lambda ln: re.sub(r"\d+", "#", ln)  # noqa: E731
    counts = Counter(k for lines in split for k in {norm(ln) for ln in lines})
    limit = max(2, len(pages) // 2)
    return [[ln for ln in lines if counts[norm(ln)] <= limit] for lines in split]


def split_clauses(pages: list[str], policy_id: str) -> list[dict[str, Any]]:
    """Split a wording's page texts into clause chunks (pure function, no PDF needed).

    Each chunk: ``clause_id``, ``policy_id``, ``section``, ``title``, ``text``, ``page`` (1-based,
    where the clause starts). Chunks with no text beyond their heading are dropped.
    """
    chunks: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    top = 0                    # current top-level section number
    leaf = ""                  # section id the roman items / notes attach to
    in_note = False
    annex: str | None = None   # inside an annexure: its letter

    def start(section: str, owner: str, title: str, line: str, page: int, heading: bool = True) -> None:
        nonlocal current
        prefix = "IRDAI" if owner == "IRDAI" else policy_id
        current = {"clause_id": f"{prefix}:{section}", "policy_id": owner, "section": section,
                   "title": title.strip()[:120], "lines": [line], "page": page, "heading": heading}
        chunks.append(current)

    for page_no, lines in enumerate(_strip_running_lines(pages), start=1):
        for line in lines:
            m = _ANNEX.match(line)
            if m:
                annex = m.group(1).upper()
                start(f"annex-{annex.lower()}", policy_id, line, line, page_no)
                continue
            if annex:
                m = _LIST.match(line)
                if annex == "A" and m:
                    start(f"List-{m.group(1)}", "IRDAI", m.group(2) or line, line, page_no)
                else:
                    current["lines"].append(line)
                continue

            m = _TOP.match(line)
            if m and int(m.group(1)) == top + 1 and len(line) <= 60:
                top = int(m.group(1))
                leaf, in_note = str(top), False
                start(leaf, policy_id, m.group(2), line, page_no)
                continue
            m = _SUB.match(line)
            if m and int(m.group(1).split(".")[0]) == top and top:
                leaf, in_note = m.group(1), False
                start(leaf, policy_id, m.group(2), line, page_no)
                continue
            if current is not None and _NOTE_START.match(line):
                in_note = True
                continue
            m = _NOTE_ITEM.match(line)
            if in_note and m:
                start(f"{leaf}.note{m.group(1)}", policy_id, m.group(2), line, page_no, heading=False)
                continue
            m = _ROMAN.match(line)
            if m and leaf and not in_note:
                start(f"{leaf}.{m.group(1)}", policy_id, m.group(2), line, page_no, heading=False)
                continue
            if current is not None:
                current["lines"].append(line)

    out = []
    seen: set[str] = set()
    for c in chunks:
        text = "\n".join(c.pop("lines"))
        heading_only = c.pop("heading") and "\n" not in text
        if c["clause_id"] in seen or heading_only:
            continue        # a heading whose items are all their own chunks, or a repeated id
        seen.add(c["clause_id"])
        out.append({**c, "text": text})
    return out


def chunk_wording(pdf_path: str | Path, policy_id: str) -> list[dict[str, Any]]:
    """Split one policy wording (or IRDAI excerpt) into clause-level chunks with metadata."""
    import pdfplumber  # heavy: imported here so api.py still imports on the lean servers

    with pdfplumber.open(str(pdf_path)) as pdf:
        pages = [page.extract_text() or "" for page in pdf.pages]
    return split_clauses(pages, policy_id)


def build_index() -> list[dict[str, Any]]:
    """Chunk every wording in ``data/corpus/`` and write ``data/corpus/chunks.jsonl`` (config ``paths.chunks``).

    Layout: ``corpus/policies/<POLICY_ID>/*.pdf`` and ``corpus/irdai/*.pdf``. The JSONL is committed,
    so CI and servers search it without the (git-ignored) PDFs. BM25 is built from it at search time;
    the vector index comes with ``search_policy_clauses`` (Week 2).
    """
    corpus = project_path("corpus")
    chunks: list[dict[str, Any]] = []
    seen: set[str] = set()
    sources = [(pdf, folder.name) for folder in sorted((corpus / "policies").glob("*")) if folder.is_dir()
               for pdf in sorted(folder.glob("*.pdf"))]
    sources += [(pdf, "IRDAI") for pdf in sorted((corpus / "irdai").glob("*.pdf"))]
    for pdf, policy_id in sources:
        for c in chunk_wording(pdf, policy_id):
            if c["clause_id"] not in seen:     # IRDAI lists repeat across wordings: keep the first
                seen.add(c["clause_id"])
                chunks.append({**c, "source": pdf.name})
    out = project_path("chunks")
    with out.open("w", encoding="utf-8", newline="\n") as fh:
        for c in chunks:
            fh.write(json.dumps(c, ensure_ascii=False) + "\n")
    return chunks


def load_chunks(policy_id: str | None = None) -> list[dict[str, Any]]:
    """Read ``chunks.jsonl``; optionally only one policy's chunks (``"IRDAI"`` for the IRDAI lists)."""
    path = project_path("chunks")
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as fh:
        chunks = [json.loads(line) for line in fh if line.strip()]
    return [c for c in chunks if policy_id is None or c["policy_id"] == policy_id]


# --- Agent tools (Week 2 · Member B) ----------------------------------------

def search_policy_clauses(policy_id: str, query: str, k: int | None = None) -> list[dict[str, Any]]:
    """Hybrid search over that policy's chunks; returns clause_id, text, score.
    ``k`` defaults to config ``retrieval.top_k``."""
    raise NotImplementedError("M3 — Week 2, Member B")


def get_policy_limits(policy_id: str) -> dict[str, Any]:
    """Structured limits from ``policies.json``: sum insured, room-rent and ICU caps,
    co-pay %, sub-limits, waiting periods."""
    raise NotImplementedError("M3 — Week 2, Member B")


def search_irdai_rules(query: str) -> list[dict[str, Any]]:
    """Search IRDAI excerpts, e.g. the non-payable item lists."""
    raise NotImplementedError("M3 — Week 2, Member B")
