# PRD: Paytm AI Teammate (Track 3)

## 1. Problem statement (given)
> Design an AI teammate that can go beyond answering questions and deliver measurable outcomes in sales or customer service. The AI should understand context, make decisions, take actions, and work alongside human teams. How might we build an AI teammate that can independently handle a customer-service or sales workflow end to end, resolving issues, taking actions across systems, and escalating to humans only when needed?

## 2. Chosen workflow
**Customer service for Paytm merchants.** Merchants raise support issues in chat. The teammate resolves them, or hands them to a human with a full case summary.

Why this workflow: merchant support is high-volume and repetitive. Most tickets are lookups and routine actions that follow clear rules, which suits an agent. A small share is risky (large refunds, KYC, fraud), which makes the escalation logic a real feature and not a formality.

## 3. Users
| User | Need |
|---|---|
| Merchant (kirana, salon, clinic, restaurant owner) | A fast, correct answer and an action taken, not a link to an FAQ |
| Support agent (human) | Receives only the cases the AI cannot or should not close, with context and a recommendation |
| Support lead | Sees measurable outcomes: how many tickets the AI closed, how fast, how many escalated and why |

## 4. In scope (MVP)
Ticket categories, each with real actions:
1. **Settlement delay:** look up the settlement, explain the cause, notify the merchant of the expected date.
2. **Payment failed but customer debited:** look up the transaction and trigger a refund within the policy limit.
3. **Refund request:** refund a successful transaction when allowed by policy.
4. **Soundbox or device fault:** check device status and raise a replacement or a diagnostic request.
5. **Must-escalate cases:** refund above the limit, settlement on hold for KYC or risk, suspected fraud, abusive or distressed merchant, anything the AI is not confident about.

Surfaces:
- Merchant chat (web).
- Ops console: live ticket list, the agent's reasoning and tool calls, escalation queue, metrics.

## 5. Out of scope
Real Paytm APIs, real payments, voice, multilingual UI, authentication for merchants (a demo merchant picker is used), sales workflow.
All "systems" (payments, settlements, devices, notifications) are **simulated** and must be labelled as such in the demo.

## 6. Success metrics
These are computed from the database and the eval harness. No number is invented.
| Metric | Definition | Demo target |
|---|---|---|
| Auto-resolution rate | Tickets closed by AI with no human / all tickets | at least 70% on the eval set |
| Correct-decision rate | Eval scenarios where outcome (resolve vs escalate) matches expected | at least 90% |
| Unsafe-action rate | Actions that violated a guardrail and were executed | 0 |
| Escalation quality | Escalations that include summary, attempted steps, recommendation | 100% |
| Time to resolution | Ticket created to closed | under 30 seconds for AI-closed tickets |

## 7. Risks
- LLM misuse of tools: mitigated by deterministic guardrails (see AGENT_DESIGN).
- Shared database with COOLops: mitigated by a table prefix, a separate Alembic version table, and no changes to existing tables.
- Free-tier cold starts on Render: warm the service before the demo.
