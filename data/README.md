# data/

Synthetic data and public documents only — no real patient, hospital or policyholder data.

| Path | What goes here | Owner · week |
| --- | --- | --- |
| `corpus/policies/` | 3–4 public policy wordings (Arogya Sanjeevani standard wording first), one sub-folder or file set per `policy_id` | B · Week 1 |
| `corpus/irdai/` | IRDAI excerpts: standardisation guidelines (non-payable item lists), 2024 health master circular | B · Week 1 |
| `policies.json` | Per-policy limits hand-typed from each wording — the ground truth for all money maths | C · Week 1 |
| `prior_claims.json` | 36 synthetic earlier claims (policyholder, hospital, bill number, dates, amounts, outcome); PC-0017's bill number is reused by scenario 5 | C · Week 1 |
| `claims/` | The 7 scenario claims first (Week 1, A), growing to 15–20: claim text + bill + expected verdict and payable | A · Week 1 |

Only documents go into RAG. Limits and prior claims are structured files so arithmetic never depends on retrieval luck.

## Agreed shapes (2026-11-04)

Validated by the models in `tools/schemas.py` (`PolicyLimits`, `BillItem`, `ExpectedOutcome`); `tests/test_data.py` checks every file. Money is always `int` rupees.

`policies.json` — keyed by `policy_id`; see the real `ASJ-01` entry for every field:

```json
{
  "ASJ-01": {
    "policy_id": "ASJ-01",
    "name": "Arogya Sanjeevani (standard wording)",
    "source": "which wording + version the numbers came from (ASJ-01: IFFCO Tokio wording)",
    "inception_date": "2026-01-01",
    "sum_insured": 500000,
    "room_cap_per_day": 5000,
    "icu_cap_per_day": 10000,
    "copay_pct": 5,
    "sub_limits": {"cataract_per_eye": 40000, "modern_treatments": 250000},
    "waiting_periods": {"initial_days": 30, "specific_conditions_months": 24, "pre_existing_months": 36, "joint_replacement_months": 48},
    "specific_conditions": ["hernia of all types", "cataract and age-related eye ailments", "..."],
    "pre_hospitalisation_days": 30,
    "post_hospitalisation_days": 60,
    "clause_refs": {"room_rent": "ASJ-01:4.1.i", "proportionate_deduction": "ASJ-01:4.1.1.note2", "copay": "ASJ-01:9.3", "non_payable_items": "IRDAI:List-I"}
  }
}
```

`GHC-01` is a synthetic policy whose wording is deliberately not in the corpus (scenario 6).

`prior_claims.json` — a list; each entry: `claim_id` (`PC-0001`), `policyholder_id`, `policy_id`, `hospital`,
`bill_number`, `admit`, `discharge`, `diagnosis`, `claimed`, `paid`, `outcome` (`approved | partial | rejected`).

`claims/CLM-0001/` — one folder per claim:

```
claim.txt        free-text claim message (synthetic names; amounts in Indian format, "Rs 4,50,000")
bill.csv         desc,category,qty,amount   (quote any desc with a comma; whole rupees only; absent when intake halts)
expected.json    scenario, verdict, claimed, payable, overclaim, clauses, deductions, escalation_reasons,
                 fraud_reasons, fraud_min_score, human_verdict, final_status, halt, working
```

Bill categories: `room, icu, nursing, professional, ot, pharmacy, diagnostics, consumables, implants, misc`.
Room + nursing per day are capped together (ASJ-01:4.1.i); the ICU rate already includes critical-care nursing (3.26).
`expected.json` holds the hand calculation in `working`; its numbers must add up (`claimed − Σ deductions = payable`).
Reason codes (`escalation_reasons`, `fraud_reasons`, `halt`) are the `Literal` types in `tools/schemas.py`.
The over-claim flag is set only when payable > 0.

Clause ids follow `<POLICY_ID>:<section>` (sections as dotted lowercase, e.g. `ASJ-01:4.1.1.note2`) or `IRDAI:<list>`; see `corpus/SOURCES.md`.

| Claim | Scenario | Verdict | Payable | Notes |
| --- | --- | --- | --- | --- |
| CLM-0001 | 1 Clean approval (appendectomy) | approve | ₹79,610 | non-payables + 5% co-pay |
| CLM-0002 | 2 Room-rent breach (pancreatitis, room ₹7,000 + nursing ₹1,000/day) | partial | ₹48,925 | proportionate 5000/8000 on all but medicines |
| CLM-0003 | 3 Waiting period (planned hernia repair, month 6) | reject | ₹0 | `ASJ-01:6.3.i` |
| CLM-0004 | 4 High value (PTCA, ₹4,50,000) | escalate → human approves | ₹4,26,550 | closed by reviewer |
| CLM-0005 | 5 Fraud signal (day 20, reused bill no.) | escalate | ₹94,050 | risk ≥ 60, two reasons |
| CLM-0006 | 6 No grounding (GHC-01) | escalate | ₹42,000 | no clause in corpus |
| CLM-0007 | 7 Missing amount | intake halts | — | no bill, no downstream agent |
