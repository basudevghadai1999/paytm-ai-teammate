# PRD: Paytm AI Teammate (Track 3)

## 1. Problem statement (given)
> Design an AI teammate that can go beyond answering questions and deliver measurable outcomes in sales or customer service. The AI should understand context, make decisions, take actions, and work alongside human teams. How might we build an AI teammate that can independently handle a customer-service or sales workflow end to end, resolving issues, taking actions across systems, and escalating to humans only when needed?

## 2. Chosen workflow
**Customer service for Paytm merchants, by phone.** A merchant gets a call from the teammate (or, in production, would call it), explains the issue, and the teammate resolves it or hands it to a human with a full case summary. A confirmation arrives by email.

Why this workflow: merchant support is high-volume and repetitive. Most tickets are lookups and routine actions that follow clear rules, which suits an agent. A small share is risky (large refunds, KYC, fraud), which makes the escalation logic a real feature and not a formality. Why a call: small merchants are busy at the counter and often prefer to speak, in Hindi or English, over typing.

## 3. Users
| User | Need |
|---|---|
| Merchant (kirana, salon, clinic, restaurant owner) | A fast, correct answer and an action taken, in their own language, with a written confirmation |
| Support agent (human) | Receives only the cases the AI cannot or should not close, with context and a recommendation, and an immediate alert for emergencies |
| Support lead | Sees measurable outcomes: how many tickets the AI closed, how fast, how many escalated and why |

## 4. In scope (MVP)
Ticket categories, each with real actions:
1. **Settlement delay:** look up the settlement, explain the cause, send a confirmation of the expected date.
2. **Payment failed but customer debited:** look up the transaction and trigger a refund within the policy limit.
3. **Refund request:** refund a successful transaction when allowed by policy.
4. **Soundbox or device fault:** check device status and raise a replacement.
5. **Must-escalate cases:** refund above the limit, settlement on hold for KYC or risk, suspected fraud, a hacked account, a legal threat, an abusive or distressed merchant, anything the AI is not confident about. Emergencies also alert the human support inbox by email.
6. **Out-of-scope requests:** declined politely, once, then closed; never escalated to a human just for being off-topic.

Surfaces:
- **Merchant call:** pick a demo merchant, enter a phone number and an email for the confirmation, and receive the call. Live status, each step, the transcript.
- **Ops console:** live ticket list, the agent's tool calls and the call transcript, escalation queue, metrics.

Channels: a real phone call (Bolna, Hindi and English) and a real confirmation email (Resend).

## 5. Out of scope
Real Paytm APIs, real payments, inbound calling number, SMS (the app emails instead), merchant authentication (a demo merchant picker and a number allowlist are used), multilingual UI, sales workflow.
Payments, settlements and devices are **simulated** and must be labelled as such in the demo. The call and the email are real.

## 6. Success metrics
These are computed from the database and the eval harness. No number is invented.
| Metric | Definition | Demo target | Latest measured |
|---|---|---|---|
| Auto-resolution rate | Tickets closed by AI with no human / in-domain tickets | at least 70% on the resolvable scenarios | All resolvable scenarios resolved; about 40 to 45% over the whole set, which includes cases meant to escalate |
| Correct-decision rate | Eval scenarios where the outcome matches expected | at least 90% | 12 of 12 |
| Unsafe-action rate | Actions that violated a guardrail and were executed | 0 | 0 |
| Escalation quality | Escalations that include summary, attempted steps, recommendation | 100% | Enforced in code |
| Time to resolution | Ticket created to closed, AI-closed tickets | under 30 seconds | About 4 seconds in some runs, over 40 in others (model latency varies) |

## 7. Risks
- LLM misuse of tools: mitigated by deterministic guardrails (see AGENT_DESIGN).
- Shared database with COOLops: mitigated by a table prefix, a separate Alembic version table, and no changes to existing tables.
- Free-tier cold starts on Render: warm the service before a call.
- Speech recognition errors, especially for Hindi and mixed speech: an email address is typed in the form, not spoken; the agent never asks for OTPs or card details.
- A public "call me" endpoint could be abused to dial strangers: outside development only allowlisted numbers can be called, with a per-minute cap.
- Email accepted by Resend is not proof of delivery.
- Keyword screens for emergencies can miss unusual phrasing: they are a safety net behind the agent's own judgement, not a replacement for it.
