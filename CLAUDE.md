# ClaimLens — notes for Claude

Multi-agent RAG health-insurance claim adjudication prototype (CSE476 CA2 Project 2, based on Q1).

## Start of every session
1. Read `context/05-progress.md` first: current week, task statuses, decisions, open questions.
2. Read whichever other brief the task touches: `02-architecture-brief.md` (agents, tools, state), `03-features-and-scope.md` (scope, feature IDs, scenarios, tests), `04-ui-and-stack-brief.md` (libraries, config, UI, conventions), `01-project-brief.md` (goals, deliverables).
3. Confirm where we are (e.g. "Week 2, working on M4") before starting.

## Fixed rules
- All money maths in deterministic Python tools, never the LLM. Money is `int` rupees; rounding only inside `compute_payable`.
- Every agent in its own module in `agents/` with at least two Python tools in `tools/`. Agents never import each other.
- Agents communicate only through the shared claim-state record (`tools/state.py`); each writes only its own section; every write is appended to `logs/run_log.jsonl`.
- Policy and Fraud agents run in parallel; Cost waits for policy limits; the Manager fans in.
- A verdict must cite clause ids that were actually retrieved. Clause ids: `<POLICY_ID>:<section>` or `IRDAI:<list>`.
- Synthetic data only. No secrets in the repo.
- Every user-facing output carries `tools.config.DISCLAIMER`: "Educational prototype — not insurance, legal or medical advice."

## Working conventions
- Use the names from the briefs: file/function names, feature IDs (M1–M15, S1–S6, N1–N4), scenario numbers (1–7).
- Stay in scope; must-haves first. Should-haves only once all seven scenarios pass.
- Thresholds and paths come from `config.yaml` via `tools.config.load_config()`.
- Run `pytest` before committing.
- At the end of a working session, update `context/05-progress.md` (statuses, decisions, open questions, dated session-log entry, newest first).
