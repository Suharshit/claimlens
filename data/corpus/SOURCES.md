# Corpus sources

Only public documents go into RAG. PDFs are git-ignored (`data/corpus/**/*.pdf`); the chunked text
built from them by `chunk_wording` is what the index uses. Download each file by hand (the build
machines can't reach these sites) and save it at the path shown.

| policy_id / list | Document | Save as | Clause ids |
| --- | --- | --- | --- |
| `ASJ-01` | IFFCO Tokio, Arogya Sanjeevani Policy — policy wording, UIN IFFHLIP20161V011920, 37 pages — <https://www.iffcotokio.co.in/content/dam/iffcotokio/iffco-pdf/policy-wordings-arogya-sanjeevani-policy.pdf> | `policies/ASJ-01/wording.pdf` | `ASJ-01:<section>`, e.g. `ASJ-01:4.1.i` |
| `IRDAI:List-I` … `List-IV` | Annexure-A Lists I–IV (not payable; subsumed into room / procedure / treatment charges) — the IRDAI standard lists, taken from the same ASJ-01 wording PDF | (inside `policies/ASJ-01/wording.pdf`) | `IRDAI:List-I` … `IRDAI:List-IV` |
| `GHC-01` | none — deliberately absent so scenario 6 finds no grounding clause | — | — |

## Chunks

`tools.retrieval_tools.build_index()` splits every PDF here into clause chunks and writes
`data/corpus/chunks.jsonl` (committed, so CI and servers never need the PDFs). Re-run it after adding
or replacing a PDF; `tests/test_retrieval.py` checks the committed file matches the PDF when the PDF is present.

## Section-id convention

The chunker follows the wording's own layout, written as dotted lowercase: heading `4.1.` → `4.1`;
roman item `i.` under it → `4.1.i`; `Note: 2.` under `4.1.1` → `4.1.1.note2`; `6.3` item `i.` → `6.3.i`;
Annexure-A `List I` → `IRDAI:List-I` (policy_id `IRDAI`); other annexures → `ASJ-01:annex-b`, `annex-c`.
The ids in `data/policies.json` (`clause_refs`) and every `expected.json` must exist in `chunks.jsonl`.

## Clauses the scenarios rely on (checked against the PDF, 4 Nov 2026)

| Clause id | Page | What it says |
| --- | --- | --- |
| `ASJ-01:4.1.i` | 6 | Room rent, boarding **and nursing**: 2% of sum insured, max ₹5,000/day |
| `ASJ-01:4.1.ii` | 6 | ICU / ICCU: 5% of sum insured, max ₹10,000/day |
| `ASJ-01:4.1.1.note2` | 6 | Above the room/ICU limit, all other expenses except medicines are cut in the same proportion |
| `ASJ-01:4.3` | 7 | Cataract: 25% of SI or ₹40,000 per eye, whichever is lower |
| `ASJ-01:4.6` | 7 | Listed modern treatments: up to 50% of SI |
| `ASJ-01:6.1` | 8 | Pre-existing diseases: 36 months |
| `ASJ-01:6.2.i` | 8 | First 30 days: illness excluded, accidents covered |
| `ASJ-01:6.3.i` | 9 | 24-month list (hernia, cataract, …) |
| `ASJ-01:6.3.ii` | 9 | 48 months: joint replacement, age-related osteoarthritis / osteoporosis |
| `ASJ-01:9.3` | 13 | Co-payment: 5% of each admissible claim |
| `IRDAI:List-I` | 20 | Non-payable items (laundry, telephone, gloves, mask, …) |
