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

from pathlib import Path
from typing import Any


# --- Corpus building (Week 1 · Member B) -----------------------------------

def chunk_wording(pdf_path: str | Path, policy_id: str) -> list[dict[str, Any]]:
    """Split one policy wording (or IRDAI excerpt) into clause-level chunks with metadata."""
    raise NotImplementedError("M3 — Week 1, Member B")


def build_index() -> None:
    """Chunk everything in ``data/corpus/`` and build the BM25 + vector index."""
    raise NotImplementedError("M3 — Week 1, Member B")


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
