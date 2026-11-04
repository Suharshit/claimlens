# ClaimLens — 05 Progress

This is the single source of truth for where the project stands. Read it at the start of every chat. Update it at the end of every working session: change task statuses, add a session-log entry (newest first), and record any decision or open question.

## Current status
- **Phase:** Week 1 tasks — build starting (calendar: end of Week 2, about two weeks behind plan)
- **Current week:** Week 2 by calendar; Week 1 tasks still to do
- **Last updated:** 2026-11-04
- **Next action:** Push `devops-pipeline`, open the PR, get `ci` green and merge. Then the Week 1 tasks: `tools/state.py` + `tools/logger.py` (M12, M13), `tools/schemas.py` fields, `policies.json` (ASJ-01), `parse_bill`, scenario 1–2 claims. Settle the framework question before Week 2 agent work.

## Decisions made

| Date | Decision | Why |
| --- | --- | --- |
| 2026-11-04 | Solo project: Suharshit owns every Member A/B/C task | No teammates; the A/B/C split stays only as a way to group tasks |
| 2026-11-04 | Every piece of work is committed and pushed through a branch + PR to `main`, so the `ci` pipeline checks it | Keeps the DevOps pipeline (INT333) exercised on real changes |
| 2026-11-04 | Text files in the repo must be UTF-8 (a Windows-1252 dash in `requirements.txt` was replaced) | pip on the Linux CI runner reads requirements files as UTF-8 |
| 2026-10-22 | DevOps pipeline (INT333) built from `DEVOPS_PIPELINE_TEMPLATE.md` on branch `devops-pipeline`; all answers in `pipeline.config.yml`; runbook in `infra/README.md` | Separate course deliverable; it deploys whatever `main` holds and adds no CSE476 feature |
| 2026-10-22 | Pipeline choices: FastAPI server mode (`api.py`, port 8000, `/healthz`), source tarball artifact, AWS ap-south-1 (2 app + LB + ops), local Terraform state + workspaces, Puppet owns config, every stage but S12 | Owner calls S0–S11; Vagrant ruled out because the PC has 7.3 GB RAM |
| 2026-10-22 | Servers install the lean `requirements-server.txt` (no PyTorch/Chroma/Jupyter/Streamlit) | 1 GB t3.micro app servers; PyTorch alone needs more than that |
| 2026-10-22 | `config.yaml` gains `paths.claims: data/claims`; `ruff.toml` pins lint rules; `fastapi`, `uvicorn`, `httpx`, `ruff` added to `requirements.txt` | API looks claims up via `project_path`; CI and laptops lint the same way |
| 2026-10-22 | Repo: github.com/Suharshit/claimlens, branch `main`; scaffold follows the 02 layout with every agent/tool as a named stub | Everyone starts from the agreed names and signatures |
| 2026-10-22 | `context/` in the repo mirrors the five project files; update `context/05-progress.md` alongside the project copy each session | Briefs travel with the code |
| 2026-10-22 | Small additions to the 02 layout: `tools/schemas.py` (Pydantic models), `tools/config.py` (`load_config`, `project_path`, `DISCLAIMER`); Human Desk + Grievance tools live in `tools/decision_tools.py`; corpus builders `chunk_wording` / `build_index` in `tools/retrieval_tools.py` | 02 named no home for these |
| 2026-10-22 | `verify_citations(clause_ids, retrieved_ids)` takes the retrieved set as a second argument | Keeps the citation guard a pure, unit-testable function |
| 2026-10-22 | Framework left unpinned in `requirements.txt` (both options commented) until the open question is settled | Week 1 tasks don't need the framework |
| 2026-10-22 | `state/*.json` and `logs/*.jsonl` are git-ignored; force-add a sample run for submission | Keeps generated files out of day-to-day commits |
| 2026-10-21 | Project name: ClaimLens | Short, clear, no Hinglish |
| 2026-10-19 | Base on CSE476 Q1, Indian health-claims variant | Keeps all five named agents and the required fan-out / fan-in with human routing |
| 2026-10-19 | All money maths in deterministic Python tools | LLM arithmetic is unreliable; makes the payout auditable |
| 2026-10-19 | Synthetic claims only; public policy wordings + IRDAI excerpts as corpus | No patient-data risk; fast to build |
| 2026-10-19 | Escalation thresholds: > ₹2,00,000, risk ≥ 60, no grounding clause | Starting values; tune in config.yaml |

## Open questions
- [ ] Confirm with the instructor that the Indian health-claims variant counts as Q1.
- [x] Team size: solo (2026-11-04).
- [ ] Solo scope: keep all seven agents, or drop the Grievance Drafter (S2 only)? The Human Review Desk stays, because M11 is a must-have.
- [ ] Framework: Microsoft Agent Framework or Semantic Kernel? Pin version. (Needed by Week 2, when agents get built.)
- [ ] Which 3–4 policy wordings to use (start with Arogya Sanjeevani standard wording).
- [ ] Which model lane / API key the team will use (fill `.env` from `.env.example`).
- [ ] Agree the shapes of `policies.json` and `data/claims/` (suggestions in `data/README.md`).
- [ ] Commit the source policy PDFs or only the chunked text? (PDFs are git-ignored for now.)
- [ ] (DevOps) When M3 lands, how does retrieval run on the lean servers: BM25-only, a prebuilt index, or bigger app instances? Keep heavy imports (`sentence_transformers`, `chromadb`) inside functions so `api.py` still imports on servers.
- [ ] (DevOps) INT333 demo date (deadline TBD in `pipeline.config.yml`).
- [ ] (DevOps) Turn on GitHub branch protection for `main` (require the `ci` checks) — needs the repo settings page.
- [ ] (DevOps) Switch on the Nagios scenario-1 check (`nagios_functional_args`) once M7 works; put the model API key in Ansible Vault then.

## Team split
- **Member A** — Intake, Cost Assessment, all money maths and unit tests.
- **Member B** — RAG corpus, Policy Retrieval, retrieval check.
- **Member C** — Fraud Signal, Adjudication Manager, Human Review Desk, notebook, README.

Solo project: A = B = C = Suharshit.

## Four-week plan

| Week | Member A | Member B | Member C | Done when |
| --- | --- | --- | --- | --- |
| 1 | Pydantic schemas, `parse_bill`, 7 scenario claims | Download 3–4 wordings, chunk by clause, build index | Shared state, run log, `policies.json`, `prior_claims.json` | One claim flows intake → state file → log |
| 2 | Cost tools with exact rupee unit tests | Policy Retrieval Agent + `get_policy_limits` | Fraud Signal Agent + risk rules | Each agent runs alone on scenario 1 |
| 3 | Over-claiming flag, deduction table | Citation guard, hit@3 check | Manager fan-in, escalation, human loop | All seven scenarios run end to end |
| 4 | `test_scenarios.py` green | Architecture diagram, slides | Demo notebook, README, viva prep | Submission checklist ticked |

## Task tracker
Status values: Not started · In progress · Done · Blocked. IDs match 03-features-and-scope.

| ID | Task | Owner | Status | Notes |
| --- | --- | --- | --- | --- |
| — | Repo setup: scaffold, config, context/, smoke tests | All | Done | 2026-10-22; `pytest` green (smoke tests) |
| — | DevOps pipeline (INT333): S0–S11 files | Suharshit | In progress | Committed on `devops-pipeline` 2026-11-04 (pytest 32 passed, ruff clean); next: push → PR → CI green → merge, first release, `make up` on AWS |
| M1 | Claim intake → structured record | A | Not started | Stubs: `tools/schemas.py`, `tools/intake_tools.py` |
| M2 | Halt on missing policy id / amount | A | Not started | |
| M3 | RAG over policies + IRDAI, filtered by policy id | B | Not started | Stubs: `tools/retrieval_tools.py` |
| M4 | Deterministic payable calculation | A | Not started | |
| M5 | Over-claiming flag | A | Not started | |
| M6 | Fraud risk score with reasons | C | Not started | |
| M7 | Parallel fan-out + fan-in | C | Not started | Stub: `workflow.py` |
| M8 | Four verdicts with payout + clause | C | Not started | |
| M9 | Citation guard | B | Not started | |
| M10 | Escalation routing | C | Not started | |
| M11 | Human-in-the-loop write-back | C | Not started | |
| M12 | Shared claim-state record | C | Not started | Stub: `tools/state.py` |
| M13 | Append-only run log | C | Not started | Stub: `tools/logger.py` |
| M14 | Demo notebook with trace | C | Not started | |
| M15 | Test file (≥ 3 scenarios; plan 7) | A | Not started | Skipped placeholders in `tests/test_scenarios.py` |
| S1 | Deduction table in output | A | Not started | |
| S2 | Grievance letter draft | — | Not started | |
| S3 | Missing-document check | — | Not started | |
| S4 | Streamlit UI | — | Not started | |
| S5 | Retrieval hit@3 check | B | Not started | |
| S6 | Accuracy table | A | Not started | |

## Submission checklist
- [ ] Built on Microsoft Agent Framework or Semantic Kernel
- [ ] ≥ 4 agents, one module each
- [ ] Every agent calls ≥ 2 Python tools
- [ ] RAG grounding + shared state used by every agent
- [ ] README ≤ 2 pages (roster, architecture + why, tools, memory/retrieval, one honest failure)
- [ ] Runnable demo notebook with multi-agent trace
- [ ] Architecture diagram
- [ ] Append-only run log
- [ ] Test file with ≥ 3 scenarios

## Known issues / blockers
(none yet)

## Session log (newest first)
Format: date · who · what was done · what's next.

- **2026-11-04** · Suharshit · Status review: GitHub `main` still has only the scaffold commit, all agents and tools still stubs, `data/` empty, about two weeks behind plan. Recorded the solo decision. Prepared the DevOps pipeline for its first commit: no secrets or state files staged, replaced a non-UTF-8 dash in `requirements.txt`, pytest 32 passed / 12 skipped, ruff clean. · Next: push `devops-pipeline`, open the PR, CI green, merge; then M12/M13 and the Week 1 data.

- **2026-10-22** · DevOps · Followed `DEVOPS_PIPELINE_TEMPLATE.md`: owner calls recorded in `pipeline.config.yml`; added `api.py` server mode + `tests/test_api.py`, CI and release workflows, Terraform (AWS), Ansible roles, Puppet module, Nagios plugin, `Makefile`, `infra/README.md` runbook. Checked locally: pytest 32 passed, ruff clean, API health/version curl, plugin exit codes 0–3, ansible-lint production 0 failures, syntax-check, templates rendered, terraform fmt + validate, puppet-lint + parser validate, tarball contents. Not yet: CI run on GitHub, release, any AWS apply. · Next: review, commit, push the branch, open a PR, watch CI.

- **2026-10-22** · Setup · Scaffolded the repo to the 02 layout: seven agent stubs (each lists ≥ 2 tools), tool stubs with the agreed function names, `workflow.py`, `config.yaml` (04 starting values), `requirements.txt`, `.env.example`, `.gitignore`, `data/README.md` with suggested data shapes, `CLAUDE.md`, `context/` with the five briefs, smoke tests (green) and skipped placeholders for tool and scenario tests. Pushed to GitHub `main`. · Next: settle framework + team size; start Week 1 tasks.
- **2026-10-21** · Planning · Brief split into five project files; name changed to ClaimLens. · Next: resolve open questions, start Week 1.
- **2026-10-19** · Planning · Researched market fit; chose the health-insurance claims idea; wrote the project brief. · Next: split brief into project files.
