"""LIVE check: can each LLM provider take a call and actually answer?

Makes real API calls (a few hundred tokens each) and counts them in the usage ledger, so the
caps in config.yaml still hold. Never runs by default; run on purpose with:

    pytest -m live -s          # -s prints what each provider answered and the budget left

A provider with no key in .env is skipped, not failed.
"""

from __future__ import annotations

import pytest

from tools.config import project_path
from tools.intake_tools import extract_claim_fields, llm_extract_claim_fields
from tools.llm_client import LlmClient, LlmUnavailable, budget_line, llm_settings, parse_json_reply

pytestmark = pytest.mark.live
PROVIDERS = [p["name"] for p in llm_settings().get("providers", [])]


def only(name: str) -> LlmClient:
    c = LlmClient(only=[name])
    if not c.configured():
        pytest.skip(f"{name}: no key — set {c.providers[0].key_env} in .env")
    return c


@pytest.mark.parametrize("name", PROVIDERS)
def test_provider_answers(name):
    c = only(name)
    try:
        reply = c.chat([{"role": "user", "content": 'Reply with exactly this JSON and nothing else: {"ok": true}'}],
                       json_mode=True, max_tokens=20)
    except LlmUnavailable as exc:
        pytest.fail(f"{name} did not answer: {'; '.join(exc.reasons)}")
    print(f"\n{name} ({reply.model}) answered {reply.text!r} using {reply.tokens} tokens")
    print("  " + budget_line(reply.budget))
    assert reply.provider == name
    assert parse_json_reply(reply.text) == {"ok": True}


@pytest.mark.parametrize("name", PROVIDERS)
def test_provider_reads_claim_1_like_the_rules(name):
    c = only(name)
    text = (project_path("claims") / "CLM-0001" / "claim.txt").read_text(encoding="utf-8")
    try:
        result = llm_extract_claim_fields(text, client=c)
    except LlmUnavailable as exc:
        pytest.fail(f"{name} did not extract: {'; '.join(exc.reasons)}")
    rules, got = extract_claim_fields(text), result["fields"]
    print(f"\n{name} ({result['model']}) read: {got}")
    print("  " + budget_line(result["budget"]))
    for key in ("policy_id", "admit", "discharge", "claimed", "bill_number"):
        assert str(got[key]) == str(rules[key]), f"{name} read {key}={got[key]!r}, rules say {rules[key]!r}"
