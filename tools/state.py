"""Shared claim-state record helpers — one JSON per claim in ``state/<claim_id>.json``.

Week 1 · M12. Agents talk to each other only through this record.
- Each agent writes only its own section (``SECTION_OWNERS``).
- Every write is appended to the run log and to the record's own ``trace``.
- Writes are atomic (temp file + rename) and serialised by a lock, because the
  Policy and Fraud agents write in parallel.
"""

from __future__ import annotations

import copy
import json
import os
import re
import tempfile
import threading
from pathlib import Path
from typing import Any

from tools.config import project_path
from tools.logger import append_log, utc_now

# Section names each agent may write (02-architecture-brief, agent roster).
SECTIONS: tuple[str, ...] = (
    "intake", "bill_items", "policy", "fraud", "cost", "decision", "human", "letters",
)

# Which agent module owns which section. Only the owner may write it.
SECTION_OWNERS: dict[str, str] = {
    "intake": "intake_agent",
    "bill_items": "intake_agent",
    "policy": "policy_agent",
    "fraud": "fraud_agent",
    "cost": "cost_agent",
    "decision": "manager_agent",
    "human": "human_desk",
    "letters": "grievance_agent",
}

STATUSES: tuple[str, ...] = ("intake", "assessing", "decided", "escalated", "closed")

# Same shape the API accepts; also stops path tricks like "../x".
CLAIM_ID = re.compile(r"^CLM-\d{4}$")

_LOCK = threading.RLock()


def _check_claim_id(claim_id: str) -> None:
    if not isinstance(claim_id, str) or not CLAIM_ID.match(claim_id):
        raise ValueError(f"claim_id must look like CLM-0001, got {claim_id!r}")


def state_path(claim_id: str) -> Path:
    """Absolute path of ``state/<claim_id>.json`` (dir from config ``paths.state_dir``)."""
    _check_claim_id(claim_id)
    return project_path("state_dir") / f"{claim_id}.json"


def new_state(claim_id: str) -> dict[str, Any]:
    """An empty record in the 02-architecture-brief shape, status ``intake``."""
    _check_claim_id(claim_id)
    record: dict[str, Any] = {"claim_id": claim_id, "status": "intake"}
    for section in SECTIONS:
        record[section] = [] if section == "bill_items" else None
    record["human"] = {"ticket": None, "reviewer": None, "verdict": None, "note": None}
    record["trace"] = []
    return record


def _to_jsonable(data: Any) -> Any:
    """Accept Pydantic models (``model_dump``) or plain JSON data; reject anything else."""
    if hasattr(data, "model_dump"):
        data = data.model_dump(mode="json")
    elif isinstance(data, list):
        data = [d.model_dump(mode="json") if hasattr(d, "model_dump") else d for d in data]
    try:
        json.dumps(data)
    except (TypeError, ValueError) as exc:
        raise TypeError(f"section data is not JSON-serialisable: {exc}") from exc
    return copy.deepcopy(data)


def _save(claim_id: str, record: dict[str, Any]) -> None:
    """Write the whole record atomically: temp file in the same folder, then rename."""
    path = state_path(claim_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{claim_id}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(record, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def read_state(claim_id: str) -> dict[str, Any]:
    """Load ``state/<claim_id>.json``. Raises ``FileNotFoundError`` if the claim has no record yet."""
    path = state_path(claim_id)
    if not path.exists():
        raise FileNotFoundError(f"no claim-state record for {claim_id} at {path}")
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def write_state(
    claim_id: str, section: str, data: Any, *, agent: str | None = None
) -> dict[str, Any]:
    """Write one section of the record, then ``append_log`` the write. Returns the new record.

    - Rejects unknown sections (see ``SECTIONS``); never touches other sections.
    - ``agent`` (optional) is checked against ``SECTION_OWNERS``; a non-owner gets ``PermissionError``.
    - Creates the record (``new_state``) on the first write.
    """
    if section not in SECTIONS:
        raise ValueError(f"unknown section {section!r}; allowed: {', '.join(SECTIONS)}")
    owner = SECTION_OWNERS[section]
    if agent is not None and agent != owner:
        raise PermissionError(f"{agent} may not write section {section!r} (owner: {owner})")
    payload = _to_jsonable(data)

    with _LOCK:
        try:
            record = read_state(claim_id)
        except FileNotFoundError:
            record = new_state(claim_id)
        ts = utc_now()
        record[section] = payload
        record["trace"].append({"ts": ts, "agent": owner, "action": "write", "section": section})
        _save(claim_id, record)
        append_log({
            "ts": ts, "claim_id": claim_id, "agent": owner, "tool": "write_state",
            "section": section, "summary": f"wrote {section}",
        })
    return record


def set_status(claim_id: str, status: str, *, agent: str) -> dict[str, Any]:
    """Move the claim to a new ``status`` (one of ``STATUSES``), logged like any write.

    Used by the workflow, Manager and Human Review Desk; the record must already exist.
    """
    if status not in STATUSES:
        raise ValueError(f"unknown status {status!r}; allowed: {', '.join(STATUSES)}")
    with _LOCK:
        record = read_state(claim_id)
        ts = utc_now()
        old = record["status"]
        record["status"] = status
        record["trace"].append({"ts": ts, "agent": agent, "action": "status", "from": old, "to": status})
        _save(claim_id, record)
        append_log({
            "ts": ts, "claim_id": claim_id, "agent": agent, "tool": "set_status",
            "summary": f"status {old} -> {status}",
        })
    return record
