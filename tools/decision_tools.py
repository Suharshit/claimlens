"""Tools for the Adjudication Manager (M8–M10), the Human Review Desk (M11)
and the Grievance Drafter (S2, should-have)."""

from __future__ import annotations

import json
import os
import tempfile
import threading
from typing import Any

from tools.config import load_config, project_path
from tools.logger import append_log, utc_now
from tools.schemas import DecisionSection, HumanSection
from tools.state import read_state, set_status, write_state


def format_inr(amount: int) -> str:
    """Indian digit grouping for display: 426550 -> '4,26,550'. Display only — no maths."""
    s = str(amount)
    if len(s) <= 3:
        return s
    head, tail = s[:-3], s[-3:]
    groups = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    return ",".join(([head] if head else []) + groups + [tail])


# --- Adjudication Manager ----------------------------------------------------

_REASON_TEXT = {
    "high_value": "claimed amount above the human-review threshold",
    "fraud_risk": "fraud risk score at or above the threshold",
    "no_grounding": "no grounding clause found",
    "citation_failed": "a cited clause was not in the retrieved set",
    "low_confidence": "grounding confidence below the threshold",
}


def _routine_clauses(limits: dict[str, Any]) -> set[str]:
    """Deductions under these clauses (IRDAI lists, co-pay) still leave an 'approve'."""
    refs = limits.get("clause_refs", {})
    return {"IRDAI:List-I", "IRDAI:List-II", "IRDAI:List-III", "IRDAI:List-IV", refs.get("copay")} - {None}


def verify_citations(clause_ids: list[str], retrieved_ids: list[str]) -> dict[str, Any]:
    """Citation guard (M9): every cited clause id must be in the retrieved set.
    Any miss forces escalation.

    Returns ``{"ok": bool, "missing": [...]}`` (missing ids in citation order).
    """
    retrieved = set(retrieved_ids)
    missing = [c for c in dict.fromkeys(clause_ids) if c not in retrieved]
    return {"ok": not missing, "missing": missing}


def apply_decision_rules(state: dict[str, Any]) -> dict[str, Any]:
    """Thresholds from config → approve, partial, reject or escalate (+ escalation reason).

    Escalate when: claimed > human_review_amount_inr; fraud score >= fraud_escalate_score;
    no clause above min_similarity; citation guard fails; confidence < min_confidence.
    "No grounding" means no clause from the claim's own policy wording was retrieved — the IRDAI
    lists apply to every policy, so they alone don't ground a decision (scenario 6).

    Base verdict: ``reject`` if the Fraud agent's waiting-period check excluded the admission
    (payout 0, the waiting clause cited); ``partial`` if any deduction goes beyond the routine
    IRDAI-list and co-pay rows; otherwise ``approve``. Cited clauses = the clauses behind the
    deductions (or the waiting clause). Confidence = the lowest retrieval score among cited
    clauses (0 for a cited clause that wasn't retrieved; 1.0 when nothing needs citing). An escalation keeps the recommended payout.
    Returns a ``DecisionSection`` dict.
    """
    cfg = load_config()["thresholds"]
    intake, cost = state["intake"], state["cost"]
    policy = state.get("policy") or {}
    fraud = state.get("fraud") or {}
    limits = policy.get("limits") or {}
    retrieved = {c["clause_id"]: c["score"] for c in policy.get("clauses", [])}
    own = [c for c in retrieved if c.startswith(f"{intake['policy_id']}:")]   # the policy's own wording
    claimed = intake["claimed"]

    wait = fraud.get("waiting_period") or {}
    if wait.get("excluded"):
        verdict, payout, cited = "reject", 0, [wait["clause_id"]]
        why = f"Rejected: {wait['condition']} is inside its waiting period until {wait['waiting_ends']}"
    else:
        payout = cost["payable"]
        cited = list(dict.fromkeys(d["clause_id"] for d in cost["deductions"] if d.get("clause_id")))
        heavy = [d for d in cost["deductions"] if d.get("clause_id") not in _routine_clauses(limits)]
        verdict = "partial" if heavy else "approve"
        why = (f"{'Partially approved' if heavy else 'Approved'}: payable ₹{format_inr(payout)} "
               f"of ₹{format_inr(claimed)} claimed")
        if cost["deductions"]:
            why += "; deductions: " + "; ".join(
                f"{d['item']} ₹{format_inr(d['amount'])} ({d.get('clause_id') or 'no clause'})" for d in cost["deductions"])

    reasons: list[str] = []
    if claimed > cfg["human_review_amount_inr"]:
        reasons.append("high_value")
    if fraud.get("score", 0) >= cfg["fraud_escalate_score"]:
        reasons.append("fraud_risk")
    if not own:
        reasons.append("no_grounding")
        cited, confidence = [], 0.0
    else:
        guard = verify_citations(cited, list(retrieved))
        if not guard["ok"]:
            reasons.append("citation_failed")
            why += f"; not retrieved: {', '.join(guard['missing'])}"
        scores = [retrieved.get(c, 0.0) for c in cited]          # an unretrieved citation has no grounding
        confidence = min(scores) if scores else 1.0
        if confidence < cfg["min_confidence"]:
            reasons.append("low_confidence")

    if reasons:
        why = (f"Escalated to a human reviewer ({'; '.join(_REASON_TEXT[r] for r in reasons)}). "
               f"Recommendation — {why}")
        verdict = "escalate"
    return DecisionSection(verdict=verdict, payout=payout, clauses=cited, rationale=why + ".",
                           confidence=round(confidence, 3), escalation_reasons=reasons).model_dump(mode="json")


def write_decision(state: dict[str, Any], decision: dict[str, Any] | None = None) -> dict[str, Any]:
    """Write verdict, payout, clauses and rationale to the ``decision`` section.

    ``decision`` defaults to ``apply_decision_rules(state)``. Status becomes ``escalated`` for an
    escalation; otherwise ``decided`` and then ``closed`` (an auto decision closes the claim).
    Returns the updated record.
    """
    decision = decision or apply_decision_rules(state)
    claim_id = state["claim_id"]
    write_state(claim_id, "decision", decision, agent="manager_agent")
    if decision["verdict"] == "escalate":
        return set_status(claim_id, "escalated", agent="manager_agent")
    set_status(claim_id, "decided", agent="manager_agent")
    return set_status(claim_id, "closed", agent="manager_agent")


# --- Human Review Desk (group-of-3 add-on) -----------------------------------

_QUEUE_LOCK = threading.Lock()


def _read_queue() -> list[dict[str, Any]]:
    path = project_path("review_queue")
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []


def _write_queue(queue: list[dict[str, Any]]) -> None:
    path = project_path("review_queue")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".review_queue.", suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(queue, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    os.replace(tmp, path)


def review_queue(open_only: bool = True) -> list[dict[str, Any]]:
    """Tickets in ``review_queue.json`` (config ``paths.review_queue``), oldest first."""
    queue = _read_queue()
    return [t for t in queue if t["status"] == "open"] if open_only else queue


def create_review_ticket(claim_id: str, summary: str) -> dict[str, Any]:
    """Add the claim to ``review_queue.json`` with a one-paragraph summary.

    One open ticket per claim (calling again returns it). Also writes the ticket id into the
    record's ``human`` section and logs the step. Returns the ticket.
    """
    with _QUEUE_LOCK:
        queue = _read_queue()
        for t in queue:
            if t["claim_id"] == claim_id and t["status"] == "open":
                return t
        ticket = {"ticket": f"RV-{len(queue) + 1:04d}", "claim_id": claim_id, "summary": summary,
                  "status": "open", "opened": utc_now(), "closed": None}
        queue.append(ticket)
        _write_queue(queue)
    write_state(claim_id, "human", HumanSection(ticket=ticket["ticket"]), agent="human_desk")
    append_log({"claim_id": claim_id, "agent": "human_desk", "tool": "create_review_ticket",
                "summary": f"ticket {ticket['ticket']} opened"})
    return ticket


def record_human_verdict(
    claim_id: str, verdict: str, note: str, *, reviewer: str = "reviewer", payout: int | None = None,
) -> dict[str, Any]:
    """Write the human verdict back into the record and set status to closed.

    ``verdict`` is approve / partial / reject. Payout: approve → the Manager's recommended payout,
    reject → 0, partial → ``payout`` (required, at most the recommendation). The claim must be
    escalated with an open ticket. Returns the closed record.
    """
    record = read_state(claim_id)
    if record["status"] != "escalated" or not (record.get("human") or {}).get("ticket"):
        raise ValueError(f"{claim_id} is not waiting for a reviewer (status {record['status']})")
    if not note or not note.strip():
        raise ValueError("a reviewer note is required")
    recommended = record["decision"]["payout"]
    if verdict == "approve":
        payout = recommended
    elif verdict == "reject":
        payout = 0
    elif verdict == "partial":
        if payout is None or not 0 <= payout <= recommended:
            raise ValueError(f"a partial verdict needs a payout between 0 and {recommended}")
    else:
        raise ValueError("verdict must be approve, partial or reject")

    ticket = record["human"]["ticket"]
    write_state(claim_id, "human", HumanSection(ticket=ticket, reviewer=reviewer, verdict=verdict,
                                                note=note.strip(), payout=payout), agent="human_desk")
    with _QUEUE_LOCK:
        queue = _read_queue()
        for t in queue:
            if t["ticket"] == ticket:
                t.update(status="closed", closed=utc_now())
        _write_queue(queue)
    return set_status(claim_id, "closed", agent="human_desk")


# --- Grievance Drafter (should-have S2 — only after all 7 scenarios pass) ----

def list_contestable(state: dict[str, Any]) -> list[dict[str, Any]]:
    """Pick deductions that look wrong against the cited clauses."""
    raise NotImplementedError("S2 — should-have")


def render_letter(template: str, items: list[dict[str, Any]]) -> str:
    """Fill a Jinja letter template with items, amounts and clauses."""
    raise NotImplementedError("S2 — should-have")
