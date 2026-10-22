"""Setup smoke tests: the scaffold imports cleanly and config.yaml has the agreed values.

These should stay green from day one. Feature tests go in test_tools.py and
test_scenarios.py.
"""

import importlib

import pytest

from tools.config import DISCLAIMER, load_config, project_path

AGENT_MODULES = [
    "agents.intake_agent",
    "agents.policy_agent",
    "agents.fraud_agent",
    "agents.cost_agent",
    "agents.manager_agent",
    "agents.human_desk",
    "agents.grievance_agent",
]

TOOL_MODULES = [
    "tools.intake_tools",
    "tools.retrieval_tools",
    "tools.fraud_tools",
    "tools.cost_tools",
    "tools.decision_tools",
    "tools.state",
    "tools.logger",
    "tools.schemas",
    "workflow",
]


@pytest.mark.parametrize("name", AGENT_MODULES + TOOL_MODULES)
def test_module_imports(name):
    importlib.import_module(name)


@pytest.mark.parametrize("name", AGENT_MODULES)
def test_every_agent_has_at_least_two_tools(name):
    agent = importlib.import_module(name)
    assert len(agent.TOOLS) >= 2, f"{name} must call at least two Python tools"
    assert all(callable(t) for t in agent.TOOLS)


def test_config_starting_values():
    cfg = load_config()
    assert cfg["model"]["temperature"] == 0
    assert cfg["retrieval"] == {"top_k": 5, "min_similarity": 0.45}
    assert cfg["thresholds"]["human_review_amount_inr"] == 200000
    assert cfg["thresholds"]["fraud_escalate_score"] == 60
    assert cfg["thresholds"]["min_confidence"] == 0.6
    assert cfg["thresholds"]["overclaim_margin_pct"] == 10


def test_runtime_folders_exist():
    assert project_path("state_dir").is_dir()
    assert project_path("run_log").parent.is_dir()
    assert project_path("corpus").is_dir()


def test_disclaimer_text():
    assert DISCLAIMER == "Educational prototype — not insurance, legal or medical advice."
