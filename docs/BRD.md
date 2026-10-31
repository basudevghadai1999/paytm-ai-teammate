# Business Requirements Document (BRD): Paytm AI Teammate

| | |
|---|---|
| **Project** | Paytm AI Teammate (Hackathon Track 3: Autonomous AI Teammates) |
| **Version / date** | 0.2, 2026-10-31 (updated to match the built system: phone calls, email, domain scope) |
| **Status** | Built; being tested |
| **Evidence rule** | Every figure is labelled **[Fact]** (from the problem statement or project docs), **[Assumption]** (to be validated), or **[Target]** (a goal for the demo). No real Paytm data was used. |

## 1. Business problem

Paytm serves millions of small merchants (kirana stores, salons, clinics, restaurants). When a merchant has a problem, such as a settlement not arriving, a customer debited for a failed payment, a refund request, or a faulty Soundbox, they need an answer and an action quickly. For a small merchant, money stuck for a day directly affects the day's operations.

Support today is typically a queue of human agents. The problems with that model:

1. **Most tickets are repetitive.** They are lookups plus a routine action that follows clear rules. [Assumption: a large share of tickets are of this kind; to be validated against real ticket data.]
2. **Chatbots answer but do not act.** A bot that says "your settlement will arrive in 2 days" or links an FAQ still leaves the merchant waiting. The problem statement calls this out: AI should "go beyond answering questions" and "take actions across systems".
3. **Humans spend time on easy cases and lack context on hard ones.** Agents handle routine tickets, and when a hard case arrives they often have to re-ask the merchant what happened.
4. **Cost and speed do not scale with merchant growth.** More merchants means more tickets and more headcount, with slower response in peaks.

**Problem statement (given) [Fact]:** *How might we build an AI teammate that can independently handle a customer-service or sales workflow end to end, resolving issues, taking actions across systems, and escalating to humans only when needed?*

## 2. Proposed solution

An AI teammate that handles Paytm merchant support **by phone**, end to end:

- **Understands context:** speaks with the merchant in Hindi or English, and reads the merchant profile, recent transactions, settlements, device status and ticket history before acting.
- **Makes decisions:** applies a policy to decide between resolving, asking a question, or escalating.
- **Takes actions:** issues refunds within limits, raises device replacements, and emails the merchant a confirmation, through tools.
- **Works with humans:** escalates risky or unclear cases with a ready summary, what was already tried, and a recommended next step, and alerts human support at once by email when the case is an emergency (fraud, a hacked account, a legal threat, a distressed merchant).
- **Stays in its lane:** only Paytm merchant support. Anything else is politely declined and the call moves on.
- **Proves outcomes:** every step is logged, and the console reports resolution rate and time.

## 3. Business objectives and success measures

| # | Objective | Measure | Target for demo | Latest measured |
|---|---|---|---|---|
| O1 | Resolve routine tickets without a human | Auto-resolution rate on the resolvable eval scenarios | at least 70% [Target] | All resolvable scenarios resolved; about 40 to 45% over the whole set, which includes cases meant to escalate |
| O2 | Make the right decision (resolve, escalate, decline) | Correct-decision rate on the eval set | at least 90% [Target] | 12 of 12 |
| O3 | Never take an unsafe action | Executed actions that violated a guardrail | 0 [Target] | 0 |
| O4 | Give humans useful handoffs | Escalations with summary, attempted steps and recommendation | 100% [Target] | Enforced in code |
| O5 | Faster resolution | Time from ticket creation to close for AI-closed tickets | under 30 seconds [Target] | About 4 s in some runs, over 40 s in others; model latency varies |
| O6 | Stay in domain | Off-topic requests declined politely, real issues still handled | all eval cases pass [Target] | Passes (scenarios 11 and 12) |
| O7 | Emergencies reach a human | Emergency escalations that alert the support inbox | 100% [Target] | Covered by tests; live delivery to be checked |

The business case in production would be reduced cost per ticket and faster merchant recovery. Those numbers are not claimed here because no real baseline exists. They would be measured in a pilot (see Section 9).

## 4. Stakeholders

| Stakeholder | Interest |
|---|---|
| Merchants | Quick, correct resolution; money not stuck |
| Support agents | Fewer routine tickets; full context on escalations |
| Support leadership | Cost per ticket, resolution time, quality, auditability |
| Risk and compliance | No unauthorized money movement; clear audit trail |
| Hackathon judges | Autonomy, measurable outcomes, safe escalation, working demo |

## 5. Scope

**In scope (MVP):**
- Four ticket categories with real actions: settlement delay, failed-but-debited payment, refund request, device fault.
- A real **phone call** with the merchant (Bolna), in Hindi or English, and a real **confirmation email** (Resend).
- Mandatory-escalation cases: high-value refund, settlement on hold (KYC or risk), suspected fraud or legal threat, distressed or abusive merchant, low confidence.
- A merchant call screen and an ops console (tickets, call transcript, agent step trace, escalation queue, metrics).
- Out-of-scope requests handled gracefully; emergency alerts to a human support inbox.
- Audit log of every agent action.

**Out of scope:** real Paytm integrations, real money movement, an inbound support number (the demo dials the merchant), SMS (the app emails instead), multi-language UI, merchant authentication, sales workflow, machine-learning model training.

The downstream systems (payments, settlements, devices) are **simulated**, and the demo must say so. The call and the email are real.

## 6. Business rules

| ID | Rule |
|---|---|
| BR-01 | The AI may refund automatically only up to a configurable limit (default INR 2,000). |
| BR-02 | Refunds above the limit must be escalated to a human with a recommendation. |
| BR-03 | A transaction can be refunded only once. |
| BR-04 | Refunds are allowed only for a successful transaction, or a failed transaction where the customer was debited. |
| BR-05 | Settlements on hold for KYC or risk must be escalated; the AI does not release them. |
| BR-06 | The AI acts only on the merchant who raised the ticket. |
| BR-07 | Fraud claims, legal threats, and abusive or distressed merchants are escalated immediately, and the human support inbox is alerted by email. |
| BR-08 | The AI asks the merchant at most one clarifying question per missing detail, then escalates if still unclear. |
| BR-09 | The AI never states that an action was completed unless a system result confirms it. |
| BR-10 | Every action, allowed or blocked, is logged with its inputs and result. |
| BR-11 | The AI only handles Paytm merchant support. Other requests are declined politely once, then the ticket is closed as out of scope; they are never escalated to a human for being off-topic. |
| BR-12 | The AI says a confirmation was emailed only if an email was actually sent. |
| BR-13 | The demo can call only numbers on an allowlist, at a limited rate, so the call endpoint cannot be used to dial strangers. |
| BR-14 | The AI never asks for OTPs, PINs, passwords or card numbers. |
| BR-15 | A call that ends before resolution is escalated, and a call where the merchant spoke of fraud or legal action that the AI missed is reopened and escalated after the call. |

## 7. Assumptions, constraints and dependencies

**Assumptions:** merchant issues in the chosen categories are resolvable from the data and tools available; the LLM can follow tool-calling instructions reliably when guardrails sit in code; judges value a working end-to-end flow over breadth.

**Constraints:** hackathon timeline; free-tier hosting (cold starts of up to a minute); one shared database with another project (COOLops); simulated payments, settlements and devices; one Bolna agent per app.

**Dependencies:** NVIDIA API (`nemotron-3.5-super-vl-120b-a12b`) with Groq (`openai/gpt-oss-120b`) as a fallback, and their availability, latency and rate limits; Bolna (voice, Sarvam, Deepgram); Resend (email, verified domain); Supabase Postgres; Render hosting. Supabase and Render are reused from COOLops.

## 8. Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Model calls a tool incorrectly or is manipulated by the merchant's text | Wrong or unauthorized action | Guardrails in code, merchant id bound server-side, injection scenario in evals |
| Model says an action happened when it did not | Merchant misled | Reply built from tool results, BR-09 |
| Shared DB with COOLops | Data or migration collision | `tm_` prefix, own Alembic version table, no changes to existing tables |
| Model outage, rate limit or slow responses during demo | Silence on a call, or a failed demo | Retries, automatic escalation when the model is unavailable, a fallback provider, a pre-recorded fallback |
| Speech recognition errors (Hindi, mixed speech, noise) | Wrong or missed details | Hindi transcriber with Paytm keywords; the email is typed, not spoken; the agent confirms before acting; unclear cases escalate |
| The public call endpoint is abused to dial strangers or run up cost | Spam and cost | Number allowlist, rate cap, calls off in production unless configured |
| Email accepted by Resend but not delivered | Merchant never sees the confirmation | Say "emailed" only on acceptance, monitor delivery events in a later phase |
| An emergency is missed by the agent | Fraud or distress not escalated | Prompt rule, post-call transcript screen (English and Hindi), alert email to support |
| Free-tier cold start | Slow first response | Warm up before the demo |
| Results look better than they are because data is simulated | Overclaiming | State clearly what is simulated; report only measured eval numbers |

## 9. Path to production (not part of the hackathon build)

1. Integrate with real merchant, payments, settlement and device APIs behind the same tool interface.
2. Add merchant authentication and consent, an inbound support number, and call-recording disclosure.
3. Run in **shadow mode** on real tickets: the AI proposes, humans act, and agreement is measured.
4. Pilot with a limited ticket category and low refund limit, then widen as measured accuracy supports it.
5. Establish the real baseline (cost per ticket, resolution time) and compare.

## 10. Acceptance criteria for the hackathon

- A live phone call resolves at least three ticket types end to end with visible actions, and a confirmation email arrives.
- One case escalates with a complete handoff package and the guardrail visibly blocks the unsafe action.
- The eval run reports the metrics in Section 3, with unsafe actions equal to 0.
- An emergency reaches a human with an alert email, and an off-topic request is declined politely.
- The live URL works and the simulated systems are disclosed.
