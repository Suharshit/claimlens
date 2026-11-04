# ClaimLens

> **Educational prototype — not insurance, legal or medical advice.** Synthetic claims only.

ClaimLens reads an Indian health-insurance claim and its hospital bill, checks both against the policy wording and IRDAI rules, and returns **approve, partial approve, reject or escalate** — with the payout and the clause behind every rupee deducted. CSE476 CA2 Project 2 (Q1: claim adjudication), multi-agent RAG with fan-out / fan-in and human routing.

**Run it:** `pip install -r requirements.txt` · `pytest` (all 7 scenarios) · open [`demo.ipynb`](demo.ipynb) · or `python workflow.py CLM-0001 CLM-0004`.

## Agent roster

| Agent (`agents/`) | Role | Writes | Tools (`tools/`) |
| --- | --- | --- | --- |
| Intake | Claim text + bill → validated record; halts on missing policy id / amount / bill | `intake`, `bill_items` | `extract_claim_fields`, `parse_bill`, `validate_policy` |
| Policy Retrieval | Posts the policy's limits, then retrieves the governing clauses | `policy` | `get_policy_limits`, `search_policy_clauses`, `search_irdai_rules` |
| Fraud Signal | Waiting periods + weighted risk rules over prior-claim memory | `fraud` | `lookup_prior_claims`, `check_waiting_period`, `score_risk` |
| Cost Assessment | Line-by-line payable and deduction table; over-claim flag | `cost` | `classify_items`, `room_rent_deduction`, `compute_payable` |
| Adjudication Manager | Fans in, decides, cites clauses, routes to a human | `decision` | `apply_decision_rules`, `verify_citations`, `write_decision` |
| Human Review Desk | Review ticket; reviewer's verdict written back, claim closed | `human` | `create_review_ticket`, `record_human_verdict` |
| Grievance Drafter (S2) | Should-have, not built | `letters` | `list_contestable`, `render_letter` |

## Architecture and why it fits

![architecture](architecture.png)

Intake runs first; then **Policy Retrieval and Fraud Signal run in parallel** — the policy check and the fraud check need nothing from each other. **Cost waits only for the policy limits**: Policy posts them first, so Cost starts while clause retrieval is still running. The **Manager fans in** all three and is the single place a verdict is made, which keeps it auditable. Escalation sends the claim to a **human** with the system's recommended payout. Agents never import each other: they talk only through one shared record, `state/<claim_id>.json`, where each agent may write only its own section, and every write is appended to `logs/run_log.jsonl`.

Orchestration today is `asyncio` (`workflow.py`), each agent's steps in a worker thread; moving it onto Microsoft Agent Framework / Semantic Kernel is pending (see `context/05-progress.md`).

## Tools: what is deterministic and why

**All money maths is Python, never the LLM.** Money is `int` rupees; rounding (half-up) happens only in `compute_payable`. The order is the policy's: IRDAI List I items out (List II–IV items billed separately are subsumed) → room rent + boarding + nursing capped at 2% of SI / ₹5,000 a day (`ASJ-01:4.1.i`), ICU at 5% / ₹10,000 (`4.1.ii`) → above a cap, every other expense except medicines cut in proportion (`4.1.1.note2`) → sub-limits (cataract `4.3`, modern treatments `4.6`) → 5% co-pay (`9.3`) → sum-insured cap. The deduction table always adds up: claimed − Σ cuts = payable.

**Fraud** (`config.yaml` → `fraud_rules`): admitted < 60 days after cover start (35) · claimed ≥ 80% of SI (25) · bill number already used by a prior claim (40) · same-day discharge, not day care (20); capped at 100. **Waiting periods**: 30 days (`6.2.i`), 24-month specified conditions such as hernia (`6.3.i`), 48-month joint replacement (`6.3.ii`); accidents are exempt.

**Escalation** (Manager): claimed > ₹2,00,000 · fraud ≥ 60 · no clause from the policy's own wording retrieved · a cited clause not in the retrieved set (**citation guard**) · confidence < 0.6, where confidence is the weakest retrieval score among the cited clauses.

## Memory and retrieval

| Store | Holds | Used by |
| --- | --- | --- |
| `data/corpus/chunks.jsonl` (RAG) | IFFCO Tokio *Arogya Sanjeevani* wording (UIN IFFHLIP20161V011920) split into 202 clause chunks by its own numbering; IRDAI Lists I–IV from its Annexure-A | Policy Retrieval, Cost (List I–IV names) |
| `data/policies.json` | Hand-typed limits per policy — ground truth for the maths | Policy, Fraud, Cost |
| `data/prior_claims.json` | 36 synthetic earlier claims | Fraud (duplicate bill, history) |
| `state/`, `logs/` | Shared claim record; append-only trace | every agent |

Retrieval is BM25 over one policy's chunks (always filtered by `policy_id`), plus the IRDAI lists. The reported score is the share of the query's IDF weight a clause contains (0–1), so `min_similarity = 0.45` has a fixed meaning; below it, nothing is returned. It runs on the 1 GB deployment servers without PyTorch; vector search is an optional add-on. Limits never come from retrieval, so a payout never depends on retrieval luck.

## Results — seven scenarios (`tests/test_scenarios.py`, `demo.ipynb`)

| # | Claim | Outcome |
| --- | --- | --- |
| 1 | Appendectomy ₹85,000 | approve ₹79,610 (List I items + 5% co-pay) |
| 2 | Room ₹7,000 + nursing ₹1,000/day | partial ₹48,925 (cap + proportionate 5,000/8,000) |
| 3 | Planned hernia repair, month 6 | reject (`6.3.i`, 24-month wait) |
| 4 | Angioplasty ₹4,50,000 | escalate → reviewer approves ₹4,26,550 → closed |
| 5 | Accident on day 20, reused bill no. | escalate (fraud score 75: both reasons) |
| 6 | Policy with no wording in the corpus | escalate: "no grounding clause found" |
| 7 | No amount, no bill | intake halts; nothing downstream runs |

Expected numbers are worked by hand in each `data/claims/<id>/expected.json`, never produced by the code under test. 266 tests in all.

## One honest failure

The first version of the data treated nursing as a separate bill line under the room cap. Reading the actual PDF clause by clause (the chunker's own test checks key phrases) showed that 4.1(i) caps *"Room Rent, Boarding, **Nursing** Expenses"* together at ₹5,000 a day — so scenario 1, meant to be a clean approval, would have tripped a proportionate deduction. We re-shaped the scenario bills, changed the cost tool to pool room and nursing, and pinned the clause text in a test. The system's own designed failure is scenario 6: when no clause from the policy's wording clears the threshold, the Manager **refuses to decide** and escalates instead of guessing.

## Repository

`agents/` one module per agent · `tools/` deterministic tools, `state.py`, `logger.py`, `schemas.py` (Pydantic) · `workflow.py` · `config.yaml` · `data/` (see `data/README.md`) · `tests/` · `context/` project briefs and progress · `api.py` + `infra/` DevOps pipeline (INT333; see `infra/README.md`).
