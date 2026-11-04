"""Tools for the Intake Agent (M1, M2)."""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from tools.config import project_path
from tools.schemas import BillItem, PolicyLimits


class IntakeHalt(ValueError):
    """Intake cannot continue (M2): missing or invalid data. The message says what to ask for.

    The workflow catches this, stops the claim, and runs no downstream agent (scenario 7).
    """


def extract_claim_fields(text: str) -> dict[str, Any]:
    """LLM call with a Pydantic schema → patient, admit/discharge dates, diagnosis,
    room type, claimed amount, policy id. Temperature 0.

    M2: if policy id or claimed amount is missing, halt with a clear message
    rather than guessing (scenario 7).
    """
    raise NotImplementedError("M1/M2 — Week 2 (needs framework + model lane)")


# Whole rupees, optionally with Indian or western comma grouping: 450, 1,500, 1,51,230.
_RUPEES = re.compile(r"^\d{1,3}(,\d{2,3})*$|^\d+$")


def _to_rupees(raw: Any, where: str) -> int:
    if isinstance(raw, bool):
        raise IntakeHalt(f"{where}: amount must be whole rupees, got {raw!r}")
    if isinstance(raw, int):
        return raw
    text = str(raw).strip().removeprefix("₹").removeprefix("Rs.").removeprefix("Rs").strip()
    if not _RUPEES.match(text):
        raise IntakeHalt(f"{where}: amount must be whole rupees (no paise), got {raw!r}")
    return int(text.replace(",", ""))


def _to_qty(raw: Any, where: str) -> int:
    text = str(raw).strip()
    if not text.isdigit():
        raise IntakeHalt(f"{where}: qty must be a whole number, got {raw!r}")
    return int(text)


def parse_bill(path: str | Path) -> list[dict[str, Any]]:
    """Read a bill CSV/JSON into line items: desc, category, qty, amount (int ₹).

    CSV needs the header ``desc,category,qty,amount``; JSON is a list of objects with
    those keys. Amounts must be whole rupees (``1,51,230`` and a leading ``₹`` are fine;
    paise are refused, since rounding happens only in ``compute_payable``).
    Raises ``IntakeHalt`` naming the file and row on any problem.
    """
    path = Path(path)
    if not path.is_file():
        raise IntakeHalt(f"bill file not found: {path}")

    suffix = path.suffix.lower()
    if suffix == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as fh:   # -sig: Excel's BOM
            reader = csv.DictReader(fh)
            expected = {"desc", "category", "qty", "amount"}
            header = {h.strip() for h in (reader.fieldnames or [])}
            if header != expected:
                raise IntakeHalt(f"{path.name}: header must be desc,category,qty,amount, got {reader.fieldnames}")
            rows = []
            for n, row in enumerate(reader, start=1):
                if None in row:   # DictReader puts surplus columns under the key None
                    raise IntakeHalt(f"{path.name} row {n}: too many columns — quote any description containing a comma")
                rows.append({k.strip(): v for k, v in row.items()})
    elif suffix == ".json":
        with path.open(encoding="utf-8") as fh:
            rows = json.load(fh)
        if not isinstance(rows, list):
            raise IntakeHalt(f"{path.name}: JSON bill must be a list of line items")
    else:
        raise IntakeHalt(f"{path.name}: bill must be .csv or .json")

    items: list[dict[str, Any]] = []
    for n, row in enumerate(rows, start=1):
        where = f"{path.name} row {n}"
        if not isinstance(row, dict) or any(v is None for v in row.values()):
            raise IntakeHalt(f"{where}: incomplete line")
        try:
            item = BillItem(
                desc=str(row.get("desc", "")).strip(),
                category=str(row.get("category", "")).strip().lower(),
                qty=_to_qty(row.get("qty"), where),
                amount=_to_rupees(row.get("amount"), where),
            )
        except ValidationError as exc:
            field = ".".join(str(p) for p in exc.errors()[0]["loc"])
            raise IntakeHalt(f"{where}: bad {field} — {exc.errors()[0]['msg']}") from exc
        items.append(item.model_dump())

    if not items:
        raise IntakeHalt(f"{path.name}: bill has no line items")
    return items


def load_policies() -> dict[str, dict[str, Any]]:
    """All policies from ``policies.json`` (config ``paths.policies``), each validated."""
    with project_path("policies").open(encoding="utf-8") as fh:
        raw = json.load(fh)
    policies = {}
    for key, entry in raw.items():
        limits = PolicyLimits.model_validate(entry)
        if limits.policy_id != key:
            raise ValueError(f"policies.json: key {key} does not match policy_id {limits.policy_id}")
        policies[key] = limits.model_dump(mode="json")
    return policies


def validate_policy(policy_id: str | None) -> dict[str, Any]:
    """Confirm the policy exists in ``policies.json``; halt with a clear error if not.

    Returns that policy's limits (the ``PolicyLimits`` shape).
    """
    if not policy_id or not str(policy_id).strip():
        raise IntakeHalt("policy id is missing — ask the claimant for the policy number")
    policy_id = str(policy_id).strip().upper()
    policies = load_policies()
    if policy_id not in policies:
        raise IntakeHalt(f"unknown policy id {policy_id} — check the policy number with the claimant")
    return policies[policy_id]
