"""ClaimLens HTTP API — server mode, so the app can be deployed and monitored.

DevOps pipeline Stage 1 (DEVOPS_PIPELINE_TEMPLATE.md, INT333), not a CSE476
feature: it only wraps ``workflow.run_claim``. Settings come from environment
variables and logs go to stdout, so the same build runs everywhere.

    GET  /healthz                 -> {"status": "ok"}
    GET  /version                 -> {"version": "v1.0.0", ...}
    POST /claims/{claim_id}/run   -> final claim-state record (501 until M7 is built)

Run locally: ``python api.py`` (PORT=8000, HOST=0.0.0.0 by default).
"""

from __future__ import annotations

import os
import re
from typing import Any

from fastapi import FastAPI, HTTPException

from tools.config import DISCLAIMER, project_path
from workflow import run_claim

APP_VERSION: str = os.environ.get("APP_VERSION", "dev")

# Claim ids are folder names under data/claims/, so only this exact shape is accepted.
CLAIM_ID = re.compile(r"^CLM-\d{4}$")

app = FastAPI(title="ClaimLens", version=APP_VERSION, description=DISCLAIMER)


def _error(status: int, message: str) -> HTTPException:
    return HTTPException(status, {"error": message, "disclaimer": DISCLAIMER})


@app.get("/healthz")
def healthz() -> dict[str, str]:
    """Liveness for the load balancer, Ansible and Nagios."""
    return {"status": "ok"}


@app.get("/version")
def version() -> dict[str, str]:
    """Deployed version (set by Ansible from the release tag)."""
    return {"app": "claimlens", "version": APP_VERSION, "disclaimer": DISCLAIMER}


@app.post("/claims/{claim_id}/run")
async def run(claim_id: str) -> dict[str, Any]:
    """Run one claim end to end and return its final claim-state record."""
    if not CLAIM_ID.match(claim_id):
        raise _error(400, "claim_id must look like CLM-0001")
    if not (project_path("claims") / claim_id).is_dir():
        raise _error(404, f"unknown claim {claim_id}")
    try:
        record = await run_claim(claim_id)
    except NotImplementedError as exc:
        raise _error(501, f"not built yet: {exc}") from exc
    return {**record, "disclaimer": DISCLAIMER}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "8000")),
    )
