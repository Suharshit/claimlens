"""ClaimLens HTTP API — server mode and the demo website.

DevOps pipeline Stage 1 (DEVOPS_PIPELINE_TEMPLATE.md, INT333) and the CSE476 demo UI (S4).
It only wraps ``workflow.run_claim`` and reads the claim-state record and run log; no agent
logic lives here. Settings come from environment variables and logs go to stdout, so the
same build runs on a laptop and on the AWS servers.

    GET  /                          -> demo website (web/index.html)
    GET  /healthz                   -> {"status": "ok"}
    GET  /version                   -> {"version": "v1.0.0", ...}
    POST /claims/{claim_id}/run     -> run one claim end to end; final claim-state record
    GET  /api/claims                -> every demo claim with its scenario, expected and current outcome
    GET  /api/claims/{claim_id}     -> claim text, bill, expected outcome, record, last run's trace
    POST /api/claims/{claim_id}/review -> Human Review Desk verdict (approve / partial / reject)
    GET  /api/clauses/{clause_id}   -> one clause's text from the corpus
    GET  /llm/usage                 -> LLM budget left per provider (no API call, no keys shown)

Run locally: ``python api.py`` then open http://localhost:8000 (PORT, HOST env vars).
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from tools.config import DISCLAIMER, PROJECT_ROOT, project_path
from workflow import run_claim, summary

APP_VERSION: str = os.environ.get("APP_VERSION", "dev")

# Claim ids are folder names under data/claims/, so only this exact shape is accepted.
CLAIM_ID = re.compile(r"^CLM-\d{4}$")
CLAUSE_ID = re.compile(r"^[A-Z][A-Z0-9-]*:[A-Za-z0-9.\-]+$")
WEB_DIR = PROJECT_ROOT / "web"

# The seven scenarios from 03-features-and-scope (titles shown in the claim list).
SCENARIOS = {
    1: "Clean approval",
    2: "Partial: room-rent breach",
    3: "Reject: waiting period",
    4: "High value → human",
    5: "Fraud signal",
    6: "Honest failure: no grounding",
    7: "Missing data",
}

app = FastAPI(title="ClaimLens", version=APP_VERSION, description=DISCLAIMER)


def _error(status: int, message: str) -> HTTPException:
    return HTTPException(status, {"error": message, "disclaimer": DISCLAIMER})


def _claim_dir(claim_id: str) -> Path:
    if not CLAIM_ID.match(claim_id):
        raise _error(400, "claim_id must look like CLM-0001")
    folder = project_path("claims") / claim_id
    if not folder.is_dir():
        raise _error(404, f"unknown claim {claim_id}")
    return folder


def _record(claim_id: str) -> dict[str, Any] | None:
    from tools.state import read_state

    try:
        return read_state(claim_id)
    except FileNotFoundError:
        return None


def _expected(folder: Path) -> dict[str, Any] | None:
    path = folder / "expected.json"
    if not path.is_file():
        return None
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw.pop("working", None)   # the hand calculation is long; the page shows the outcome
    return raw


def _last_run_trace(claim_id: str) -> list[dict[str, Any]]:
    """Run-log events of this claim's latest run (the log is append-only and keeps every run)."""
    from tools.logger import read_log

    events = read_log(claim_id)
    starts = [i for i, e in enumerate(events) if e.get("tool") == "reset_state"]
    return events[starts[-1]:] if starts else events


# ---------------------------------------------------------------- health / version

@app.get("/healthz")
def healthz() -> dict[str, str]:
    """Liveness for the load balancer, Ansible and Nagios."""
    return {"status": "ok"}


@app.get("/version")
def version() -> dict[str, str]:
    """Deployed version (set by Ansible from the release tag)."""
    return {"app": "claimlens", "version": APP_VERSION, "disclaimer": DISCLAIMER}


@app.get("/llm/usage")
def llm_usage() -> dict[str, Any]:
    """How much of each provider's daily/minute cap is left (from the usage ledger)."""
    from tools.llm_client import LlmClient, llm_enabled

    return {"llm_enabled": llm_enabled(), "providers": LlmClient().status(), "disclaimer": DISCLAIMER}


# ---------------------------------------------------------------- run

@app.post("/claims/{claim_id}/run")
async def run(claim_id: str) -> dict[str, Any]:
    """Run one claim end to end and return its final claim-state record."""
    _claim_dir(claim_id)
    try:
        record = await run_claim(claim_id)
    except NotImplementedError as exc:
        raise _error(501, f"not built yet: {exc}") from exc
    return {**record, "disclaimer": DISCLAIMER}


# ---------------------------------------------------------------- demo website (S4)

@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html", media_type="text/html")


@app.get("/architecture.png", include_in_schema=False)
def architecture() -> FileResponse:
    return FileResponse(PROJECT_ROOT / "architecture.png", media_type="image/png")


@app.get("/api/claims")
def list_claims() -> dict[str, Any]:
    """Every claim folder, with its scenario, the hand-worked expected outcome and the current one."""
    claims = []
    for folder in sorted(p for p in project_path("claims").iterdir() if p.is_dir() and CLAIM_ID.match(p.name)):
        exp = _expected(folder) or {}
        rec = _record(folder.name)
        number = exp.get("scenario")
        claims.append({
            "claim_id": folder.name,
            "scenario": number,
            "title": SCENARIOS.get(number, folder.name),
            "expected": {k: exp.get(k) for k in ("verdict", "payable", "claimed", "final_status", "halt",
                                                  "escalation_reasons", "human_verdict")},
            "current": summary(rec) if rec else None,
        })
    return {"claims": claims, "disclaimer": DISCLAIMER}


@app.get("/api/claims/{claim_id}")
def claim_detail(claim_id: str) -> dict[str, Any]:
    """What the page shows for one claim: input, expected outcome, record and the last run's trace."""
    from tools.intake_tools import IntakeHalt, parse_bill

    folder = _claim_dir(claim_id)
    text_path = folder / "claim.txt"
    bill_path = next((folder / n for n in ("bill.csv", "bill.json") if (folder / n).exists()), None)
    bill, bill_error = None, None
    if bill_path is not None:
        try:
            bill = parse_bill(bill_path)
        except IntakeHalt as exc:
            bill_error = str(exc)
    rec = _record(claim_id)
    return {
        "claim_id": claim_id,
        "claim_text": text_path.read_text(encoding="utf-8") if text_path.is_file() else "",
        "bill": bill,
        "bill_error": bill_error if bill_path else "no bill attached",
        "expected": _expected(folder),
        "record": rec,
        "summary": summary(rec) if rec else None,
        "trace": _last_run_trace(claim_id) if rec else [],
        "disclaimer": DISCLAIMER,
    }


class ReviewIn(BaseModel):
    verdict: str = Field(pattern="^(approve|partial|reject)$")
    note: str = Field(min_length=1, max_length=500)
    reviewer: str = Field(default="Demo Reviewer", min_length=1, max_length=80)
    payout: int | None = Field(default=None, ge=0)


@app.post("/api/claims/{claim_id}/review")
def review(claim_id: str, body: ReviewIn) -> dict[str, Any]:
    """Human Review Desk: write the reviewer's verdict back and close the claim (M11)."""
    from agents import human_desk

    _claim_dir(claim_id)
    try:
        record = human_desk.review(claim_id, body.verdict, body.note, reviewer=body.reviewer, payout=body.payout)
    except (ValueError, FileNotFoundError) as exc:
        raise _error(409, str(exc)) from exc
    return {**record, "disclaimer": DISCLAIMER}


@app.get("/api/clauses/{clause_id}")
def clause(clause_id: str) -> dict[str, Any]:
    """The text of one corpus clause, so a cited id can be read on the page."""
    from tools.retrieval_tools import load_chunks

    if not CLAUSE_ID.match(clause_id):
        raise _error(400, "clause id must look like ASJ-01:4.1.i or IRDAI:List-I")
    for chunk in load_chunks():
        if chunk.get("clause_id") == clause_id:
            return {"clause_id": clause_id, "title": chunk.get("title"), "text": chunk.get("text", ""),
                    "disclaimer": DISCLAIMER}
    raise _error(404, f"clause {clause_id} is not in the corpus")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "8000")),
    )
