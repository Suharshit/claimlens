# Corpus sources

Only public documents go into RAG. PDFs are git-ignored (`data/corpus/**/*.pdf`); the chunked text
built from them by `chunk_wording` is what the index uses. Download each file by hand (the build
machines can't reach these sites) and save it at the path shown.

| policy_id / list | Document | Save as | Clause ids |
| --- | --- | --- | --- |
| `ASJ-01` | IFFCO Tokio, Arogya Sanjeevani Policy — policy wording, UIN IFFHLIP20161V011920 — <https://www.iffcotokio.co.in/content/dam/iffcotokio/iffco-pdf/policy-wordings-arogya-sanjeevani-policy.pdf> | `policies/ASJ-01/wording.pdf` | `ASJ-01:<section>`, e.g. `ASJ-01:4.1.i` |
| `IRDAI:List-I` | Annexure-A List I ("Items for which coverage is not available in the policy") — the IRDAI standard list, taken from the same ASJ-01 wording PDF | (inside `policies/ASJ-01/wording.pdf`) | `IRDAI:List-I` |
| `GHC-01` | none — deliberately absent so scenario 6 finds no grounding clause | — | — |

## Section-id convention

Wording numbering is written as dotted lowercase: `4.1(i)` → `4.1.i`, Note 2 under 4.1 → `4.1.note2`,
`6.3(i)` → `6.3.i`. The ids in `data/policies.json` (`clause_refs`) and every `expected.json` must match
the chunks `chunk_wording` produces.

## Clauses the scenarios rely on (check against the PDF)

| Clause id | What it says |
| --- | --- |
| `ASJ-01:4.1.i` | Room rent: 2% of sum insured, max ₹5,000/day |
| `ASJ-01:4.1.ii` | ICU / ICCU: 5% of sum insured, max ₹10,000/day |
| `ASJ-01:4.1.note2` | Above the room/ICU limit, other expenses except medicines are cut in the same proportion |
| `ASJ-01:4.3` | Cataract: 25% of SI or ₹40,000 per eye, whichever is lower |
| `ASJ-01:4.6` | Modern treatments: up to 50% of SI |
| `ASJ-01:6.1` | Pre-existing diseases: 36 months |
| `ASJ-01:6.2` | First 30 days: illness excluded, accidents covered |
| `ASJ-01:6.3.i` | Specified diseases (hernia, cataract, …): 24 months |
| `ASJ-01:6.3.ii` | Joint replacement, age-related osteoarthritis / osteoporosis: 48 months |
| `ASJ-01:9.3` | Co-payment: 5% of each admissible claim |
| `IRDAI:List-I` | Non-payable items (gloves, mask, laundry, telephone, …) |
