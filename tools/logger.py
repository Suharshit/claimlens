"""Append-only JSONL run log at ``logs/run_log.jsonl`` (config ``paths.run_log``).

Week 1 · M13. The file is only ever opened in append mode — nothing in the
codebase rewrites or truncates it. One event per line; fields:
``ts`` (UTC ISO-8601), ``claim_id``, ``agent``, ``tool``, ``summary`` plus any extras.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.config import project_path

# Policy and Fraud agents run in parallel; one lock keeps each line whole.
_LOCK = threading.Lock()


def log_path() -> Path:
    """Absolute path of the run log (from config ``paths.run_log``)."""
    return project_path("run_log")


def utc_now() -> str:
    """Current UTC time as ISO-8601 with a ``Z`` suffix, to the millisecond."""
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def append_log(event: dict[str, Any]) -> None:
    """Append one event as a single JSON line (adds a UTC ``ts`` if missing).

    Raises ``TypeError`` if ``event`` is not a dict or holds values JSON cannot encode,
    so a bad event fails loudly instead of corrupting the log.
    """
    if not isinstance(event, dict):
        raise TypeError(f"log event must be a dict, got {type(event).__name__}")
    record = {"ts": utc_now(), **event} if "ts" not in event else dict(event)
    line = json.dumps(record, ensure_ascii=False, sort_keys=False)
    path = log_path()
    with _LOCK:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8", newline="\n") as fh:
            fh.write(line + "\n")


def read_log(claim_id: str | None = None) -> list[dict[str, Any]]:
    """Read the log back (oldest first), optionally only one claim's events.

    For tests, the demo notebook and trace views — never used to rewrite the file.
    """
    path = log_path()
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as fh:
        events = [json.loads(line) for line in fh if line.strip()]
    if claim_id is not None:
        events = [e for e in events if e.get("claim_id") == claim_id]
    return events


def log_step(claim_id: str, agent: str, tool: str, summary: str, **extra: Any) -> None:
    """One trace line for a tool call or agent step (agents call this for every tool they use)."""
    append_log({"claim_id": claim_id, "agent": agent, "tool": tool, "summary": summary, **extra})
