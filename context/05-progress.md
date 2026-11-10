# ClaimLens — 05 Progress

This is the single source of truth for where the project stands. Read it at the start of every chat. Update it at the end of every working session: change task statuses, add a session-log entry (newest first), and record any decision or open question.

## Current status
- **Phase:** All must-haves (M1–M15) done — LLM intake merged (#15); all seven scenarios pass end to end with and without the LLM; submission pieces and should-haves left
- **Current week:** Week 3 / final week by calendar (10 Nov); deadline 15 Nov
- **Last updated:** 2026-11-10
- **Next action (Suharshit):** push `docs/progress-m1-done` → PR → merge; then push `feat/s4-demo-website` → PR → merge. Try the site: `python api.py` → http://localhost:8000. Then slides + viva prep, INT333 `make up ENV=dev` (the site comes with it). Full list: `HANDOFF.md`.

## Decisions made

| Date | Decision | Why |
| --- | --- | --- |
| 2026-11-10 | **S4 demo UI = a web page served by the FastAPI app** (`web/index.html` at `GET /`, JSON routes `/api/claims`, `/api/claims/{id}`, `/api/claims/{id}/review`, `/api/clauses/{id}`) instead of the Streamlit `app.py` planned in 04 | Benefits both courses: the CSE476 demo and the app the INT333 pipeline already deploys to AWS (Streamlit can't run on the 1 GB servers); no new dependency; vanilla HTML/JS, no CDN, so it works offline at the viva. 04 left unchanged; this row supersedes its Streamlit line |
| 2026-11-10 | The website's Evaluation tab is the S6 accuracy table: expected (hand-worked `expected.json`) vs actual per scenario, same verdict + payout check as `tests/test_scenarios.py` | No separate S6 artefact needed; 7/7 shown live |
| 2026-11-10 | Fix: `create_review_ticket` writes an existing open ticket back into the record | A re-run of an escalated claim (`reset_state`) left it escalated with no ticket, so it could never be reviewed — found while testing the website's Run-again button; regression test in `test_scenarios.py` |
| 2026-11-10 | README rewritten to fit 2 A4 pages with the diagram (it rendered to 4): diagram floated right at 215 px beside the architecture/money/fraud/memory text, roster drops the Writes column (sections match agent names), memory table folded into prose, LLM intake paragraph added, test count 291 + 4 live | Deliverable limit is 2 pages; `architecture.png` is also a separate deliverable at full size |
| 2026-11-10 | The Indian health-claims variant is taken as a valid Q1 answer; no instructor confirmation needed | The professor is open to both generic and domain variants; the architecture maps 1:1 onto Q1 (five named agents, fan-out / fan-in, human routing). Corpus stays the IFFCO wording + IRDAI lists; partial approve stays as a fourth verdict |
| 2026-11-10 | **Model lane: free open-weight models over OpenAI-compatible APIs** — Groq (`qwen/qwen3.8-27b`, reasoning hidden) first, NVIDIA build (`nvidia/nemotron-3.5-lightning-30b-a3b`, thinking off) second, rule-based extractor last. Keys `GROQ_API_KEY` / `NVIDIA_API_KEY` in `.env`; providers, models and caps in `config.yaml` `llm:` | No cost, no card; Groq has the clearest free limits and is fast for a live demo; Nemotron gives an NVIDIA open model as backup. Ruled out: Ollama (7.3 GB laptop, servers can't host a model), Hugging Face (≈$0.10/month free credit), OpenRouter (50 free requests/day), Kaggle (GPU notebooks, not an API) |
| 2026-11-10 | Models re-picked after the first live ping: Groq had dropped `llama-3.3-70b-versatile` (404) and NVIDIA retired `nemotron-3-nano-30b-a3b` on 2026-09-01 (410). Tried the claim-1 extraction on each candidate: `qwen/qwen3.8-27b` 10/10 fields agree, 0.6 s; `openai/gpt-oss-120b` 9/10; `nemotron-3.5-lightning-30b-a3b` 10/10; `nemotron-nano-3-30b-a3b` and `nemotron-3-super-120b-a12b` 404 for this account. Added `python -m tools.llm_client models` and a 404/410 hint | Free catalogs change without notice; the fix is a config edit, and the tool now says so |
| 2026-11-10 | `tools/llm_client.py` calls `/chat/completions` with `httpx` (not an MAF chat client) | Reads the providers' `x-ratelimit-*` headers and token usage for the caps; one small dependency on the lean servers (`httpx` added to `requirements-server.txt`); the workflow itself stays on MAF |
| 2026-11-10 | Self-imposed caps below each free tier, counted per provider per UTC day + rolling minute in `state/llm_usage.json` (config `paths.llm_usage`, deliberately not a runtime key so the count holds across notebook, tests and API). A call that would pass a cap is never sent; HTTP 429 blocks the provider for `retry-after`; failed attempts still count. Groq caps 25 RPM / 900 RPD / 7K TPM / 90K TPD (free, from its headers: 1,000 RPD / 8K TPM); NVIDIA 30 RPM / 200 RPD (credit-metered) | The free tiers can't be overrun by a demo loop; budget left is shown by `python -m tools.llm_client`, `GET /llm/usage`, and every intake log line |
| 2026-11-10 | LLM = a second reading, rules win: rules extract first and decide any halt (M2); the LLM reads the same message; `reconcile_fields` keeps the rule value on every disagreement (logged as a mismatch), fills only fields the rules couldn't read, and never takes `policy_id` or `claimed`; filled fields must still validate as `ClaimIntake`. No key / cap reached / error → rules only, reason logged | Money and halts stay deterministic; scenario 3's waiting-period match depends on the rule diagnosis wording; a wrong LLM reading can't change any verdict (tested) |
| 2026-11-10 | Tests: `tests/conftest.py` sets `CLAIMLENS_LLM=off` for every test not marked `live`; `tests/test_llm_client.py` (offline, `httpx.MockTransport`); `tests/test_llm_live.py` marked `live`, excluded by `pytest.ini` — run with `pytest -m live -s`, skips a provider with no key | CI and normal `pytest` never touch the network or spend budget, even with real keys in `.env` |
| 2026-11-05 | Release tags are pushed with plain git from PowerShell (`git tag -a vX.Y.Z` + `git push origin vX.Y.Z`); every other `make` target runs from WSL Ubuntu, as `infra/README.md` says | `make` isn't installed on Windows; `make release` is only those two git commands |
| 2026-11-05 | **Framework: Microsoft Agent Framework** (`agent-framework-core==1.24.0`, pinned in both requirements files). `workflow.build_workflow()` is a `WorkflowBuilder` graph: intake → fan-out [policy_limits, fraud]; policy_limits → fan-out [policy_retrieve, cost]; fan-in [policy_retrieve, cost, fraud] → manager → human_desk. Each agent is an `@executor`; the edge message is the claim id; agents still share data only via the claim-state record | MAF is Microsoft's successor to Semantic Kernel (1.0 GA Apr 2026); its fan-out / fan-in edge groups map 1:1 onto the brief; the core package has no model-SDK or PyTorch deps, so it runs on the 1 GB servers (checked: scenario 1 HTTP 200 in 0.3 s). Decided by merging PR "Move the workflow onto Microsoft Agent Framework" |
| 2026-11-05 | Demo = `demo.ipynb` (executed, outputs saved): claim + bill, live agent trace from the run log, decision card + deduction table, scenario 4 reviewer step, 7-scenario expected-vs-actual table. Generated by a script so it can be rebuilt | M14; the trace shows Policy/Fraud interleaving and Cost starting on the posted limits |
| 2026-11-05 | README rewritten as the submission README (roster, architecture + why, tools, memory/retrieval, results, one honest failure — the nursing-in-the-cap correction found by reading the PDF, plus scenario 6's refusal to decide); `architecture.mmd` → `architecture.png` | Deliverables; the 03 example failure (LLM room-rent maths) never happened in this build, so it isn't claimed |
| 2026-11-05 | (Orchestration superseded the same day by the Microsoft Agent Framework graph above; the threading, limits-first and review-ticket behaviour carried over.) Workflow (M7) = asyncio: each agent's `run_sync` runs in a worker thread; Policy and Fraud start together; Policy posts limits first (`post_limits`) and an `asyncio.Event` starts Cost while Policy keeps retrieving (`retrieve`); the Manager fans in; an escalation opens a review ticket and returns status `escalated`; `human_desk.review(...)` closes it. A re-run resets the record (`reset_state`); the run log keeps history | Real parallelism with the existing state lock; framework-neutral, so the chosen framework only replaces the orchestration, not the agents |
| 2026-11-05 | `extract_claim_fields` is a deterministic rule-based extractor for the synthetic claim format (policy id, policyholder, patient, dates, diagnosis + procedure, room, amount, bill number, accident); halts with `IntakeHalt(reason=…)` on a missing policy id or amount. The LLM path is added with the framework; the rule path stays for CI/offline and as the test oracle | No model lane or API key yet; CI must run without one |
| 2026-11-05 | Intake halts are recorded with `set_halt` → record `halt` = {reason, message}, status stays `intake`; `HaltReason` adds `missing_bill`, `invalid_bill` | Scenario 7 is visible in the record and the log, and nothing downstream runs |
| 2026-11-05 | "No grounding" = no clause from the claim's own policy wording retrieved (IRDAI lists alone don't ground a decision) | IRDAI lists apply to every policy; scenario 6 must still escalate |
| 2026-11-05 | `CLAIMLENS_RUNTIME_DIR` moves `state/`, `logs/` and the review queue (tests, notebook, servers); every agent logs each tool call with `log_step` | Tests never write into the repo; the trace shows every tool |
| 2026-11-05 | Nagios real-function check switched on (`nagios_functional_args`), and CI's server job runs the same POST `/claims/CLM-0001/run` check on the lean install | M7 works on the lean server deps (checked: HTTP 200 in 0.4 s) |
| 2026-11-05 | `apply_decision_rules`: base verdict = reject if the waiting-period check excluded the admission (payout 0, cite its clause); partial if any deduction goes beyond IRDAI-list rows and co-pay; else approve. Escalation reasons in fixed order: high_value (> ₹2,00,000), fraud_risk (≥ 60), no_grounding (nothing retrieved), citation_failed, low_confidence (< 0.6). An escalation keeps the recommended payout | Deterministic, testable verdicts; the reviewer sees what the system would have paid |
| 2026-11-05 | Confidence = the lowest retrieval score among the cited clauses (an unretrieved citation counts 0; 1.0 when nothing needs citing) | A verdict is only as grounded as its weakest citation — ties M9 and M10 together |
| 2026-11-05 | `write_decision`: escalation → status `escalated`; auto decision → `decided` → `closed`. `DecisionSection` gains `escalation_reasons`; rationale is a deterministic template (the LLM may rephrase it later, never change numbers) | Matches the flow (auto decision closes the claim) |
| 2026-11-05 | Human Review Desk: `review_queue.json` (config `paths.review_queue`, git-ignored with `state/`), ticket ids `RV-0001…`, one open ticket per claim; `record_human_verdict(claim_id, verdict, note, *, reviewer, payout)` — approve pays the recommendation, reject 0, partial needs a payout ≤ recommendation; note required; claim must be escalated; closes the ticket and the claim. `HumanSection` gains `payout` | M11 write-back with a clear audit trail |
| 2026-11-05 | Retrieval = BM25 (`rank_bm25`) over one policy's chunks in `chunks.jsonl`; reported score = share of the query's IDF weight the clause contains (0–1), and only hits ≥ `retrieval.min_similarity` (0.45) return; an empty result means "no grounding clause". Vectors stay an optional add-on | Runs on the 1 GB servers and in CI without PyTorch or a model download; the threshold has a fixed meaning; scenario 6 (GHC-01) returns nothing |
| 2026-11-05 | The Policy Retrieval Agent asks one plain query per limit it needs (room rent, ICU, proportionate note, co-pay, 30-day wait, specified-condition wait + diagnosis) and `search_irdai_rules` for List I; `tests/test_search.py` pins each query to its clause | The citation guard needs every clause Cost and Fraud cite to be in the retrieved set |
| 2026-11-05 | Fraud rules and weights live in config `fraud_rules`: admitted < 60 days after cover start 35 · claimed ≥ 80% of SI 25 · bill number already in `prior_claims.json` 40 · same-day discharge, not day care 20; capped at 100 | Scenario 5 = 35 + 40 = 75 ≥ 60; any single rule stays below 60; scenario 4 lists amount_near_sum_insured (25) without escalating on fraud |
| 2026-11-05 | `check_waiting_period(start, admit, condition, *, limits, accident=False)`: 30-day wait (6.2.i), 48-month joint replacement (6.3.ii), 24-month specified conditions (6.3.i) matched by whole-word `condition_terms` in `policies.json`; accidents skip all of these; PED (6.1) not checked (no declared-PED data) | Scenario 3 rejects on `6.3.i`; scenario 5's accident on day 20 isn't excluded; terms are data, not code |
| 2026-11-05 | `FraudSection` = `score`, `reasons` (`FraudReason` codes), `details` (one sentence each), `waiting_period` (`WaitingPeriodCheck`); `ClaimIntake.accident` added | The Manager needs the waiting-period result to reject; codes are testable, details readable |
| 2026-11-04 | Cost order: IRDAI lists → room/ICU caps → proportionate cuts (exact `Fraction`s) → round each cut half-up → sub-limit → 5% co-pay on admissible (rounded half-up) → sum-insured cap. Rounding only in `compute_payable` (`_round`); rows ordered so `claimed − Σ deductions = payable` | One auditable path; the deduction table always adds up |
| 2026-11-04 | `classify_items` reads Lists I–IV from `chunks.jsonl` and matches the normalised description exactly (also without its bracketed part; '/' or ',' alternatives only for unqualified entries); List I → `non_payable`, Lists II–IV billed separately → `subsumed`, both deducted in full | No accidental partial-word matches; the lists come from the same corpus the citations do |
| 2026-11-04 | Room-cap cut is one row "Room + nursing (N days)" (taken from room first, then nursing); ICU capped separately (4.1.ii); if both exceed, the lower ratio applies to the other expenses | Matches the scenario tables; one ratio keeps note 2 unambiguous |
| 2026-11-04 | `compute_payable(items, limits, *, sub_limit=None, margin_pct=None)` returns exactly the `cost` section (`deductions`, `payable`, `overclaim`); the agent chooses `sub_limit` (e.g. `cataract_per_eye`) from the diagnosis; margin defaults to config. `overclaim_flag(claimed, payable, margin)` is the M5 helper | Keeps the brief's signature; sub-limits need clinical context the bill doesn't carry |
| 2026-11-04 | Waiting-period rejection is not a cost deduction: Cost gives scenario 3 a bill-level payable (₹73,150); the Manager's reject makes the payout ₹0 | Cost stays pure bill maths; the decision lives with the Manager |
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
- [x] Indian health-claims variant counts as Q1 (2026-11-10): the professor accepts either a generic or a domain variant, so no confirmation needed.
- [x] Team size: solo (2026-11-04).
- [ ] Solo scope: keep all seven agents, or drop the Grievance Drafter (S2 only)? The Human Review Desk stays, because M11 is a must-have.
- [x] Framework: Microsoft Agent Framework, `agent-framework-core==1.24.0` (2026-11-05).
- [ ] Which other 2–3 policy wordings to add (ASJ-01 = IFFCO Tokio wording, decided 2026-11-04). Scenarios only need ASJ-01 + GHC-01.
- [x] Model lane: Groq first, NVIDIA build (Nemotron) second, rules as fallback (2026-11-10); keys in `.env` from `.env.example`.
- [ ] (DevOps) Use the LLM on the AWS servers? Default is no key there → rules only. If yes, put `GROQ_API_KEY` in Ansible Vault and template it into the service env.
- [x] Shapes of `policies.json` and `data/claims/` agreed (2026-11-04, `data/README.md`).
- [x] IFFCO wording PDF downloaded and every scenario/limit clause id checked against it (2026-11-04, `tests/test_retrieval.py`).
- [x] Commit only the chunked text (`data/corpus/chunks.jsonl`); PDFs stay git-ignored (2026-11-04).
- [x] (DevOps) Retrieval on the lean servers: BM25 over the committed `chunks.jsonl` (2026-11-05); `rank-bm25` is already in `requirements-server.txt`.
- [ ] Road ambulance: 4.1.1.v covers it up to ₹2,000 but List I item 67 is "AMBULANCE" — `classify_items` would mark a line named exactly "Ambulance" non-payable. Not in any scenario; decide if a claim needs it.
- [ ] (DevOps) INT333 demo date (deadline TBD in `pipeline.config.yml`).
- [ ] (DevOps) Turn on GitHub branch protection for `main` (require the `ci` checks) — needs the repo settings page.
- [x] (DevOps) Nagios scenario-1 check switched on (2026-11-05). Put the model API key in Ansible Vault once intake uses the LLM.

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
| — | DevOps pipeline (INT333): S0–S11 files | Suharshit | In progress | PR #1 merged 2026-11-04; release **v0.1.0** published 2026-11-05 (tarball + sha256, release workflow green); next: WSL setup, `make up ENV=dev` on AWS |
| M1 | Claim intake → structured record | A | Done | Rule-based `extract_claim_fields` (2026-11-05) + LLM path (Groq qwen3.8-27b → NVIDIA Nemotron 3.5 Lightning → rules, capped, rules-win cross-check), PR #15 merged 2026-11-10; live tests pass, 7/7 scenarios match with the LLM on |
| M2 | Halt on missing policy id / amount | A | Done | 2026-11-05 `IntakeHalt(reason)` + `set_halt`; scenario 7 halts, nothing downstream runs |
| M3 | RAG over policies + IRDAI, filtered by policy id | B | Done | 2026-11-04 chunking (202 chunks); 2026-11-05 `search_policy_clauses`, `get_policy_limits`, `search_irdai_rules` (BM25, 0–1 IDF-coverage score, policy filter); `tests/test_search.py` |
| M4 | Deterministic payable calculation | A | Done | 2026-11-04 `classify_items`, `room_rent_deduction`, `compute_payable` in `tools/cost_tools.py`; reproduces scenarios 1, 2, 4, 5, 6 row for row; `tests/test_cost_tools.py` |
| M5 | Over-claiming flag | A | Done | 2026-11-04 `overclaim_flag`; set in `compute_payable` from config margin |
| M6 | Fraud risk score with reasons | C | Done | 2026-11-05 `lookup_prior_claims`, `find_bill_number`, `check_waiting_period`, `score_risk` in `tools/fraud_tools.py`; `tests/test_fraud_tools.py` |
| M7 | Parallel fan-out + fan-in | C | Done | 2026-11-05 Microsoft Agent Framework workflow (`build_workflow`, fan-out / fan-in edge groups) + all agent `run` functions |
| M8 | Four verdicts with payout + clause | C | Done | 2026-11-05 `apply_decision_rules`, `write_decision`; `tests/test_decision_tools.py` |
| M9 | Citation guard | B | Done | 2026-11-05 `verify_citations`; failure escalates (`citation_failed`) |
| M10 | Escalation routing | C | Done | 2026-11-05 five reasons in `apply_decision_rules` |
| M11 | Human-in-the-loop write-back | C | Done | 2026-11-05 `create_review_ticket`, `record_human_verdict`, `review_queue` |
| M12 | Shared claim-state record | C | Done | 2026-11-04 `tools/state.py`, tests in `tests/test_state_log.py` (branch `feat/m12-m13-state-log`) |
| M13 | Append-only run log | C | Done | 2026-11-04 `tools/logger.py`, tests in `tests/test_state_log.py` |
| M14 | Demo notebook with trace | C | Done | 2026-11-05 `demo.ipynb` — 7/7 scenarios match |
| M15 | Test file (≥ 3 scenarios; plan 7) | A | Done | 2026-11-05 `tests/test_scenarios.py`: all 7 scenarios end to end + parallelism, section ownership, re-run and append-only log tests |
| S1 | Deduction table in output | A | Done | Table from `compute_payable` (item, amount, reason, clause), shown in `demo.ipynb` and on the website with clickable clause ids |
| S2 | Grievance letter draft | — | Not started | |
| S3 | Missing-document check | — | Not started | |
| S4 | Demo UI (web page, not Streamlit — see decisions) | C | In progress | 2026-11-10 built on `feat/s4-demo-website`: claim list, run, decision card, clause pop-ups, deductions, fraud gauge, agent timeline lanes, live trace, Human Review Desk form, Evaluation and Architecture tabs; `tests/test_web.py` (14). Done once merged |
| S5 | Retrieval hit@3 check | B | Not started | |
| S6 | Accuracy table | A | In progress | 2026-11-10 the website's Evaluation tab (expected vs actual, 7/7); Done with S4's merge |

## Submission checklist
- [x] Built on Microsoft Agent Framework (`workflow.py`)
- [x] ≥ 4 agents, one module each (7)
- [x] Every agent calls ≥ 2 Python tools
- [x] RAG grounding + shared state used by every agent
- [x] README ≤ 2 pages (roster, architecture + why, tools, memory/retrieval, one honest failure) — checked 2026-11-10: exactly 2 A4 pages rendered with the diagram (floated beside the details)
- [x] Sample run committed (`logs/run_log.jsonl`, `state/CLM-0001.json`, `state/CLM-0004.json`, force-added 2026-11-10)
- [x] Runnable demo notebook with multi-agent trace (`demo.ipynb`)
- [x] Architecture diagram (`architecture.png`)
- [x] Append-only run log (M13)
- [x] Test file with ≥ 3 scenarios (all 7)

## Known issues / blockers
(none yet)

## Session log (newest first)
Format: date · who · what was done · what's next.

- **2026-11-11** · Claude (Suharshit's request) · Website Architecture tab: the low-res `architecture.png` replaced by an inline, tall SVG drawn from `architecture.mmd` — main flow down the middle, halt branch left, fan-out band, fan-in to the Manager, escalation triggers in the Human Review Desk box, and the shared claim-state record + run log as a full-height rail with each agent's dashed write to its own section; adds the LLM second reading on Intake. Checked in a headless browser. · Next: merge `feat/s4-demo-website`; slides; viva prep; AWS deploy.

- **2026-11-10** · Claude (Suharshit chose the web page: "benefit both courses") · Branch `feat/s4-demo-website`: FastAPI-served demo site (`web/index.html`, 4 JSON routes), `tests/test_web.py`; checked in a headless browser (runs, review flow, clause pop-up, 7/7 evaluation, no console errors). Found and fixed a real bug: re-running an escalated claim lost its review ticket. README run line mentions the site (still 2 pages). pytest 306 passed. · Next: merge both branches; slides; viva prep; AWS deploy.

- **2026-11-10** · Suharshit + Claude · Demo re-run (trace shows `reconcile_fields` + budget left on claims 1–6; verdicts unchanged). README updated for the LLM path and cut from 4 rendered pages to 2. Sample run force-added. All on branch `docs/progress-m1-done` (5 commits). pytest 291 passed. · Next: push + merge; then the demo website (S4).

- **2026-11-10** · Suharshit · Decided the Indian variant counts as Q1 (professor open to both); open question closed. · Next: unchanged.

- **2026-11-10** · Suharshit · PR #15 (`feat/m1-llm-intake`) merged → M1 Done; every must-have complete. · Next: re-run demo + sample run, README page check, slides, viva prep, AWS deploy; then S5/S6.

- **2026-11-10** · Suharshit + Claude · Keys in `.env`; first ping failed (Groq 404, NVIDIA 410 — both models gone). Listed each key's models, tried the claim-1 extraction on five candidates, switched to `qwen/qwen3.8-27b` (Groq) and `nemotron-3.5-lightning-30b-a3b` (NVIDIA); added `models` command + retired-model hint. `ping` OK on both; `pytest -m live` 4 passed; `pytest` 291 passed / 1 skipped; all 7 scenarios end to end with the real LLM on match expected, Groq agreeing on all 10 fields for 1–6 (7 halts before the LLM). · Next: push `feat/m1-llm-intake`, PR, merge → M1 Done.

- **2026-11-10** · Claude (Suharshit's go-ahead) · Reviewed status (build complete, M1 LLM path the only open must-have, 5 days left). Compared free model lanes (Ollama, Hugging Face, NVIDIA build, Groq, OpenRouter, Kaggle) and chose Groq → NVIDIA Nemotron → rules. Branch `feat/m1-llm-intake`: `tools/llm_client.py` (OpenAI-compatible client, provider fallback, usage ledger with per-day/per-minute request and token caps, 429 blocking, `python -m tools.llm_client` status / `ping`), `llm_extract_claim_fields` + `reconcile_fields` in `tools/intake_tools.py`, Intake Agent cross-check with budget-left in the log, `GET /llm/usage`, `config.yaml` `llm:` block, `.env.example`, `tests/conftest.py`, `tests/test_llm_client.py` (23 offline tests), `tests/test_llm_live.py` (4 live tests, `-m live`). pytest 289 passed / 1 skipped / 4 live deselected; ruff clean. Not done from the session: real keys, live run, push, PR. · Next: Suharshit adds keys, runs `pytest -m live -s`, pushes and opens the PR; then slides + viva prep.

- **2026-11-05** · Suharshit · Tagged and pushed `v0.1.0` from PowerShell (`make` isn't on Windows); release workflow green, GitHub Release has `claimlens.tar.gz` + `.sha256`. · Next: WSL one-time setup, `make up ENV=dev`.

- **2026-11-05** · Suharshit (decision) / Claude (merge) · Framework decided: Microsoft Agent Framework — PR #12 merged after syncing with `main`; HANDOFF.md updated. · Next: release v0.1.0 + AWS deploy; optional LLM intake; should-haves.

- **2026-11-05** · Claude · Opened PR #12 (Microsoft Agent Framework workflow, CI green) for Suharshit's decision — not merged. Wrote `HANDOFF.md`: sync steps, framework decision, GitHub housekeeping, INT333 release + AWS deploy, optional LLM intake, submission pieces, should-haves. Couldn't push the release tag or delete branches from the session. · Next: Suharshit merges or closes #12.

- **2026-11-05** · Claude (with Suharshit's go-ahead to branch, push and merge) · Built and merged six PRs, each through CI: #6 M4/M5 (already merged), #7 M6 fraud tools, #8 M3 search (BM25, 0–1 coverage score), #9 M8–M11 decision rules, citation guard, escalation, human review desk, #10 M7 agents + asyncio workflow — all 7 scenarios end to end, Nagios/CI functional check on — and this PR: M14 `demo.ipynb`, submission README, `architecture.png`. pytest 266 passed / 1 skipped. Remaining for Suharshit in `HANDOFF.md`: framework + model decision and migration, LLM intake path, INT333 release + AWS deploy, branch cleanup, slides, viva prep. · Next: framework decision.

- **2026-11-04** · Suharshit · PR #5 merged (CI was queued ~10 min by a GitHub Actions incident, then green). Branch `feat/m4-cost-tools`: `classify_items` (IRDAI Lists I–IV from the corpus), `room_rent_deduction` (room + nursing pooled, ICU cap, note-2 ratio in exact fractions), `compute_payable` (half-up rounding, sub-limit, co-pay, SI cap, over-claim flag), `overclaim_flag`; reproduces every hand-worked cost table; `tests/test_cost_tools.py`. pytest 174 passed / 9 skipped, ruff clean. · Next: merge; `feat/m6-fraud-tools`; `feat/m3-search`; settle framework.

- **2026-11-04** · Suharshit · PR #4 merged. Branch `feat/m3-chunking`: read the downloaded IFFCO PDF (37 pages) — found nursing sits inside the ₹5,000 room cap and the proportionate note is under 4.1.1; re-shaped scenario bills 1–4 and 6 (scenario 2 payable now ₹48,925), re-keyed `4.1.1.note2` and `6.2.i`. Built `split_clauses` / `chunk_wording` / `build_index` / `load_chunks`, committed `data/corpus/chunks.jsonl` (202 chunks), `tests/test_retrieval.py` (splitter on synthetic text, every referenced clause present, clause text matches the maths, rebuild == committed). pytest 139 passed / 11 skipped, ruff clean. · Next: merge; settle framework; Week 2 cost tools + search.

- **2026-11-04** · Suharshit · PR #3 merged. Chose the IFFCO Tokio wording for ASJ-01 and the wording's medicines-only proportionate rule; re-keyed clause ids, recomputed scenario 2 (₹52,725). Branch `feat/data-scenarios-3-7`: claims CLM-0003…0007 (reject ₹0; escalate→human ₹4,26,550; fraud ₹94,050; no-grounding GHC-01 ₹42,000; halt), `prior_claims.json` (36), `data/corpus/SOURCES.md`, reason-code types, richer `ExpectedOutcome`, `PriorClaim`; `tests/test_data.py` extended. pytest 120 passed / 11 skipped, ruff clean. PDF download blocked on both build machines (403). · Next: merge; download the wording PDF; `feat/m3-chunking`.

- **2026-11-04** · Suharshit · M12/M13 PR #2 merged. Branch `feat/m1-schemas-data`: filled `tools/schemas.py` (all sections + `PolicyLimits`, `ExpectedOutcome`), `write_state` now validates sections and the whole record; `parse_bill`, `validate_policy`, `load_policies`, `IntakeHalt`; `data/policies.json` (ASJ-01, from the standard wording); scenario claims CLM-0001 (approve, ₹79,610) and CLM-0002 (partial, ₹56,145) with hand-worked `expected.json`; `tests/test_data.py`. pytest 95 passed / 11 skipped, ruff clean. · Next: merge; corpus PDFs + verify section ids; `prior_claims.json`; scenarios 3–7.

- **2026-11-04** · Suharshit · DevOps PR #1 merged. Built M12 (`tools/state.py`: `read_state`, `write_state` with section ownership, atomic locked writes, `set_status`, per-record trace) and M13 (`tools/logger.py`: append-only `append_log`, `read_log`). 25 new tests incl. parallel Policy/Fraud writes; pytest 57 passed / 12 skipped, ruff clean. · Next: merge `feat/m12-m13-state-log`; then `tools/schemas.py`, `policies.json`, `parse_bill`, scenario 1–2 claims.

- **2026-11-04** · Suharshit · Status review: GitHub `main` still has only the scaffold commit, all agents and tools still stubs, `data/` empty, about two weeks behind plan. Recorded the solo decision. Prepared the DevOps pipeline for its first commit: no secrets or state files staged, replaced a non-UTF-8 dash in `requirements.txt`, pytest 32 passed / 12 skipped, ruff clean. · Next: push `devops-pipeline`, open the PR, CI green, merge; then M12/M13 and the Week 1 data.

- **2026-10-22** · DevOps · Followed `DEVOPS_PIPELINE_TEMPLATE.md`: owner calls recorded in `pipeline.config.yml`; added `api.py` server mode + `tests/test_api.py`, CI and release workflows, Terraform (AWS), Ansible roles, Puppet module, Nagios plugin, `Makefile`, `infra/README.md` runbook. Checked locally: pytest 32 passed, ruff clean, API health/version curl, plugin exit codes 0–3, ansible-lint production 0 failures, syntax-check, templates rendered, terraform fmt + validate, puppet-lint + parser validate, tarball contents. Not yet: CI run on GitHub, release, any AWS apply. · Next: review, commit, push the branch, open a PR, watch CI.

- **2026-10-22** · Setup · Scaffolded the repo to the 02 layout: seven agent stubs (each lists ≥ 2 tools), tool stubs with the agreed function names, `workflow.py`, `config.yaml` (04 starting values), `requirements.txt`, `.env.example`, `.gitignore`, `data/README.md` with suggested data shapes, `CLAUDE.md`, `context/` with the five briefs, smoke tests (green) and skipped placeholders for tool and scenario tests. Pushed to GitHub `main`. · Next: settle framework + team size; start Week 1 tasks.
- **2026-10-21** · Planning · Brief split into five project files; name changed to ClaimLens. · Next: resolve open questions, start Week 1.
- **2026-10-19** · Planning · Researched market fit; chose the health-insurance claims idea; wrote the project brief. · Next: split brief into project files.
