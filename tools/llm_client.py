"""LLM access for ClaimLens (M1): free open-weight models behind OpenAI-compatible APIs.

Only the Intake Agent uses this, to read the claim message. The LLM never touches money:
amounts come from ``parse_bill`` and all rupee maths stays in ``tools/cost_tools.py``.

Providers are tried in the order listed under ``llm.providers`` in config.yaml (Groq first,
then NVIDIA build / Nemotron). Each provider has self-imposed caps kept *below* its free-tier
limits; every call is counted in a usage ledger (config ``paths.llm_usage``) so the caps hold
across runs and the remaining budget can be shown:

    python -m tools.llm_client          # budget left per provider (no API call)
    python -m tools.llm_client ping     # one tiny real call per provider with a key
    python -m tools.llm_client models   # chat models each key can use now (after a 404/410)

Keys come from the environment or ``.env`` (never config.yaml, never the repo).
Set ``CLAIMLENS_LLM=off`` to force the rule-based path (the test suite does this).
"""

from __future__ import annotations

import json
import os
import re
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from tools.config import DISCLAIMER, PROJECT_ROOT, load_config, project_path

_LOCK = threading.Lock()
_THINK = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


class LlmUnavailable(RuntimeError):
    """No provider could answer: LLM off, no key, every cap reached, or every call failed.

    ``reasons`` lists one line per provider tried. The caller falls back to the rules.
    """

    def __init__(self, message: str, reasons: list[str] | None = None):
        super().__init__(message)
        self.reasons = reasons or []


@dataclass(frozen=True)
class Provider:
    """One entry of ``llm.providers`` in config.yaml."""
    name: str
    base_url: str
    model: str
    key_env: str
    json_mode: bool = False
    caps: dict[str, int | None] = field(default_factory=dict)   # requests/tokens per minute/day
    extra: dict[str, Any] = field(default_factory=dict)         # merged into the request body

    @classmethod
    def from_config(cls, raw: dict[str, Any]) -> Provider:
        return cls(name=raw["name"], base_url=raw["base_url"].rstrip("/"), model=raw["model"],
                   key_env=raw["key_env"], json_mode=bool(raw.get("json_mode", False)),
                   caps=dict(raw.get("caps") or {}), extra=dict(raw.get("extra") or {}))


@dataclass
class LlmReply:
    """A successful answer: the text plus who answered and what budget is left."""
    text: str
    provider: str
    model: str
    tokens: int
    budget: dict[str, Any]


def llm_settings() -> dict[str, Any]:
    return load_config().get("llm") or {}


def llm_enabled() -> bool:
    """LLM path on? ``llm.enabled`` in config, overridden off by ``CLAIMLENS_LLM=off``."""
    if os.environ.get("CLAIMLENS_LLM", "").strip().lower() in {"off", "0", "false", "no"}:
        return False
    return bool(llm_settings().get("enabled", False))


def load_env_file() -> None:
    """Read keys from ``<repo>/.env`` without overriding variables already set."""
    try:
        from dotenv import load_dotenv
    except ImportError:   # python-dotenv is in both requirements files; stay usable without it
        return
    load_dotenv(PROJECT_ROOT / ".env", override=False)


def _today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


# ---------------------------------------------------------------- usage ledger

class UsageLedger:
    """Counts requests and tokens per provider per UTC day (plus a rolling 60-second window).

    Stored as JSON (git-ignored under ``state/``). Writes are atomic and locked, so the
    caps hold across runs of the notebook, the tests and the API in one process.
    """

    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else project_path("llm_usage")

    def _load(self) -> dict[str, Any]:
        if not self.path.is_file():
            return {}
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}   # a corrupt ledger must not stop intake; it restarts the count

    def _save(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
        os.replace(tmp, self.path)

    @staticmethod
    def _entry(data: dict[str, Any], name: str, now: float) -> dict[str, Any]:
        e = data.setdefault(name, {})
        if e.get("day") != _today():          # new UTC day: daily counters reset
            e.update(day=_today(), requests=0, tokens=0, blocked_until=None)
        e["window"] = [w for w in e.get("window", []) if now - w[0] < 60]
        e.setdefault("provider_reported", {})
        return e

    def snapshot(self, name: str, now: float | None = None) -> dict[str, Any]:
        now = time.time() if now is None else now
        with _LOCK:
            return dict(self._entry(self._load(), name, now))

    def record(self, name: str, tokens: int, headers: dict[str, str] | None = None,
               now: float | None = None) -> None:
        now = time.time() if now is None else now
        with _LOCK:
            data = self._load()
            e = self._entry(data, name, now)
            e["requests"] += 1
            e["tokens"] += tokens
            e["window"].append([now, tokens])
            e["last_call"] = datetime.fromtimestamp(now, timezone.utc).isoformat(timespec="seconds")
            if headers:
                e["provider_reported"] = headers
            self._save(data)

    def block(self, name: str, seconds: float, now: float | None = None) -> None:
        """Provider said 429: don't call it again until ``seconds`` have passed."""
        now = time.time() if now is None else now
        with _LOCK:
            data = self._load()
            self._entry(data, name, now)["blocked_until"] = now + seconds
            self._save(data)


def budget(provider: Provider, ledger: UsageLedger, now: float | None = None) -> dict[str, Any]:
    """What's used and what's left under this provider's caps (``None`` cap = not capped)."""
    now = time.time() if now is None else now
    e = ledger.snapshot(provider.name, now)
    used = {
        "requests_per_day": e["requests"],
        "tokens_per_day": e["tokens"],
        "requests_per_minute": len(e["window"]),
        "tokens_per_minute": sum(t for _, t in e["window"]),
    }
    left = {k: (None if provider.caps.get(k) is None else max(0, provider.caps[k] - v))
            for k, v in used.items()}
    blocked = e.get("blocked_until")
    return {"provider": provider.name, "model": provider.model, "day": e["day"],
            "used": used, "caps": {k: provider.caps.get(k) for k in used}, "left": left,
            "blocked_for_s": max(0, round(blocked - now)) if blocked and blocked > now else 0,
            "provider_reported": e.get("provider_reported", {})}


def _check_caps(provider: Provider, b: dict[str, Any], est_tokens: int) -> str | None:
    """Why this call must not go out, or ``None`` if it fits under every cap."""
    if b["blocked_for_s"]:
        return f"rate-limited by the provider, retry in {b['blocked_for_s']} s"
    left = b["left"]
    for key in ("requests_per_day", "requests_per_minute"):
        if left[key] is not None and left[key] < 1:
            return f"{key.replace('_', ' ')} cap reached ({b['caps'][key]})"
    for key in ("tokens_per_day", "tokens_per_minute"):
        if left[key] is not None and left[key] < est_tokens:
            return f"{key.replace('_', ' ')} cap would be passed ({left[key]} left, call needs ~{est_tokens})"
    return None


def budget_line(b: dict[str, Any]) -> str:
    """One readable line, e.g. ``groq: 897/900 requests, 87,900/90,000 tokens left today``."""
    parts = []
    for key, label in (("requests_per_day", "requests"), ("tokens_per_day", "tokens")):
        cap = b["caps"][key]
        if cap is not None:
            parts.append(f"{b['left'][key]:,}/{cap:,} {label}")
    return f"{b['provider']}: " + (", ".join(parts) + " left today" if parts else "no daily cap set")


# ---------------------------------------------------------------- client

class LlmClient:
    """Chat-completions client over the configured providers, with caps and fallback.

    ``only`` limits it to named providers (the live tests check each one alone);
    ``transport`` lets the offline tests plug in an ``httpx.MockTransport``.
    """

    def __init__(self, *, only: list[str] | None = None, ledger: UsageLedger | None = None,
                 transport: httpx.BaseTransport | None = None, settings: dict[str, Any] | None = None):
        load_env_file()
        self.settings = settings if settings is not None else llm_settings()
        providers = [Provider.from_config(p) for p in self.settings.get("providers", [])]
        self.providers = [p for p in providers if not only or p.name in only]
        self.ledger = ledger or UsageLedger()
        self.transport = transport

    def key(self, provider: Provider) -> str | None:
        value = os.environ.get(provider.key_env, "").strip()
        return value or None

    def configured(self) -> list[Provider]:
        """Providers whose API key is set."""
        return [p for p in self.providers if self.key(p)]

    def models(self, provider: Provider) -> list[str]:
        """Model ids the provider lists for this key (``GET /models``; not counted, it's free)."""
        key = self.key(provider)
        if not key:
            raise LlmUnavailable(f"{provider.name}: no key ({provider.key_env} not set)")
        with httpx.Client(transport=self.transport, timeout=float(self.settings.get("timeout_s", 30))) as http:
            resp = http.get(f"{provider.base_url}/models", headers={"Authorization": f"Bearer {key}"})
        resp.raise_for_status()
        return sorted(m["id"] for m in resp.json().get("data", []))

    def status(self) -> list[dict[str, Any]]:
        """Budget for every configured provider (no API call)."""
        return [{**budget(p, self.ledger), "key_set": self.key(p) is not None} for p in self.providers]

    def chat(self, messages: list[dict[str, str]], *, json_mode: bool = False,
             max_tokens: int | None = None) -> LlmReply:
        """Send one chat request to the first provider that has a key and budget left."""
        max_tokens = max_tokens or int(self.settings.get("max_tokens", 400))
        est = sum(len(m["content"]) for m in messages) // 4 + max_tokens   # rough, errs high
        reasons: list[str] = []
        for p in self.providers:
            key = self.key(p)
            if not key:
                reasons.append(f"{p.name}: no key ({p.key_env} not set)")
                continue
            why = _check_caps(p, budget(p, self.ledger), est)
            if why:
                reasons.append(f"{p.name}: {why}")
                continue
            try:
                return self._call(p, key, messages, json_mode=json_mode and p.json_mode,
                                  max_tokens=max_tokens, est=est)
            except _ProviderError as exc:
                reasons.append(f"{p.name}: {exc}")
        if not self.providers:
            reasons.append("no providers under llm.providers in config.yaml")
        raise LlmUnavailable("no LLM provider answered — " + "; ".join(reasons), reasons)

    def _call(self, p: Provider, key: str, messages: list[dict[str, str]], *, json_mode: bool,
              max_tokens: int, est: int) -> LlmReply:
        body: dict[str, Any] = {"model": p.model, "messages": messages, "max_tokens": max_tokens,
                                "temperature": load_config().get("model", {}).get("temperature", 0),
                                **p.extra}
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        timeout = float(self.settings.get("timeout_s", 30))
        try:
            with httpx.Client(transport=self.transport, timeout=timeout) as http:
                resp = http.post(f"{p.base_url}/chat/completions", json=body,
                                 headers={"Authorization": f"Bearer {key}"})
        except httpx.HTTPError as exc:
            # The request may have reached the provider, so it counts against our caps.
            self.ledger.record(p.name, est)
            raise _ProviderError(f"network error: {type(exc).__name__}") from exc

        headers = {k.lower(): v for k, v in resp.headers.items() if k.lower().startswith("x-ratelimit")}
        if resp.status_code == 429:
            self.ledger.record(p.name, 0, headers)
            wait = _retry_after(resp.headers.get("retry-after"))
            self.ledger.block(p.name, wait)
            raise _ProviderError(f"HTTP 429 rate limit, blocked for {round(wait)} s")
        if resp.status_code >= 400:
            self.ledger.record(p.name, 0, headers)
            hint = ""
            if resp.status_code in (404, 410):
                hint = (f" — model {p.model!r} retired or not on this key; "
                        "run `python -m tools.llm_client models` and update config.yaml")
            raise _ProviderError(f"HTTP {resp.status_code}{hint}: {resp.text[:160]}")
        try:
            data = resp.json()
            text = data["choices"][0]["message"].get("content") or ""
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            self.ledger.record(p.name, est, headers)
            raise _ProviderError("response was not a chat completion") from exc
        tokens = int((data.get("usage") or {}).get("total_tokens") or est)
        self.ledger.record(p.name, tokens, headers)
        return LlmReply(text=_THINK.sub("", text).strip(), provider=p.name,
                        model=data.get("model") or p.model, tokens=tokens, budget=budget(p, self.ledger))


class _ProviderError(Exception):
    """One provider failed; the client moves on to the next."""


def _retry_after(raw: str | None) -> float:
    try:
        return max(1.0, float(raw)) if raw else 60.0
    except ValueError:
        return 60.0


def parse_json_reply(text: str) -> dict[str, Any]:
    """The first JSON object in a reply (models sometimes wrap it in prose or ``` fences)."""
    text = _THINK.sub("", text)
    start = text.find("{")
    if start < 0:
        raise ValueError("no JSON object in the reply")
    obj, _ = json.JSONDecoder().raw_decode(text[start:])
    if not isinstance(obj, dict):
        raise ValueError("reply JSON is not an object")
    return obj


# ---------------------------------------------------------------- CLI

def _print_status(client: LlmClient) -> None:
    print(f"LLM path: {'on' if llm_enabled() else 'off'} · ledger: {client.ledger.path}")
    for b in client.status():
        print(f"\n[{b['provider']}] model {b['model']} · key {'set' if b['key_set'] else 'NOT set'} · day {b['day']} (UTC)")
        for k in b["used"]:
            cap = b["caps"][k]
            cap_txt = "no cap" if cap is None else f"{b['left'][k]:,} left of {cap:,}"
            print(f"  {k:<20} used {b['used'][k]:>7,}   {cap_txt}")
        if b["blocked_for_s"]:
            print(f"  blocked by provider for {b['blocked_for_s']} s")
        if b["provider_reported"]:
            print("  provider says: " + ", ".join(f"{k}={v}" for k, v in b["provider_reported"].items()))
    print(f"\n{DISCLAIMER}")


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    client = LlmClient()
    if args[:1] == ["models"]:
        skip = ("embed", "guard", "whisper", "orpheus", "reward", "parse", "safety", "retriever", "vision", "vl")
        for p in client.providers:
            try:
                ids = [m for m in client.models(p) if not any(s in m.lower() for s in skip)]
            except (LlmUnavailable, httpx.HTTPError) as exc:
                print(f"{p.name}: could not list models — {exc}")
                continue
            print(f"\n[{p.name}] configured: {p.model}" + ("" if p.model in ids else "   ← NOT in the list"))
            for m in ids:
                print(f"  {'*' if m == p.model else ' '} {m}")
        return 0
    if args[:1] == ["ping"]:
        code = 0
        for p in client.configured() or client.providers:
            try:
                reply = LlmClient(only=[p.name], ledger=client.ledger).chat(
                    [{"role": "user", "content": 'Reply with exactly this JSON: {"ok": true}'}],
                    json_mode=True, max_tokens=20)
                print(f"{p.name}: OK ({reply.model}, {reply.tokens} tokens) → {reply.text[:60]!r}")
                print("  " + budget_line(reply.budget))
            except LlmUnavailable as exc:
                code = 1
                print(f"{p.name}: FAILED — {'; '.join(exc.reasons)}")
        return code
    _print_status(client)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
