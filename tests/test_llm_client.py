"""M1 LLM path, offline: caps, budget left, fallback and the rules-win cross-check.

No network: every HTTP call goes to an ``httpx.MockTransport``. Test providers read keys from
CL_TEST_KEY_* variables, so a real ``.env`` on the machine can't leak into these tests.
The real-API checks live in ``tests/test_llm_live.py`` (``pytest -m live``).
"""

from __future__ import annotations

import asyncio
import json
import time

import httpx
import pytest

import agents.intake_agent as intake_agent
from tools.config import project_path
from tools.intake_tools import (
    extract_claim_fields,
    llm_extract_claim_fields,
    reconcile_fields,
)
from tools.llm_client import (
    LlmClient,
    LlmUnavailable,
    UsageLedger,
    budget,
    budget_line,
    main,
    parse_json_reply,
)
from tools.logger import read_log
from workflow import run_claim


def provider(name, **caps):
    full = {"requests_per_minute": None, "requests_per_day": None,
            "tokens_per_minute": None, "tokens_per_day": None, **caps}
    return {"name": name, "base_url": f"https://{name}.example/v1", "model": f"{name}-model",
            "key_env": f"CL_TEST_KEY_{name.upper()}", "json_mode": True, "caps": full}


def settings(*providers):
    return {"enabled": True, "timeout_s": 5, "max_tokens": 50, "providers": list(providers)}


class FakeApi:
    """Answers chat completions per host; records every request it gets."""

    def __init__(self, replies=None):
        self.replies = replies or {}     # host -> callable(request) -> httpx.Response
        self.calls: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(request)
        handler = self.replies.get(request.url.host, ok('{"ok": true}'))
        return handler(request)

    def hosts(self):
        return [r.url.host for r in self.calls]


def ok(content, tokens=120, headers=None):
    def handler(request):
        body = {"model": json.loads(request.content)["model"],
                "choices": [{"message": {"role": "assistant", "content": content}}],
                "usage": {"total_tokens": tokens}}
        return httpx.Response(200, json=body, headers=headers or {})
    return handler


def status(code, headers=None):
    return lambda request: httpx.Response(code, text="nope", headers=headers or {})


@pytest.fixture
def keys(monkeypatch):
    monkeypatch.setenv("CL_TEST_KEY_A", "key-a")
    monkeypatch.setenv("CL_TEST_KEY_B", "key-b")


@pytest.fixture
def ledger(tmp_path):
    return UsageLedger(tmp_path / "llm_usage.json")


def client(api, ledger, *providers):
    return LlmClient(settings=settings(*providers), ledger=ledger, transport=httpx.MockTransport(api))


PING = [{"role": "user", "content": "ping"}]


# ---- one call, counted ----

def test_call_is_sent_counted_and_budget_shrinks(keys, ledger):
    api = FakeApi({"a.example": ok('{"ok": true}', tokens=120,
                                   headers={"x-ratelimit-remaining-requests": "999"})})
    c = client(api, ledger, provider("a", requests_per_day=10, tokens_per_day=1000))
    reply = c.chat(PING, json_mode=True)

    assert reply.text == '{"ok": true}' and reply.provider == "a" and reply.tokens == 120
    sent = json.loads(api.calls[0].content)
    assert sent["temperature"] == 0 and sent["model"] == "a-model"
    assert sent["response_format"] == {"type": "json_object"}
    assert api.calls[0].headers["authorization"] == "Bearer key-a"
    assert reply.budget["used"]["requests_per_day"] == 1
    assert reply.budget["left"]["requests_per_day"] == 9
    assert reply.budget["left"]["tokens_per_day"] == 880
    assert reply.budget["provider_reported"] == {"x-ratelimit-remaining-requests": "999"}
    assert budget_line(reply.budget) == "a: 9/10 requests, 880/1,000 tokens left today"


def test_extra_body_is_merged_and_json_mode_respected(keys, ledger):
    api = FakeApi()
    p = {**provider("a"), "json_mode": False, "extra": {"chat_template_kwargs": {"enable_thinking": False}}}
    client(api, ledger, p).chat(PING, json_mode=True)
    sent = json.loads(api.calls[0].content)
    assert sent["chat_template_kwargs"] == {"enable_thinking": False}
    assert "response_format" not in sent          # provider doesn't support JSON mode


# ---- caps: refuse before calling, fall through to the next provider ----

def test_daily_request_cap_stops_calls_and_falls_back(keys, ledger):
    api = FakeApi()
    c = client(api, ledger, provider("a", requests_per_day=1), provider("b"))
    assert c.chat(PING).provider == "a"
    assert c.chat(PING).provider == "b"
    assert api.hosts() == ["a.example", "b.example"]       # second call never reached a


def test_minute_cap(keys, ledger):
    api = FakeApi()
    c = client(api, ledger, provider("a", requests_per_minute=1), provider("b"))
    c.chat(PING)
    assert c.chat(PING).provider == "b"


def test_token_cap_counts_the_call_before_sending(keys, ledger):
    api = FakeApi()
    c = client(api, ledger, provider("a", tokens_per_day=30))   # call needs ~50 (max_tokens) + prompt
    with pytest.raises(LlmUnavailable) as exc:
        c.chat(PING)
    assert api.calls == []
    assert "tokens per day cap would be passed" in exc.value.reasons[0]


def test_every_cap_reached_raises_with_reasons(keys, ledger):
    api = FakeApi()
    c = client(api, ledger, provider("a", requests_per_day=0), provider("b", requests_per_day=0))
    with pytest.raises(LlmUnavailable) as exc:
        c.chat(PING)
    assert api.calls == []
    assert [r.split(":")[0] for r in exc.value.reasons] == ["a", "b"]
    assert all("requests per day cap reached" in r for r in exc.value.reasons)


def test_429_blocks_the_provider_then_falls_back(keys, ledger):
    api = FakeApi({"a.example": status(429, {"retry-after": "120"})})
    c = client(api, ledger, provider("a"), provider("b"))
    assert c.chat(PING).provider == "b"
    assert c.chat(PING).provider == "b"
    assert api.hosts() == ["a.example", "b.example", "b.example"]   # a not retried while blocked
    assert budget(c.providers[0], ledger)["blocked_for_s"] > 100


def test_server_error_and_network_error_fall_back_then_give_up(keys, ledger):
    def boom(request):
        raise httpx.ConnectError("down", request=request)
    api = FakeApi({"a.example": status(500), "b.example": boom})
    c = client(api, ledger, provider("a"), provider("b"))
    with pytest.raises(LlmUnavailable) as exc:
        c.chat(PING)
    assert "HTTP 500" in exc.value.reasons[0] and "network error" in exc.value.reasons[1]
    assert budget(c.providers[1], ledger)["used"]["requests_per_day"] == 1   # attempt still counted


def test_no_key_means_no_call(ledger, monkeypatch):
    monkeypatch.delenv("CL_TEST_KEY_A", raising=False)
    api = FakeApi()
    with pytest.raises(LlmUnavailable) as exc:
        client(api, ledger, provider("a")).chat(PING)
    assert api.calls == [] and "no key" in exc.value.reasons[0]


def test_caps_reset_on_a_new_utc_day(keys, ledger):
    ledger.path.write_text(json.dumps({"a": {"day": "2000-01-01", "requests": 5, "tokens": 999,
                                             "window": [], "provider_reported": {}}}), encoding="utf-8")
    p = client(FakeApi(), ledger, provider("a", requests_per_day=5)).providers[0]
    b = budget(p, ledger)
    assert b["used"]["requests_per_day"] == 0 and b["left"]["requests_per_day"] == 5


def test_minute_window_forgets_old_calls(keys, ledger):
    ledger.record("a", 10, now=time.time() - 120)
    p = client(FakeApi(), ledger, provider("a", requests_per_minute=1)).providers[0]
    assert budget(p, ledger)["left"]["requests_per_minute"] == 1


def test_ledger_persists_between_clients(keys, ledger):
    client(FakeApi(), ledger, provider("a", requests_per_day=3)).chat(PING)
    fresh = client(FakeApi(), UsageLedger(ledger.path), provider("a", requests_per_day=3))
    assert fresh.status()[0]["left"]["requests_per_day"] == 2


def test_status_cli_and_api_show_budget_without_keys(keys, ledger, monkeypatch, capsys):
    import api
    from fastapi.testclient import TestClient

    monkeypatch.setattr("tools.llm_client.llm_settings", lambda: settings(provider("a", requests_per_day=7)))
    monkeypatch.setattr("tools.llm_client.UsageLedger", lambda path=None: ledger)
    assert main([]) == 0
    out = capsys.readouterr().out
    assert "[a]" in out and "7 left of 7" in out and "key-a" not in out

    body = TestClient(api.app).get("/llm/usage").json()
    assert body["providers"][0]["left"]["requests_per_day"] == 7
    assert body["providers"][0]["key_set"] is True and "key-a" not in json.dumps(body)
    assert body["disclaimer"]


# ---- reply parsing ----

def test_parse_json_reply_handles_fences_and_think_blocks():
    assert parse_json_reply('```json\n{"a": 1}\n```') == {"a": 1}
    assert parse_json_reply('<think>hmm {"no": 0}</think>Here: {"a": 2} done') == {"a": 2}
    with pytest.raises(ValueError):
        parse_json_reply("no json here")


# ---- extraction + cross-check ----

CLAIM_1 = (project_path("claims") / "CLM-0001" / "claim.txt").read_text(encoding="utf-8")
LLM_CLAIM_1 = {
    "policy_id": "ASJ-01", "policyholder_id": "PH-1001", "patient": "Ravi Kumar (synthetic)",
    "admit": "2026-09-02", "discharge": "2026-09-05", "diagnosis": "Acute appendicitis",
    "procedure": "laparoscopic appendectomy", "room_type": "twin-sharing room",
    "claimed": "Rs 85,000", "bill_number": "SMH/26/04417", "accident": "false",
}


def test_llm_extract_normalises_the_reply(keys, ledger):
    api = FakeApi({"a.example": ok(json.dumps(LLM_CLAIM_1))})
    result = llm_extract_claim_fields(CLAIM_1, client=client(api, ledger, provider("a")))
    f = result["fields"]
    assert f["claimed"] == 85000 and f["accident"] is False and f["patient"] == "Ravi Kumar"
    assert f["diagnosis"] == "Acute appendicitis; laparoscopic appendectomy"
    assert result["provider"] == "a" and result["budget"]["used"]["requests_per_day"] == 1


def test_llm_extract_bad_json_is_unavailable(keys, ledger):
    api = FakeApi({"a.example": ok("Sorry, I can't help with that.")})
    with pytest.raises(LlmUnavailable):
        llm_extract_claim_fields(CLAIM_1, client=client(api, ledger, provider("a")))


def llm_fields(**changes):
    rules = extract_claim_fields(CLAIM_1)
    return {**rules, **changes}


def test_reconcile_agrees_on_claim_1():
    rules = extract_claim_fields(CLAIM_1)
    merged, report = reconcile_fields(rules, llm_fields(diagnosis="acute appendicitis"))
    assert merged == rules
    assert report["mismatches"] == {} and report["filled"] == []
    assert set(report["agreed"]) == {"policy_id", "policyholder_id", "patient", "admit", "discharge",
                                     "diagnosis", "room_type", "claimed", "bill_number", "accident"}


def test_reconcile_rules_win_every_disagreement():
    rules = extract_claim_fields(CLAIM_1)
    merged, report = reconcile_fields(rules, llm_fields(claimed=95000, policy_id="ASJ-02",
                                                        diagnosis="appendix pain", admit="2026-09-03"))
    assert merged == rules                                   # nothing changed
    assert set(report["mismatches"]) == {"claimed", "policy_id", "diagnosis", "admit"}
    assert report["mismatches"]["claimed"] == {"rules": 85000, "llm": 95000}


def test_reconcile_fills_only_gaps_and_never_money():
    rules = {**extract_claim_fields(CLAIM_1), "room_type": "not stated", "bill_number": None}
    merged, report = reconcile_fields(rules, llm_fields())
    assert merged["room_type"] == "twin-sharing room" and merged["bill_number"] == "SMH/26/04417"
    assert sorted(report["filled"]) == ["bill_number", "room_type"]
    assert merged["claimed"] == rules["claimed"] and merged["policy_id"] == rules["policy_id"]


def test_reconcile_drops_fills_that_fail_validation():
    rules = {**extract_claim_fields(CLAIM_1), "room_type": "not stated", "patient": "not stated"}
    bad = llm_fields(room_type="twin-sharing room", patient="Ravi Kumar", discharge="2026-08-01")
    merged, report = reconcile_fields({**rules, "discharge": None}, bad)
    assert merged["room_type"] == "not stated" and report["filled"] == [] and report["errors"]


# ---- the agent: LLM on, rules still decide ----

@pytest.fixture
def runtime(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAIMLENS_RUNTIME_DIR", str(tmp_path))
    monkeypatch.setenv("CLAIMLENS_LLM", "on")
    return tmp_path


def test_disagreeing_llm_cannot_change_a_verdict(runtime, monkeypatch):
    """Scenario 3 rejects on the waiting period; a wrong LLM diagnosis and amount change nothing."""
    def fake(text):
        rules = extract_claim_fields(text)
        return {"fields": {**rules, "diagnosis": "food poisoning", "claimed": 1},
                "provider": "groq", "model": "test-model", "tokens": 300,
                "budget": {"provider": "groq", "left": {"requests_per_day": 899, "tokens_per_day": 89700,
                                                        "requests_per_minute": 24, "tokens_per_minute": 9700},
                           "caps": {"requests_per_day": 900, "tokens_per_day": 90000,
                                    "requests_per_minute": 25, "tokens_per_minute": 10000}}}
    monkeypatch.setattr(intake_agent, "llm_extract_claim_fields", fake)
    rec = asyncio.run(run_claim("CLM-0003"))
    assert rec["decision"]["verdict"] == "reject" and rec["decision"]["payout"] == 0
    step = next(e for e in read_log("CLM-0003") if e.get("tool") == "reconcile_fields")
    assert set(step["llm"]["mismatches"]) == {"diagnosis", "claimed"}
    assert "rules kept on diagnosis, claimed" in step["summary"]
    assert "899/900 requests" in step["summary"]


def test_llm_unavailable_falls_back_to_rules(runtime, monkeypatch):
    def down(text):
        raise LlmUnavailable("no LLM provider answered — groq: no key", ["groq: no key (GROQ_API_KEY not set)"])
    monkeypatch.setattr(intake_agent, "llm_extract_claim_fields", down)
    rec = asyncio.run(run_claim("CLM-0001"))
    assert rec["decision"]["verdict"] == "approve"
    step = next(e for e in read_log("CLM-0001") if e.get("tool") == "llm_extract_claim_fields")
    assert step["summary"].startswith("rules only") and step["llm_reasons"]


def test_intake_halt_is_decided_before_the_llm(runtime, monkeypatch):
    """Scenario 7: rules halt first; the LLM is never asked."""
    def never(text):
        raise AssertionError("LLM must not be called for a halted claim")
    monkeypatch.setattr(intake_agent, "llm_extract_claim_fields", never)
    rec = asyncio.run(run_claim("CLM-0007"))
    assert rec["halt"] and rec["status"] == "intake"


def test_retired_model_error_says_how_to_fix_it(keys, ledger):
    api = FakeApi({"a.example": status(410)})
    with pytest.raises(LlmUnavailable) as exc:
        client(api, ledger, provider("a")).chat(PING)
    assert "HTTP 410" in exc.value.reasons[0] and "python -m tools.llm_client models" in exc.value.reasons[0]


def test_models_lists_what_the_key_can_use(keys, ledger):
    def listing(request):
        assert request.url.path == "/v1/models" and request.headers["authorization"] == "Bearer key-a"
        return httpx.Response(200, json={"data": [{"id": "z-model"}, {"id": "a-model"}]})
    api = FakeApi({"a.example": listing})
    assert client(api, ledger, provider("a")).models(client(api, ledger, provider("a")).providers[0]) == ["a-model", "z-model"]
    assert budget(client(api, ledger, provider("a")).providers[0], ledger)["used"]["requests_per_day"] == 0  # listing is free
