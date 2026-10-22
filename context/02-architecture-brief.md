# ClaimLens — 02 Architecture Brief

## Pattern
Fan-out / fan-in with human routing (required by Q1). After intake, the Policy Retrieval and Fraud Signal agents run in parallel. Cost Assessment starts as soon as the policy limits are posted. The Adjudication Manager fans in every signal and either decides or routes the claim to a human. Every agent reads and writes one shared claim-state record.

## Flow

```
                 Intake Agent
          (claim + bill -> structured record)
                      |
                  fan-out
           +----------+-----------+
           v                      v
 Policy Retrieval Agent     Fraud Signal Agent
 (RAG: clauses + limits)    (rules + prior claims)
           |                      |
      after limits                |
           v                      |
 Cost Assessment Agent            |
 (deterministic payable maths)    |
           +-----------+----------+
                    fan-in
                       v
            Adjudication Manager
       (fans in signals, decides, cites clause)
           +-----------+-----------+
         auto                   escalate
           v                       v
     Auto decision          Human Review Desk
 (approve/partial/reject)   (verdict written back)
           +-----------+-----------+
                       v
                 Claim closed

All agents  <-->  state/<claim_id>.json   +   logs/run_log.jsonl (append-only)
```

## Why this pattern fits
- The policy check and the fraud check need nothing from each other, so running them in parallel is faster and easier to trace.
- Cost needs the policy limits first, so it is the one ordered step.
- A single manager keeps the final call in one place, which makes it auditable.
- The human route gives high-value claims a person's sign-off, as real insurers require.

## Agent roster

| Agent (module) | Role | Writes to claim state |
| --- | --- | --- |
| Intake Agent (`intake_agent.py`) | Turns claim text + bill into a structured record | `intake`, `bill_items` |
| Policy Retrieval Agent (`policy_agent.py`) | RAG over policy wordings and IRDAI rules; returns governing clauses and limits | `policy` |
| Fraud Signal Agent (`fraud_agent.py`) | Scores the claim on risk rules and prior-claim memory | `fraud` |
| Cost Assessment Agent (`cost_agent.py`) | Computes the payable amount line by line; flags over-claiming | `cost` |
| Adjudication Manager (`manager_agent.py`) | Fans in all signals, decides, cites clauses, routes to a human when needed | `decision` |
| Human Review Desk (`human_desk.py`) | Group-of-3 add-on: records the adjuster's verdict and closes the claim | `human` |
| Grievance Drafter (`grievance_agent.py`) | Should-have: drafts a query reply or grievance letter for contestable deductions | `letters` |

## Tools per agent
Rule: all money maths lives in deterministic Python functions, never in the LLM. The model only extracts, retrieves, explains and drafts.

| Agent | Tool (Python function) | What it does |
| --- | --- | --- |
| Intake | `extract_claim_fields(text)` | LLM call with a Pydantic schema → patient, admit/discharge dates, diagnosis, room type, claimed amount, policy id |
| Intake | `parse_bill(path)` | Reads bill CSV/JSON into line items (description, category, qty, amount) |
| Intake | `validate_policy(policy_id)` | Confirms the policy exists in `policies.json`; halts with a clear error if not |
| Policy Retrieval | `search_policy_clauses(policy_id, query, k)` | Hybrid BM25 + vector search over that policy's chunks; returns clause ids, text, score |
| Policy Retrieval | `get_policy_limits(policy_id)` | Structured limits: sum insured, room-rent and ICU caps, co-pay %, sub-limits, waiting periods |
| Policy Retrieval | `search_irdai_rules(query)` | Searches IRDAI excerpts, e.g. non-payable item lists |
| Fraud Signal | `lookup_prior_claims(policyholder_id)` | Reads the prior-claim memory store |
| Fraud Signal | `check_waiting_period(start, admit, condition)` | Flags claims inside the initial or condition-specific waiting period |
| Fraud Signal | `score_risk(record)` | Weighted rules: claim soon after inception, amount near sum insured, duplicate bill number, stay under 24 h for a non-daycare procedure |
| Cost Assessment | `classify_items(items)` | Marks each bill line payable, non-payable or subsumed using the IRDAI lists |
| Cost Assessment | `room_rent_deduction(items, limits)` | Applies proportionate deduction when the room exceeds the cap |
| Cost Assessment | `compute_payable(items, limits)` | Applies sub-limits, co-pay and sum-insured cap; returns payable total and a deduction table |
| Adjudication Manager | `apply_decision_rules(state)` | Thresholds from config → approve, partial, reject or escalate |
| Adjudication Manager | `verify_citations(clause_ids)` | Every cited clause id must exist in the retrieved set; any miss forces escalation |
| Adjudication Manager | `write_decision(state)` | Writes verdict, payout, clauses and rationale to the record |
| Human Review Desk | `create_review_ticket(claim_id, summary)` | Adds the claim to `review_queue.json` with a one-paragraph summary |
| Human Review Desk | `record_human_verdict(claim_id, verdict, note)` | Writes the human verdict back and sets status to closed |
| Grievance Drafter | `list_contestable(state)` | Picks deductions that look wrong against the cited clauses |
| Grievance Drafter | `render_letter(template, items)` | Fills a Jinja letter template with items, amounts and clauses |

Shared helpers: `read_state(claim_id)`, `write_state(claim_id, section, data)`, `append_log(event)`.

## Escalation triggers (config.yaml)
- Claimed amount above ₹2,00,000 → always human.
- Fraud risk score ≥ 60 → escalate.
- No retrieved clause above the similarity threshold → never auto-decide.
- Citation guard failure (cited clause not in retrieved set) → escalate.
- Manager confidence below threshold → escalate.

## Data and RAG corpus

| Data | What it holds | Source |
| --- | --- | --- |
| `data/corpus/` (RAG) | 3–4 policy wordings + IRDAI excerpts, chunked by clause | Insurers' public policy-wording PDFs (Arogya Sanjeevani standard wording first); IRDAI standardisation guidelines (non-payable lists); 2024 health master circular |
| `policies.json` | Per-policy limits: sum insured, room/ICU caps, co-pay, sub-limits, waiting periods | Hand-typed from each wording — ground truth for maths |
| `prior_claims.json` | Earlier claims per policyholder (dates, amounts, bill numbers, outcomes) | Synthetic, 30–50 rows |
| `claims/` | 15–20 test claims with text, bill, expected verdict and payable | Synthetic, hand-checked |

Only documents go into RAG; limits and memory are structured files so arithmetic never depends on retrieval luck.

**Chunking and retrieval**
- Split each wording by clause/section number.
- Metadata per chunk: `policy_id`, `section`, `clause_id`, `page`.
- Embeddings: small sentence-transformers model (e.g. `bge-small-en`) in Chroma or FAISS.
- BM25 for exact terms ("room rent", "cataract").
- Always filter by `policy_id` so one policy's clause is never cited for another.

## Shared claim-state record
One JSON per claim in `state/<claim_id>.json`. Each agent writes only its own section; every write is also appended to `logs/run_log.jsonl`.

```json
{
  "claim_id": "CLM-0007",
  "status": "intake | assessing | decided | escalated | closed",
  "intake": {"policy_id": "ASJ-01", "patient": "...", "admit": "2026-09-02", "discharge": "2026-09-05", "diagnosis": "...", "room_type": "single", "claimed": 185000},
  "bill_items": [{"desc": "Room charges", "category": "room", "qty": 3, "amount": 18000}],
  "policy": {"limits": {"sum_insured": 500000, "room_cap_per_day": 5000, "copay_pct": 5}, "clauses": [{"clause_id": "ASJ-01:4.3", "text": "...", "score": 0.82}]},
  "fraud": {"score": 22, "reasons": ["first claim within 90 days of inception"]},
  "cost": {"deductions": [{"item": "Gloves", "amount": 450, "reason": "non-payable consumable", "clause_id": "IRDAI:List-I"}], "payable": 151230},
  "decision": {"verdict": "partial", "payout": 151230, "clauses": ["ASJ-01:4.3"], "rationale": "...", "confidence": 0.78},
  "human": {"ticket": null, "reviewer": null, "verdict": null, "note": null},
  "trace": []
}
```

## Repository layout

```
claimlens/
  agents/        intake_agent.py  policy_agent.py  fraud_agent.py
                 cost_agent.py  manager_agent.py  human_desk.py  grievance_agent.py
  tools/         intake_tools.py  retrieval_tools.py  fraud_tools.py
                 cost_tools.py  decision_tools.py  state.py  logger.py
  workflow.py    fan-out / fan-in orchestration and human routing
  config.yaml    thresholds, model lane, top-k
  data/          corpus/  policies.json  prior_claims.json  claims/
  state/         one JSON record per claim
  logs/          run_log.jsonl (append-only)
  tests/         test_tools.py  test_scenarios.py
  app.py         optional Streamlit UI
  demo.ipynb
  README.md
  architecture.png
```
