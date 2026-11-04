"""Server-mode API (DevOps pipeline S1): health, version and the claim-run route.

The run route is tested with a fake workflow so these stay green while
``workflow.run_claim`` is still a stub.
"""

import pytest
from fastapi.testclient import TestClient

import api
from tools.config import DISCLAIMER

client = TestClient(api.app)


@pytest.fixture
def claims_dir(tmp_path, monkeypatch):
    (tmp_path / "CLM-0001").mkdir()
    monkeypatch.setattr(api, "project_path", lambda key: tmp_path)
    return tmp_path


def test_healthz():
    res = client.get("/healthz")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_version_carries_disclaimer():
    body = client.get("/version").json()
    assert body["version"] == api.APP_VERSION
    assert body["disclaimer"] == DISCLAIMER


def test_run_rejects_malformed_claim_id():
    res = client.post("/claims/CLM-1/run")
    assert res.status_code == 400
    assert res.json()["detail"]["disclaimer"] == DISCLAIMER


def test_run_unknown_claim_is_404(claims_dir):
    assert client.post("/claims/CLM-9999/run").status_code == 404


def test_run_returns_record_with_disclaimer(claims_dir, monkeypatch):
    async def fake_run_claim(claim_id):
        return {"claim_id": claim_id, "status": "closed"}

    monkeypatch.setattr(api, "run_claim", fake_run_claim)
    res = client.post("/claims/CLM-0001/run")
    assert res.status_code == 200
    assert res.json() == {"claim_id": "CLM-0001", "status": "closed", "disclaimer": DISCLAIMER}


def test_run_is_501_while_workflow_is_a_stub(claims_dir, monkeypatch):
    async def stub(claim_id):
        raise NotImplementedError("M7")

    monkeypatch.setattr(api, "run_claim", stub)
    assert client.post("/claims/CLM-0001/run").status_code == 501
