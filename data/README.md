# data/

Synthetic data and public documents only — no real patient, hospital or policyholder data.

| Path | What goes here | Owner · week |
| --- | --- | --- |
| `corpus/policies/` | 3–4 public policy wordings (Arogya Sanjeevani standard wording first), one sub-folder or file set per `policy_id` | B · Week 1 |
| `corpus/irdai/` | IRDAI excerpts: standardisation guidelines (non-payable item lists), 2024 health master circular | B · Week 1 |
| `policies.json` | Per-policy limits hand-typed from each wording — the ground truth for all money maths | C · Week 1 |
| `prior_claims.json` | 30–50 synthetic earlier claims (policyholder, dates, amounts, bill numbers, outcomes) | C · Week 1 |
| `claims/` | The 7 scenario claims first (Week 1, A), growing to 15–20: claim text + bill + expected verdict and payable | A · Week 1 |

Only documents go into RAG. Limits and prior claims are structured files so arithmetic never depends on retrieval luck.

## Suggested shapes (agree in Week 1, then keep stable)

These are starting suggestions, not decisions — adjust as a team and record the final shape in `context/05-progress.md`.

`policies.json` — keyed by `policy_id`, money as `int` rupees:

```json
{
  "ASJ-01": {
    "name": "Arogya Sanjeevani (standard wording)",
    "sum_insured": 500000,
    "room_cap_per_day": 5000,
    "icu_cap_per_day": 10000,
    "copay_pct": 5,
    "sub_limits": {"cataract_per_eye": 40000},
    "waiting_periods_days": {"initial": 30, "specific_conditions": 730, "pre_existing": 1095},
    "inception_date": "2026-01-01"
  }
}
```

`claims/CLM-0001/` — one folder per claim:

```
claim.txt        free-text claim message
bill.csv         desc,category,qty,amount
expected.json    {"scenario": 1, "verdict": "approve", "payable": 0, "clauses": ["ASJ-01:4.3"]}
```

Clause ids follow `<POLICY_ID>:<section>` or `IRDAI:<list>`.
