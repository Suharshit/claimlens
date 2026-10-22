# ClaimLens

> **Educational prototype — not insurance, legal or medical advice.**

ClaimLens reads a health-insurance claim and its hospital bill, checks both against the policy wording and IRDAI rules, and returns one of four verdicts — approve, partial approve, reject or escalate — with the payout and the clause behind every rupee deducted.

CSE476 CA2 Project 2 (based on Q1). Multi-agent RAG with a fan-out / fan-in pattern and human routing. Synthetic data only.

*This is the working README for the team. The submission README (≤ 2 pages: agent roster, architecture and why, tools per agent, memory/retrieval, one honest failure) replaces it in Week 4.*

## Project context

Read these before working — they are the source of truth:

| File | What it covers |
| --- | --- |
| [`context/01-project-brief.md`](context/01-project-brief.md) | Problem, pitch, Q1 mapping, deliverables, viva points |
| [`context/02-architecture-brief.md`](context/02-architecture-brief.md) | Agents, tools, claim-state record, escalation, repo layout |
| [`context/03-features-and-scope.md`](context/03-features-and-scope.md) | Feature IDs M1–M15, S1–S6, N1–N4 and scenarios 1–7 |
| [`context/04-ui-and-stack-brief.md`](context/04-ui-and-stack-brief.md) | Stack, config, notebook, Streamlit, coding conventions |
| [`context/05-progress.md`](context/05-progress.md) | Current week, task tracker, decisions, open questions, session log |

## Setup (Windows, Python 3.11)

```powershell
git clone https://github.com/Suharshit/claimlens.git
cd claimlens
py -3.11 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env      # then add your model API key
pytest                      # smoke tests should pass
```

macOS/Linux: `python3.11 -m venv .venv && source .venv/bin/activate`, `cp .env.example .env`.

## Layout

```
agents/      one module per agent (intake, policy, fraud, cost, manager, human_desk, grievance)
tools/       deterministic Python tools + state.py, logger.py, schemas.py, config.py
workflow.py  fan-out / fan-in orchestration and human routing
config.yaml  thresholds, retrieval top-k, paths
data/        corpus/ (RAG), policies.json, prior_claims.json, claims/  — see data/README.md
state/       one JSON record per claim (generated)
logs/        run_log.jsonl, append-only (generated)
tests/       test_smoke.py, test_tools.py, test_scenarios.py
context/     the five project briefs
```

Every agent and tool is a stub with the agreed function name, docstring and owner/week; it raises `NotImplementedError` until built.

## Week 1 — done when one claim flows intake → state file → log

| Member | Start here |
| --- | --- |
| A | `tools/schemas.py` (Pydantic models), `parse_bill` in `tools/intake_tools.py`, 7 scenario claims in `data/claims/` |
| B | Wordings into `data/corpus/`, `chunk_wording` + `build_index` in `tools/retrieval_tools.py` |
| C | `read_state` / `write_state` in `tools/state.py`, `append_log` in `tools/logger.py`, `data/policies.json`, `data/prior_claims.json` |

## Ground rules

- All money maths in deterministic Python tools (`tools/cost_tools.py`), never the LLM. Money is `int` rupees; rounding only in `compute_payable`.
- Every agent in its own module with at least two Python tools; agents never import each other.
- Agents talk only through the shared claim-state record (`state/<claim_id>.json`).
- Policy and Fraud agents run in parallel; Cost waits for policy limits.
- A verdict must cite clause ids that were actually retrieved (citation guard).
- Synthetic data only. No secrets in the repo — keys go in `.env`.
