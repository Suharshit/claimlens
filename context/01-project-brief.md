# ClaimLens — 01 Project Brief

**Course:** CSE476 CA2 Project 2 · **Base question:** Q1 (insurance claim adjudication), tuned to Indian cashless health claims
**Build window:** ~4 weeks · **Team:** 3 members (2-member fallback noted in 05-progress)

## One-line pitch
ClaimLens reads a health-insurance claim and its hospital bill, checks both against the policy wording and IRDAI rules, and returns one of four verdicts — approve, partial approve, reject or escalate — with the payout and the clause behind every rupee deducted.

## Problem
Indian health insurers left about ₹26,000 crore of claimed money unpaid in FY24: ₹15,100 crore disallowed as deductions and ₹10,937 crore repudiated (Outlook Business, citing IRDAI). Hospital desks and patients rarely know which deductions are correct, because the rules are spread across policy wordings, sub-limits and IRDAI's lists of non-payable items.

## Who it helps
- Hospital insurance-desk (TPA desk) staff checking a claim before submission or after settlement.
- Policyholders who want to know whether a deduction was fair.

## Goal of the class version
A working multi-agent prototype that runs on synthetic claims, meets every CSE476 common requirement and the Q1 brief, and has measurable accuracy on a small claim set.

## How ClaimLens maps to the CSE476 Q1 brief

| CSE476 Q1 requirement | How ClaimLens meets it |
| --- | --- |
| Intake Agent turns raw claim text into a structured record | Claim text + bill → claim id, incident type, amount, policy id, bill line items |
| Policy Retrieval Agent runs RAG, returns clauses and coverage limit | RAG over policy wordings and IRDAI rules, filtered by policy id |
| Fraud Signal Agent scores risk rules and prior-claim memory | Rule checks + a prior-claims store; score 0–100 with reasons |
| Cost Assessment Agent estimates a fair payout, flags over-claiming | Deterministic maths: non-payable items, room-rent proportionate deduction, co-pay, sub-limits, sum-insured cap |
| Adjudication Manager decides approve / reject / escalate from clauses | Adds partial approve; every verdict cites clause ids that exist in the corpus |
| Fan-out / fan-in with human routing | Policy and Fraud agents run in parallel, Cost runs once limits are in, the Manager fans in |
| Group-of-3 add-on: high-value claim goes to a human | Human Review Desk; the human verdict is written back into the record to close the claim |

## CSE476 common requirements (must all be met)
- Built on Microsoft Agent Framework or Semantic Kernel.
- At least four agents, each its own module with one clear role (ClaimLens has six or seven).
- Every agent calls at least two real Python tools.
- RAG grounding from the provided document set.
- One shared state record read and written by every agent.
- Rubric: Implementation 10 · Presentation 10 · Viva 10.

## Deliverables
- Source code, one module per agent.
- README of at most two pages: agent roster, architecture and why it fits, tools per agent, what memory and retrieval hold, one honest failure handled.
- Runnable demo notebook that prints the multi-agent trace.
- Architecture diagram (`architecture.png`).
- Append-only run log.
- Test file with at least three scenarios (ClaimLens plans seven).

## Viva — every member must be able to explain
- Why the payable maths is deterministic (Python tools, not the LLM).
- How the citation guard works.
- Why the Cost agent waits for the Policy agent.
- What happens on each escalation trigger.

## Safety and data rules
- Synthetic claims only; never real patient records.
- Every output is labelled: educational prototype, not insurance, legal or medical advice.
- The final decision on any escalated or high-value claim belongs to a human.

## Related files
02-architecture-brief · 03-features-and-scope · 04-ui-and-stack-brief · 05-progress
