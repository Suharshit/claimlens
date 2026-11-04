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

## Agreed shapes (2026-11-04)

Validated by the models in `tools/schemas.py` (`PolicyLimits`, `BillItem`, `ExpectedOutcome`); `tests/test_data.py` checks every file. Money is always `int` rupees.

`policies.json` — keyed by `policy_id`; see the real `ASJ-01` entry for every field:

```json
{
  "ASJ-01": {
    "policy_id": "ASJ-01",
    "name": "Arogya Sanjeevani (standard wording)",
    "source": "which wording + version the numbers came from",
    "inception_date": "2026-01-01",
    "sum_insured": 500000,
    "room_cap_per_day": 5000,
    "icu_cap_per_day": 10000,
    "copay_pct": 5,
    "sub_limits": {"cataract_per_eye": 40000, "modern_treatments": 250000},
    "waiting_periods": {"initial_days": 30, "specific_conditions_months": 24, "pre_existing_months": 36, "joint_replacement_months": 36},
    "specific_conditions": ["cataract", "hernia", "hysterectomy"],
    "pre_hospitalisation_days": 30,
    "post_hospitalisation_days": 60,
    "clause_refs": {"room_rent": "ASJ-01:5.a.i", "copay": "ASJ-01:10.e", "non_payable_items": "IRDAI:List-I"}
  }
}
```

`claims/CLM-0001/` — one folder per claim:

```
claim.txt        free-text claim message (synthetic names; amounts written "Rs 85,000")
bill.csv         desc,category,qty,amount   (quote any desc with a comma; whole rupees only)
expected.json    scenario, verdict, claimed, payable, overclaim, clauses, deductions, working
```

Bill categories: `room, icu, nursing, professional, ot, pharmacy, diagnostics, consumables, implants, misc`.
`expected.json` holds the hand calculation in `working`; its numbers must add up (`claimed − Σ deductions = payable`).

Clause ids follow `<POLICY_ID>:<section>` (sections as dotted lowercase, e.g. `ASJ-01:5.note.ii`) or `IRDAI:<list>`.

| Claim | Scenario | Verdict | Payable |
| --- | --- | --- | --- |
| CLM-0001 | 1 Clean approval (appendectomy) | approve | ₹79,610 |
| CLM-0002 | 2 Room-rent breach (pancreatitis, single AC) | partial | ₹56,145 |
