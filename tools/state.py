"""Shared claim-state record helpers — one JSON per claim in ``state/<claim_id>.json``.

Week 1 · Member C (M12). Agents talk to each other only through this record.
Each agent writes only its own section; every write is also appended to the run log.
"""

from __future__ import annotations

from typing import Any

# Section names each agent may write (02-architecture-brief, agent roster).
SECTIONS: tuple[str, ...] = (
    "intake", "bill_items", "policy", "fraud", "cost", "decision", "human", "letters",
)


def read_state(claim_id: str) -> dict[str, Any]:
    """Load ``state/<claim_id>.json`` (path from config ``paths.state_dir``)."""
    raise NotImplementedError("M12 — Week 1, Member C")


def write_state(claim_id: str, section: str, data: Any) -> dict[str, Any]:
    """Write one section of the record, then ``append_log`` the write.

    Must reject unknown sections (see ``SECTIONS``) and must not touch other sections.
    """
    raise NotImplementedError("M12 — Week 1, Member C")
