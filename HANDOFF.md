# ClaimLens — handoff (5 Nov 2026)

> Educational prototype — not insurance, legal or medical advice.

Deadline for both courses: **15 Nov 2026**. Source of truth for decisions and statuses: `context/05-progress.md`.

## Where things stand

**CSE476 build: every must-have works.** All seven scenarios run end to end and match the hand-worked
expected outcomes (266 tests, `demo.ipynb` shows 7/7). The remaining items are decisions, polish and
the presentation — no missing features.

| Scenario | Result |
| --- | --- |
| 1 Clean approval (CLM-0001) | approve ₹79,610 |
| 2 Room-rent breach (CLM-0002) | partial ₹48,925 |
| 3 Waiting period (CLM-0003) | reject ₹0, `ASJ-01:6.3.i` |
| 4 High value (CLM-0004) | escalate → reviewer approves ₹4,26,550 → closed |
| 5 Fraud signal (CLM-0005) | escalate, fraud score 75 (day 20 + reused bill) |
| 6 No grounding (CLM-0006) | escalate, "no grounding clause found" |
| 7 Missing amount (CLM-0007) | intake halts, nothing downstream runs |

**PRs merged on 4–5 Nov (all through CI):**

| PR | What |
| --- | --- |
| #6 | M4 + M5 cost maths and over-claim flag |
| #7 | M6 fraud tools: prior claims, waiting periods, risk score |
| #8 | M3 search: BM25 per policy, 0–1 score, IRDAI lists |
| #9 | M8–M11 decision rules, citation guard, escalation, human review desk |
| #10 | M7 agents + fan-out / fan-in workflow; Nagios + CI functional check on |
| #11 | M14 demo notebook, submission README, `architecture.png` |
| #13 | this handoff (`HANDOFF.md`) |
| #12 | Workflow on Microsoft Agent Framework (framework decision) |

## What only you can do (in order)

### 1. Sync your PC (5 min)

```powershell
cd E:\claimlens
git switch main
git pull
git branch -d feat/m4-cost-tools          # and any other merged local branches
python -m pip install -r requirements.txt
python -m pytest -q                        # expect 266 passed, 0–1 skipped
```

Your downloaded `data/corpus/policies/ASJ-01/wording.pdf` stays (it's git-ignored); with it present the
rebuild test runs too.

### 2. Framework — done ✅

Decided 5 Nov: **Microsoft Agent Framework** (`agent-framework-core==1.24.0`), merged as PR #12. `workflow.py`
is a `WorkflowBuilder` graph with fan-out / fan-in edge groups; agents and tools are unchanged. After
`git pull`, run `pip install -r requirements.txt` to get the package.

### 3. GitHub housekeeping (10 min) — Claude's session can't delete branches or change settings

1. Settings → General → tick **Automatically delete head branches**.
2. Delete the merged branches (Branches page, or):
   ```powershell
   git push origin --delete feat/m3-search feat/m6-fraud-tools feat/m7-workflow feat/m8-m11-decision-tools feat/m14-demo-docs docs/handoff feat/maf-workflow
   ```
3. Settings → Branches → add a rule for `main`: require a pull request and the status checks
   **App — lint, test (py3.11)**, **App — lint, test (py3.12)**, **Server install — lean deps, health, Nagios plugin**, **Infra — validate**.

### 4. INT333: first release + AWS deploy (½ day) — needs your AWS account

The framework is merged, so the release will contain it.

**Release v0.1.0 — done ✅** (5 Nov; tagged with plain git from PowerShell, since `make` only runs in WSL).

Next, from **WSL Ubuntu** (`wsl --install -d Ubuntu-22.04` once), follow `infra/README.md`: `aws configure` (ap-south-1) → copy `infra/terraform/example.tfvars` to
`terraform.tfvars` and set `admin_cidr` to your IP → `make up ENV=dev` (Terraform → Ansible → Puppet → Nagios)
→ sign the Puppet certificates → open Nagios through the SSH tunnel and check the new **scenario-1 functional
check** (POST `/claims/CLM-0001/run`) is green → rehearse the S11 runbook (stop the app, edit nginx) and
`make down` when done. Fill `deadline:` in `pipeline.config.yml` with the INT333 demo date.

### 5. LLM intake — built on `feat/m1-llm-intake` (2026-11-10)

Model lane: Groq (`qwen/qwen3.8-27b`) → NVIDIA build (`nvidia/nemotron-3.5-lightning-30b-a3b`) → rules.
The rules still extract first and decide any halt; the LLM is a second reading and the rules win every
disagreement (logged). Calls are capped below each free tier (`config.yaml` `llm:`), counted in
`state/llm_usage.json`. To finish:

1. Free keys: https://console.groq.com/keys and https://build.nvidia.com → put them in `.env`
   (copy `.env.example`; never commit `.env`).
2. `python -m tools.llm_client` → both keys show "set"; `python -m tools.llm_client ping` → both OK.
3. `pytest` (offline, must stay green) and `pytest -m live -s` (real calls, prints budget left).
4. Push the branch, open the PR, let `ci` go green, merge.
5. Optional: re-run `demo.ipynb` so the trace shows the `reconcile_fields` step with the budget left.
6. Servers: no key = rules only. To use the LLM there, put `GROQ_API_KEY` in Ansible Vault.

### 6. Submission pieces (1–2 days)

- **Sample run for the repo:** run `demo.ipynb` top to bottom, then force-add one clean run:
  `git add -f logs/run_log.jsonl state/CLM-0001.json state/CLM-0004.json` on a branch → PR.
- **README length:** check it is ≤ 2 pages when exported; if the diagram pushes it over, link
  `architecture.png` instead of embedding it.
- **Slides** (CSE476: AI focus; INT333: DevOps focus) — plans are in your Notion docs.
- **Viva prep** (`context/01-project-brief.md`): why money maths is deterministic; how the citation guard
  works (`verify_citations` + confidence = weakest cited clause); why Cost waits for Policy (limits posted
  first, `policy_limits → cost` edge); each escalation trigger (high value, fraud ≥ 60, no grounding,
  citation miss, confidence < 0.6).
- **Confirm with the instructor** that the Indian health-claims variant counts as Q1.

### 7. Should-haves, now unlocked (all seven scenarios pass) — Claude can build these

Quick wins first: **S6** accuracy table (predicted vs expected payable — the notebook's summary is most of
it), **S5** retrieval hit@3 on ~20 labelled questions, **S1** deduction table in the UI, then **S4** a one-page
Streamlit app (claim picker, live trace, decision card, Human Review Desk buttons) — about a day, and it
demos better than the simulated reviewer cell. **S2** grievance letters and **S3** missing-document check
only if time remains.

## Open questions left in `05-progress.md`

- Solo scope: keep or drop the Grievance Drafter (S2).
- Road ambulance: the wording pays it up to ₹2,000 (4.1.1.v) but List I names "AMBULANCE".
- Other 2–3 policy wordings (only needed for breadth; scenarios use ASJ-01 + GHC-01).
- INT333 demo date.

## Things Claude tried but couldn't do from its session

- Push the `v0.1.0` release tag (blocked) → step 4.
- Delete merged branches / change repo settings (proxy refuses) → step 3.
- Download PDFs (403 on both machines) → you downloaded the IFFCO wording; any further wordings likewise.
- AWS, Ansible, Puppet, Nagios on real servers (needs your AWS credentials) → step 4.
