# ClaimLens — 03 Features & Scope

## Scope
One cashless or reimbursement claim at a time, built from synthetic data and public documents. Real patient data, live insurer systems and production hosting are out.

| In scope | Out of scope |
| --- | --- |
| 15–20 synthetic claims (claim text + bill as CSV or JSON) | Real patient or hospital data |
| 3–4 public policy wordings + IRDAI rule excerpts as the RAG corpus | Live insurer, TPA or NHCX integration |
| Line-item payable calculation in ₹ | Payments, settlement or bank transfers |
| Four verdicts: approve, partial approve, reject, escalate | Scanned or handwritten bill OCR (stretch only) |
| Human review loop for high-value or low-confidence claims | Login, multi-user accounts, cloud deployment |
| English output | Regional-language output (stretch only) |

**Input:** a claim message (free text) + a bill with line items + the policy id.

**Output per claim:**
- verdict;
- payable amount;
- deduction table (item, amount cut, reason, clause id);
- fraud risk score with reasons;
- clause behind the decision;
- escalation reason, when routed to a human.

**Working assumptions (config.yaml, tunable):**
- Claims above ₹2,00,000 always go to a human.
- Risk score ≥ 60 escalates.
- No retrieved clause above the similarity threshold → never auto-decided.

## Feature list
Build must-haves first — they alone satisfy the brief and rubric. Add should-haves only after all seven scenarios pass. Track status in 05-progress.

### Must-have (meets the assignment)
- [ ] M1 Claim intake from free text + bill file into a validated, structured record
- [ ] M2 Halt with a clear message when policy id or claimed amount is missing, rather than guessing
- [ ] M3 RAG over policy wordings and IRDAI rules, filtered by policy id, returning clause ids and coverage limit
- [ ] M4 Deterministic payable calculation: non-payable items, room-rent proportionate deduction, co-pay, sub-limits, sum-insured cap
- [ ] M5 Over-claiming flag when claimed exceeds computed payable by a set margin
- [ ] M6 Fraud risk score (0–100) with named reasons from rules and prior-claim memory
- [ ] M7 Parallel fan-out of Policy and Fraud agents, then fan-in at the Adjudication Manager
- [ ] M8 Verdict of approve, partial approve, reject or escalate, with payout and governing clause
- [ ] M9 Citation guard: a verdict citing a clause not in the retrieved set is blocked and escalated
- [ ] M10 Escalation routing for high value, high risk, low confidence or no grounding clause
- [ ] M11 Human-in-the-loop: human verdict written back into the record and closes the claim (group-of-3 add-on)
- [ ] M12 Shared claim-state record that every agent reads and writes
- [ ] M13 Append-only JSONL run log of every agent step
- [ ] M14 Demo notebook that prints the full multi-agent trace
- [ ] M15 Test file covering at least three scenarios

### Should-have (raises the presentation mark)
- [ ] S1 Deduction table in the output: item, amount cut, reason, clause
- [ ] S2 Grievance or query-reply letter draft for contestable deductions
- [ ] S3 Missing-document check (discharge summary, final bill, investigation reports)
- [ ] S4 Streamlit screen: pick a claim, watch the trace, approve or override as the human reviewer
- [ ] S5 Retrieval check: hit@3 on 20 hand-labelled questions
- [ ] S6 Accuracy table: predicted vs expected payable on all test claims

### Nice-to-have (only if time remains)
- [ ] N1 PDF bill parsing with `pdfplumber`
- [ ] N2 Plain-language Hindi or Punjabi summary of the verdict for the patient
- [ ] N3 "What would another policy pay?" comparison for the same bill
- [ ] N4 Pre-authorisation mode: flag missing items before the claim is submitted

## Demo scenarios and tests
Scenarios 1–4 are the live demo; all seven go into `tests/test_scenarios.py`. Amounts are illustrative — set real expected values from the limits typed into `policies.json`.

| # | Scenario | Claim set-up | Expected result |
| --- | --- | --- | --- |
| 1 | Clean approval | Appendectomy, ₹85,000, room within cap, no risk flags | Approve; payout = claimed minus non-payable consumables; clause cited |
| 2 | Partial: room-rent breach | Single room above the policy's daily cap | Partial approve; proportionate deduction shown line by line with the room-rent clause |
| 3 | Reject: waiting period | Planned surgery for a condition still inside its waiting period | Reject; waiting-period clause cited |
| 4 | High value → human | Cardiac procedure, ₹4,50,000 | Escalate; reviewer approves with a note; status becomes closed |
| 5 | Fraud signal | Claim 20 days after policy start; bill number repeats a prior claim | Escalate with risk score ≥ 60 and both reasons listed |
| 6 | Honest failure: no grounding | Policy id with no matching clause above threshold | No auto-decision; escalate with "no grounding clause found" |
| 7 | Missing data | Claim text with no amount | Intake halts and asks for the amount; no downstream agent runs |

**Test layers**
1. Unit tests on deterministic tools (`room_rent_deduction`, `compute_payable`, `score_risk`) with exact rupee assertions.
2. Scenario tests: full workflow; assert verdict, payout and that every cited clause id exists.
3. Log test: run log only grows, and every agent appears in each trace.

## Honest failure for the README
An early design let the model compute the room-rent deduction and it produced wrong totals; the fix moved every rupee calculation into `compute_payable` with unit tests. Second candidate: scenario 6 — the system refuses to decide when no clause is retrieved, and escalates instead.
