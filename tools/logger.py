"""Append-only JSONL run log at ``logs/run_log.jsonl`` (config ``paths.run_log``).

Week 1 · Member C (M13). Open the file in append mode only — never rewrite it.
Suggested event fields: ts, claim_id, agent, tool, summary.
"""

from __future__ import annotations

from typing import Any


def append_log(event: dict[str, Any]) -> None:
    """Append one event as a single JSON line (add a UTC timestamp if missing)."""
    raise NotImplementedError("M13 — Week 1, Member C")
