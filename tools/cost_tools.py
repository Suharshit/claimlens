"""Tools for the Cost Assessment Agent (M4, M5, S1).

ALL rupee maths lives here, never in the LLM. Every money value is an ``int``
in rupees; rounding happens only inside ``compute_payable``. Each function gets
exact-rupee unit tests in tests/test_cost_tools.py.

Order of the calculation (ASJ-01 wording; see context/05-progress.md):
  1. ``classify_items``      — IRDAI List I lines are not payable; Lists II–IV lines billed
                               separately are subsumed (not paid on their own).
  2. ``room_rent_deduction`` — room + boarding + nursing per day are capped together (4.1.i), ICU
                               separately (4.1.ii); above a cap, every other payable expense except
                               medicines is cut in proportion cap ÷ actual rate (4.1.1 note 2).
  3. ``compute_payable``     — rounds each cut, then a sub-limit if one applies, then the co-pay on
                               the admissible amount (9.3), then the sum-insured cap; sets the
                               over-claim flag (M5).
"""

from __future__ import annotations

import re
from fractions import Fraction
from functools import lru_cache
from math import floor
from typing import Any

from tools.config import load_config
from tools.schemas import CostSection

# IRDAI lists (Annexure-A) and what a match means.
_LISTS = {
    "IRDAI:List-I": ("non_payable", "non-payable item"),
    "IRDAI:List-II": ("subsumed", "subsumed into room charges"),
    "IRDAI:List-III": ("subsumed", "subsumed into procedure charges"),
    "IRDAI:List-IV": ("subsumed", "subsumed into costs of treatment"),
}
ROOM_CATEGORIES = ("room", "nursing")          # capped together per day (4.1.i)
NOT_PROPORTIONED = ("room", "nursing", "icu", "pharmacy")   # note 2: medicines exempt
SUB_LIMIT_CLAUSE = {"cataract_per_eye": "cataract", "modern_treatments": "modern_treatments"}


def _norm(text: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9 ]+", " ", text.lower()).split())


def _names(item: str) -> set[str]:
    """Match keys for one list entry: the whole name, plus '/' or ',' alternatives when unqualified."""
    names = {_norm(item)}
    if "(" not in item and "[" not in item:
        names |= {_norm(part) for part in re.split(r"[/,\\\\]", item) if _norm(part)}
    return names


@lru_cache(maxsize=1)
def irdai_lists() -> dict[str, frozenset[str]]:
    """Item names of IRDAI Lists I–IV, read from the committed corpus (``chunks.jsonl``)."""
    from tools.retrieval_tools import load_chunks

    lists: dict[str, frozenset[str]] = {}
    for chunk in load_chunks("IRDAI"):
        if chunk["clause_id"] not in _LISTS:
            continue
        entries: list[str] = []
        for line in chunk["text"].splitlines()[1:]:
            m = re.match(r"^(\d+)\s+(.+)$", line.strip())
            if m:
                entries.append(m.group(2))
            elif entries and not line.startswith(("Sl", "No")):
                entries[-1] += " " + line.strip()        # wrapped entry
        lists[chunk["clause_id"]] = frozenset(n for e in entries for n in _names(e))
    return lists


def classify_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Mark each bill line payable, non-payable or subsumed using the IRDAI lists.

    Adds ``status`` (``payable | non_payable | subsumed``), ``list_clause`` and ``list_reason``.
    Matching is exact on the normalised description (with or without its bracketed part), so a
    line is only excluded when the list names it. Returns new dicts; the input is not changed.
    """
    lists = irdai_lists()
    out = []
    for item in items:
        desc = _norm(item["desc"])
        bare = _norm(re.sub(r"\(.*?\)", "", item["desc"]))
        status, clause, reason = "payable", None, None
        for clause_id, names in lists.items():
            if desc in names or bare in names:
                status, reason = _LISTS[clause_id]
                clause = clause_id
                break
        out.append({**item, "status": status, "list_clause": clause, "list_reason": reason})
    return out


def _fmt(x: Fraction) -> str:
    return str(x.numerator) if x.denominator == 1 else f"{float(x):.2f}"


def room_rent_deduction(items: list[dict[str, Any]], limits: dict[str, Any]) -> list[dict[str, Any]]:
    """Apply proportionate deduction when the room exceeds the daily cap (scenario 2).

    Takes classified items. Returns new dicts, each with ``admissible`` (exact ``Fraction`` —
    nothing is rounded here) and ``cuts``: a list of ``{item, amount, reason, clause_id}`` with
    ``Fraction`` amounts. The room-cap cut is one row on the first room line.
    """
    refs = limits.get("clause_refs", {})
    rows = [{**i, "admissible": Fraction(i["amount"]) if i["status"] == "payable" else Fraction(0), "cuts": []}
            for i in items]
    payable = [r for r in rows if r["status"] == "payable"]
    ratios: list[tuple[Fraction, Fraction, Fraction]] = []      # (ratio, cap, rate)

    room = [r for r in payable if r["category"] == "room"]
    if room:
        days = sum(r["qty"] for r in room)
        pooled = [r for r in payable if r["category"] in ROOM_CATEGORIES]
        billed = sum(Fraction(r["amount"]) for r in pooled)
        cap = Fraction(limits["room_cap_per_day"])
        rate = billed / days
        if rate > cap:
            cut = billed - cap * days
            ratios.append((cap / rate, cap, rate))
            remaining = cut
            for r in pooled:                       # take the cut from room first, then nursing
                take = min(remaining, r["admissible"])
                r["admissible"] -= take
                remaining -= take
            label = "Room + nursing" if any(r["category"] == "nursing" for r in pooled) else "Room charges"
            room[0]["cuts"].append({
                "item": f"{label} ({days} days)", "amount": cut,
                "reason": f"room rent, boarding and nursing above cap: {days} x ({_fmt(rate)} - {_fmt(cap)})",
                "clause_id": refs.get("room_rent")})

    for r in [r for r in payable if r["category"] == "icu"]:
        cap = Fraction(limits["icu_cap_per_day"])
        rate = Fraction(r["amount"], r["qty"])
        if rate > cap:
            cut = Fraction(r["amount"]) - cap * r["qty"]
            r["admissible"] -= cut
            ratios.append((cap / rate, cap, rate))
            r["cuts"].append({"item": f"ICU charges ({r['qty']} days)", "amount": cut,
                              "reason": f"ICU above cap: {r['qty']} x ({_fmt(rate)} - {_fmt(cap)})",
                              "clause_id": refs.get("icu")})

    if ratios:
        ratio, cap, rate = min(ratios)
        for r in payable:
            if r["category"] in NOT_PROPORTIONED:
                continue
            cut = r["admissible"] * (1 - ratio)
            if cut:
                r["admissible"] -= cut
                r["cuts"].append({"item": r["desc"], "amount": cut,
                                  "reason": f"proportionate deduction {_fmt(cap)}/{_fmt(rate)}",
                                  "clause_id": refs.get("proportionate_deduction")})
    return rows


def _round(x: Fraction) -> int:
    """Half-up to whole rupees — the only rounding in ClaimLens."""
    return floor(x + Fraction(1, 2))


def overclaim_flag(claimed: int, payable: int, margin_pct: int | float) -> bool:
    """M5: claimed exceeds payable by more than ``margin_pct`` percent (never for a zero payable)."""
    return payable > 0 and (claimed - payable) * 100 > margin_pct * payable


def compute_payable(
    items: list[dict[str, Any]], limits: dict[str, Any], *,
    sub_limit: str | None = None, margin_pct: int | float | None = None,
) -> dict[str, Any]:
    """Apply sub-limits, co-pay and sum-insured cap.

    Returns {"payable": int, "deductions": [{item, amount, reason, clause_id}, ...], "overclaim": bool}
    — the ``cost`` section, validated by ``CostSection``. ``items`` are bill lines (classified or not).
    ``sub_limit`` names a key of ``limits["sub_limits"]`` (e.g. ``cataract_per_eye``) when the
    treatment has one; ``margin_pct`` defaults to config ``thresholds.overclaim_margin_pct``.
    Rows come in this order: room/ICU caps, proportionate cuts, non-payable/subsumed lines,
    sub-limit, co-pay, sum-insured cap — so ``claimed − Σ amounts = payable`` always holds.
    """
    if margin_pct is None:
        margin_pct = load_config()["thresholds"]["overclaim_margin_pct"]
    refs = limits.get("clause_refs", {})
    classified = items if all("status" in i for i in items) else classify_items(items)
    rows = room_rent_deduction(classified, limits)
    claimed = sum(i["amount"] for i in items)

    deductions: list[dict[str, Any]] = []
    cap_rows = [c for r in rows for c in r["cuts"] if not c["reason"].startswith("proportionate")]
    prop_rows = [c for r in rows for c in r["cuts"] if c["reason"].startswith("proportionate")]
    for c in cap_rows + prop_rows:
        deductions.append({**c, "amount": _round(c["amount"])})
    for r in rows:
        if r["status"] != "payable":
            deductions.append({"item": r["desc"], "amount": r["amount"], "reason": r["list_reason"],
                               "clause_id": r["list_clause"]})
    admissible = claimed - sum(d["amount"] for d in deductions)

    if sub_limit:
        cap = limits["sub_limits"][sub_limit]
        if admissible > cap:
            deductions.append({"item": f"Sub-limit: {sub_limit.replace('_', ' ')}", "amount": admissible - cap,
                               "reason": f"sub-limit {cap}", "clause_id": refs.get(SUB_LIMIT_CLAUSE.get(sub_limit, ""))})
            admissible = cap

    pct = limits["copay_pct"]
    copay = _round(Fraction(admissible * pct, 100))
    if copay:
        deductions.append({"item": f"Co-payment {pct}%", "amount": copay,
                           "reason": f"{pct}% co-payment on admissible claim", "clause_id": refs.get("copay")})
    payable = admissible - copay

    if payable > limits["sum_insured"]:
        deductions.append({"item": "Sum insured cap", "amount": payable - limits["sum_insured"],
                           "reason": f"payable limited to sum insured {limits['sum_insured']}", "clause_id": None})
        payable = limits["sum_insured"]

    deductions = [d for d in deductions if d["amount"]]
    section = CostSection(deductions=deductions, payable=payable,
                          overclaim=overclaim_flag(claimed, payable, margin_pct))
    return section.model_dump(mode="json")
