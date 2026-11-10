"""Shared test setup.

Every normal test runs with the LLM path OFF (``CLAIMLENS_LLM=off``), so the suite never makes
a network call or spends API budget — even on a laptop whose ``.env`` holds real keys.
Only tests marked ``live`` (``pytest -m live``) talk to the real providers.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _llm_off_unless_live(request, monkeypatch):
    if request.node.get_closest_marker("live") is None:
        monkeypatch.setenv("CLAIMLENS_LLM", "off")
