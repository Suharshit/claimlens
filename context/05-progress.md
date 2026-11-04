# ClaimLens — 05 Progress

This is the single source of truth for where the project stands. Read it at the start of every chat. Update it at the end of every working session: change task statuses, add a session-log entry (newest first), and record any decision or open question.

## Current status
- **Phase:** Week 1 nearly done — data, state, schemas and chunked corpus in place (calendar: end of Week 2, about one week behind plan)
- **Current week:** Week 2 by calendar; Week 2 tasks start next
- **Last updated:** 2026-11-04
- **Next action:** Merge `feat/m3-chunking`. Week 1 is then complete apart from `extract_claim_fields` (needs the framework). Next: settle the framework + model lane, then Week 2 — `feat/m4-cost-tools` (`classify_items`, `room_rent_deduction`, `compute_payable` with exact-rupee tests against scenarios 1–6) and `feat/m3-search` (`search_policy_clauses`, `get_policy_limits`, `search_irdai_rules`).

## Decisions made

| Date | Decision | Why |
| --- | --- | --- |
| 2026-11-04 | Room cap (4.1.i) covers room rent + boarding + **nursing** per day; the proportionate ratio is cap ÷ (room + nursing) per day; the ICU rate already includes critical-care nursing (3.26) | Read from the PDF: 4.1.i names "Room Rent, Boarding, Nursing Expenses" under one ₹5,000 cap. Scenario bills re-shaped so 1, 4, 5, 6 sit at or under the cap; scenario 2 now room ₹7,000 + nursing ₹1,000, payable ₹48,925 |
| 2026-11-04 | Clause ids follow the PDF's layout as chunked: proportionate note = `ASJ-01:4.1.1.note2` (it sits under 4.1.1), 30-day wait = `ASJ-01:6.2.i`; Annexure-A lists = `IRDAI:List-I`…`List-IV` (policy_id `IRDAI`); other annexures `ASJ-01:annex-b`/`annex-c` | Ids come from the chunker, never typed by hand; all scenario/limit ids verified present in `chunks.jsonl` |
| 2026-11-04 | Commit the chunked text (`data/corpus/chunks.jsonl`, config `paths.chunks`), not the PDFs; a test rebuilds it from the PDF when present and must match exactly | CI and the lean servers search without PDFs or pdfplumber; the PDF stays the checkable source |
| 2026-11-04 | `split_clauses(pages, policy_id)` is the pure splitter (headings, roman items, numbered notes, Annexure lists; repeated header/footer lines dropped); `chunk_wording` = pdfplumber + `split_clauses`; `build_index` writes `chunks.jsonl` only — BM25 is built from it at search time and the vector index arrives with `search_policy_clauses` | Splitter is unit-testable on synthetic text; heavy imports stay inside functions |
| 2026-11-04 | ASJ-01 corpus document = IFFCO Tokio Arogya Sanjeevani wording (UIN IFFHLIP20161V011920); clause ids re-keyed to its numbering: room `4.1.i`, ICU `4.1.ii`, proportionate `4.1.note2`, cataract `4.3`, modern `4.6`, PED `6.1`, 30-day `6.2`, specified `6.3.i`, joint `6.3.ii`, co-pay `9.3`; List I (its Annexure-A) stays `IRDAI:List-I`. Joint replacement wait 48 months per this wording | A full policy wording (not a prospectus), current 36-month PED, List I in the same PDF; supersedes the Acko numbering |
| 2026-11-04 | Proportionate room-rent deduction follows the wording (4.1 note 2): every other expense except medicines is cut. Scenario 2 payable is now ₹52,725 (was ₹56,145) | Every rule stays citable from one PDF; supersedes the IRDAI-wide exemption decision below |
| 2026-11-04 | Synthetic policy `GHC-01` in `policies.json` with no wording in the corpus | Gives scenario 6 a valid policy whose retrieval finds no grounding clause |
| 2026-11-04 | Shared reason codes in `tools/schemas.py`: `EscalationReason` (high_value, fraud_risk, no_grounding, low_confidence, citation_failed), `FraudReason` (soon_after_inception, amount_near_sum_insured, duplicate_bill_number, short_stay_non_daycare), `HaltReason` (missing_policy_id, unknown_policy, missing_claimed_amount) | M6/M10/M2 code and the scenario tests check the same codes, not free text |
| 2026-11-04 | `ExpectedOutcome` gains escalation/fraud reasons, `fraud_min_score`, `human_verdict`, `final_status`, `halt`; a halted claim has no verdict, amounts or bill | Scenarios 4–7 need these to be testable end to end |
| 2026-11-04 | Over-claim flag (M5) only when payable > 0 | A rejection (scenario 3) isn't over-claiming |
| 2026-11-04 | One `inception_date` per policy in `policies.json` stands for the scenario policyholders' cover start (2026-01-01) | Enough for the waiting-period and soon-after-inception rules; per-policyholder dates only if needed later |
| 2026-11-04 | `prior_claims.json`: 36 synthetic claims (seeded); PC-0017 holds bill `CGH/25/07731`, reused by scenario 5; no other scenario bill number appears | Gives the duplicate-bill rule exactly one true hit |
| 2026-11-04 | `write_state` validates each section against `tools.schemas.SECTION_MODELS` and the whole record against `ClaimState`; models forbid unknown fields; money fields are strict `int` (floats/strings refused) | Bad data fails at the write, naming the field, instead of surfacing later as a wrong payout |
| 2026-11-04 | `ClaimIntake` gains optional `policyholder_id` and `bill_number` | Fraud Signal needs them for prior-claim lookup and the duplicate-bill rule (scenario 5) |
| 2026-11-04 | `policies.json` shape: `waiting_periods` in months (`initial_days` in days), plus `name`, `source`, `specific_conditions`, `pre/post_hospitalisation_days`, `clause_refs`; documented in `data/README.md` | Wordings state waits in months; `clause_refs` tells Cost/Manager which clause id to cite for each limit |
| 2026-11-04 | ASJ-01 limits: SI ₹5,00,000; room 2% of SI max ₹5,000/day; ICU 5% max ₹10,000/day; co-pay 5%; cataract min(25% SI, ₹40,000)/eye; modern treatments 50% SI; waits 30 days / 24 months specified / 36 months PED; pre 30 / post 60 days | Standard Arogya Sanjeevani terms (section ids and joint-replacement wait since re-keyed to the IFFCO wording, above) |
| 2026-11-04 | ~~Proportionate deduction exempts pharmacy, diagnostics, consumables and implants (IRDAI rule)~~ — superseded the same day by the wording rule above | — |
| 2026-11-04 | Co-pay (5%) is applied after non-payable and room-rent deductions, on the admissible amount; it appears as its own deduction row | Matches ASJ wording ("on every admissible claim"); scenario 1's payout therefore = claimed − non-payables − 5% co-pay, slightly refining the 03 wording |
| 2026-11-04 | `parse_bill` accepts CSV or JSON, whole rupees only (`1,51,230` and `₹` allowed, paise refused), and raises `IntakeHalt` naming file + row; `IntakeHalt(ValueError)` lives in `tools/intake_tools.py` | M2: intake stops with a clear message; rounding stays only in `compute_payable` |
| 2026-11-04 | Each `expected.json` carries the hand calculation (`working`) and the deduction table; `tests/test_data.py` checks it adds up | Expected values are worked by hand, never produced by the code under test; doubles as viva evidence |
| 2026-11-04 | `write_state(claim_id, section, data, *, agent=None)`: optional `agent` is checked against `SECTION_OWNERS` (non-owner → `PermissionError`); first write creates the record; writes are atomic (temp file + `os.replace`) under a lock | Enforces "each agent writes only its own section" and keeps parallel Policy/Fraud writes from losing updates |
| 2026-11-04 | Added `set_status(claim_id, status, *, agent)` and `new_state` / `state_path` in `tools/state.py`, and `read_log(claim_id=None)` / `utc_now()` in `tools/logger.py` | `status` isn't an agent section, so it needs its own logged write; tests and trace views need to read the log |
| 2026-11-04 | Each write is recorded twice: a line in `logs/run_log.jsonl` and an entry in the record's `trace` (same `ts`) | Log test needs every agent in each trace; demo can show the trace from the record alone |
| 2026-11-04 | Claim ids must match `CLM-\d{4}` in `tools/state.py` (same as `api.py`) | Blocks path tricks like `../x` in state file names |
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
- [ ] Which other 2–3 policy wordings to add (ASJ-01 = IFFCO Tokio wording, decided 2026-11-04). Scenarios only need ASJ-01 + GHC-01.
- [ ] Which model lane / API key the team will use (fill `.env` from `.env.example`).
- [x] Shapes of `policies.json` and `data/claims/` agreed (2026-11-04, `data/README.md`).
- [x] IFFCO wording PDF downloaded and every scenario/limit clause id checked against it (2026-11-04, `tests/test_retrieval.py`).
- [x] Commit only the chunked text (`data/corpus/chunks.jsonl`); PDFs stay git-ignored (2026-11-04).
- [ ] (DevOps) When M3 search lands, how does retrieval run on the lean servers: BM25-only over the committed `chunks.jsonl` (no PDF/pdfplumber needed), a prebuilt vector index, or bigger app instances? Keep heavy imports inside functions so `api.py` still imports on servers.
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
| — | DevOps pipeline (INT333): S0–S11 files | Suharshit | In progress | PR #1 merged to `main` 2026-11-04; next: first release, `make up` on AWS |
| M1 | Claim intake → structured record | A | In progress | 2026-11-04: `tools/schemas.py` filled, `parse_bill`, `validate_policy`, `load_policies` done + tested; `extract_claim_fields` (LLM) waits for the framework |
| M2 | Halt on missing policy id / amount | A | In progress | `IntakeHalt` raised for missing/unknown policy and bad bills; missing-amount halt comes with `extract_claim_fields` |
| M3 | RAG over policies + IRDAI, filtered by policy id | B | In progress | 2026-11-04: `split_clauses`, `chunk_wording`, `build_index`, `load_chunks` done; 202 chunks in `chunks.jsonl`; search tools next (Week 2) |
| M4 | Deterministic payable calculation | A | Not started | |
| M5 | Over-claiming flag | A | Not started | |
| M6 | Fraud risk score with reasons | C | Not started | |
| M7 | Parallel fan-out + fan-in | C | Not started | Stub: `workflow.py` |
| M8 | Four verdicts with payout + clause | C | Not started | |
| M9 | Citation guard | B | Not started | |
| M10 | Escalation routing | C | Not started | |
| M11 | Human-in-the-loop write-back | C | Not started | |
| M12 | Shared claim-state record | C | Done | 2026-11-04 `tools/state.py`, tests in `tests/test_state_log.py` (branch `feat/m12-m13-state-log`) |
| M13 | Append-only run log | C | Done | 2026-11-04 `tools/logger.py`, tests in `tests/test_state_log.py` |
| M14 | Demo notebook with trace | C | Not started | |
| M15 | Test file (≥ 3 scenarios; plan 7) | A | In progress | All 7 scenario claims + hand-worked `expected.json` ready (CLM-0001…0007); `tests/test_scenarios.py` still skipped until M7 |
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
- [x] Append-only run log (M13)
- [ ] Test file with ≥ 3 scenarios

## Known issues / blockers
(none yet)

## Session log (newest first)
Format: date · who · what was done · what's next.

- **2026-11-04** · Suharshit · PR #4 merged. Branch `feat/m3-chunking`: read the downloaded IFFCO PDF (37 pages) — found nursing sits inside the ₹5,000 room cap and the proportionate note is under 4.1.1; re-shaped scenario bills 1–4 and 6 (scenario 2 payable now ₹48,925), re-keyed `4.1.1.note2` and `6.2.i`. Built `split_clauses` / `chunk_wording` / `build_index` / `load_chunks`, committed `data/corpus/chunks.jsonl` (202 chunks), `tests/test_retrieval.py` (splitter on synthetic text, every referenced clause present, clause text matches the maths, rebuild == committed). pytest 139 passed / 11 skipped, ruff clean. · Next: merge; settle framework; Week 2 cost tools + search.

- **2026-11-04** · Suharshit · PR #3 merged. Chose the IFFCO Tokio wording for ASJ-01 and the wording's medicines-only proportionate rule; re-keyed clause ids, recomputed scenario 2 (₹52,725). Branch `feat/data-scenarios-3-7`: claims CLM-0003…0007 (reject ₹0; escalate→human ₹4,26,550; fraud ₹94,050; no-grounding GHC-01 ₹42,000; halt), `prior_claims.json` (36), `data/corpus/SOURCES.md`, reason-code types, richer `ExpectedOutcome`, `PriorClaim`; `tests/test_data.py` extended. pytest 120 passed / 11 skipped, ruff clean. PDF download blocked on both build machines (403). · Next: merge; download the wording PDF; `feat/m3-chunking`.

- **2026-11-04** · Suharshit · M12/M13 PR #2 merged. Branch `feat/m1-schemas-data`: filled `tools/schemas.py` (all sections + `PolicyLimits`, `ExpectedOutcome`), `write_state` now validates sections and the whole record; `parse_bill`, `validate_policy`, `load_policies`, `IntakeHalt`; `data/policies.json` (ASJ-01, from the standard wording); scenario claims CLM-0001 (approve, ₹79,610) and CLM-0002 (partial, ₹56,145) with hand-worked `expected.json`; `tests/test_data.py`. pytest 95 passed / 11 skipped, ruff clean. · Next: merge; corpus PDFs + verify section ids; `prior_claims.json`; scenarios 3–7.

- **2026-11-04** · Suharshit · DevOps PR #1 merged. Built M12 (`tools/state.py`: `read_state`, `write_state` with section ownership, atomic locked writes, `set_status`, per-record trace) and M13 (`tools/logger.py`: append-only `append_log`, `read_log`). 25 new tests incl. parallel Policy/Fraud writes; pytest 57 passed / 12 skipped, ruff clean. · Next: merge `feat/m12-m13-state-log`; then `tools/schemas.py`, `policies.json`, `parse_bill`, scenario 1–2 claims.

- **2026-11-04** · Suharshit · Status review: GitHub `main` still has only the scaffold commit, all agents and tools still stubs, `data/` empty, about two weeks behind plan. Recorded the solo decision. Prepared the DevOps pipeline for its first commit: no secrets or state files staged, replaced a non-UTF-8 dash in `requirements.txt`, pytest 32 passed / 12 skipped, ruff clean. · Next: push `devops-pipeline`, open the PR, CI green, merge; then M12/M13 and the Week 1 data.

- **2026-10-22** · DevOps · Followed `DEVOPS_PIPELINE_TEMPLATE.md`: owner calls recorded in `pipeline.config.yml`; added `api.py` server mode + `tests/test_api.py`, CI and release workflows, Terraform (AWS), Ansible roles, Puppet module, Nagios plugin, `Makefile`, `infra/README.md` runbook. Checked locally: pytest 32 passed, ruff clean, API health/version curl, plugin exit codes 0–3, ansible-lint production 0 failures, syntax-check, templates rendered, terraform fmt + validate, puppet-lint + parser validate, tarball contents. Not yet: CI run on GitHub, release, any AWS apply. · Next: review, commit, push the branch, open a PR, watch CI.

- **2026-10-22** · Setup · Scaffolded the repo to the 02 layout: seven agent stubs (each lists ≥ 2 tools), tool stubs with the agreed function names, `workflow.py`, `config.yaml` (04 starting values), `requirements.txt`, `.env.example`, `.gitignore`, `data/README.md` with suggested data shapes, `CLAUDE.md`, `context/` with the five briefs, smoke tests (green) and skipped placeholders for tool and scenario tests. Pushed to GitHub `main`. · Next: settle framework + team size; start Week 1 tasks.
- **2026-10-21** · Planning · Brief split into five project files; name changed to ClaimLens. · Next: resolve open questions, start Week 1.
- **2026-10-19** · Planning · Researched market fit; chose the health-insurance claims idea; wrote the project brief. · Next: split brief into project files.
