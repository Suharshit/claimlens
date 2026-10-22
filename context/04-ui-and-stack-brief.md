# ClaimLens — 04 UI & Stack Brief

## Tech stack
Python only, so everything can be debugged in one notebook.

| Layer | Choice |
| --- | --- |
| Language | Python 3.11 |
| Agent framework | Microsoft Agent Framework (or Semantic Kernel) — use its workflow / concurrent orchestration for the fan-out. Pin the version in week 1. |
| Model | Any course model lane; temperature 0 for intake and decisions |
| Retrieval | `sentence-transformers` embeddings (e.g. `bge-small-en`), Chroma or FAISS, `rank_bm25` for keyword search |
| Schemas and validation | Pydantic v2 |
| Documents | `pdfplumber` for policy PDFs |
| Templates | Jinja2 (grievance letters) |
| Config | `config.yaml` via PyYAML |
| Tests | pytest |
| Demo | Jupyter notebook (primary), Streamlit (optional UI) |

**Suggested `requirements.txt`:** agent-framework (or semantic-kernel), pydantic, sentence-transformers, chromadb (or faiss-cpu), rank-bm25, pdfplumber, jinja2, pyyaml, pytest, jupyter, streamlit, python-dotenv. Pin exact versions once installed.

**Environment:** model API key in `.env` (never committed); `.env.example` in the repo.

## config.yaml (starting values)

```yaml
model:
  temperature: 0
retrieval:
  top_k: 5
  min_similarity: 0.45
thresholds:
  human_review_amount_inr: 200000
  fraud_escalate_score: 60
  min_confidence: 0.6
  overclaim_margin_pct: 10
paths:
  corpus: data/corpus
  policies: data/policies.json
  prior_claims: data/prior_claims.json
  state_dir: state
  run_log: logs/run_log.jsonl
```

## Primary demo: notebook (`demo.ipynb`)
Required by the brief. For each demo claim it should print, in order:
1. Raw claim text and bill.
2. Each agent step as it runs (agent name, tool called, short result), showing Policy and Fraud starting together.
3. The final state record: verdict, payout, deduction table, fraud score and reasons, cited clauses.
4. For scenario 4: the escalation, a simulated human verdict, and the closed record.
5. A summary table of all seven scenarios (expected vs actual).

## Optional UI: Streamlit (`app.py`, should-have S4)
Keep it to one page with a sidebar; plain and readable beats styled.

| Screen / panel | What it shows | Actions |
| --- | --- | --- |
| Claim picker (sidebar) | List of claims in `data/claims/` with status badge (new, decided, escalated, closed) | Select a claim; "Run ClaimLens" |
| Claim input | Claim text, bill line items table, policy id | — |
| Live trace | Agent steps streamed in order, Policy and Fraud side by side, tool names and timings | — |
| Decision card | Verdict, payable ₹ vs claimed ₹, confidence, escalation reason if any | — |
| Deduction table | Item, amount cut, reason, clause id (click to view clause text) | — |
| Fraud panel | Score 0–100 and the reasons list | — |
| Human Review Desk | Queue of escalated claims with summary | Approve / partial / reject with a note → writes back and closes |
| Evaluation tab | Accuracy table (S6) and retrieval hit@3 (S5) | Re-run all scenarios |

Footer on every screen: "Educational prototype — not insurance, legal or medical advice."

## Coding conventions
- One agent per module in `agents/`; its tools in `tools/`. Agents never import each other — they communicate only via the claim-state record and the workflow.
- Every money value is an `int` in rupees; rounding happens only inside `compute_payable`.
- Every tool returns a Pydantic model or dict and calls `append_log`.
- Clause ids follow `<POLICY_ID>:<section>` or `IRDAI:<list>`.
- No secrets, real names or real patient data in the repo.
