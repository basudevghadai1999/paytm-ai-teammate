# Functional Requirements Document (FRD): Paytm AI Teammate

Companion to [BRD.md](BRD.md). Updated to match the built system (phone calls, email, domain scope). Business rules (BR-xx) are defined there. Design detail is in [AGENT_DESIGN.md](AGENT_DESIGN.md) and [ARCHITECTURE.md](ARCHITECTURE.md).

Priority: **M** = must have, **S** = should have, **C** = could have (stretch).

## 1. Actors

| Actor | Description |
|---|---|
| Merchant | Receives the call, describes the issue, gets a confirmation email |
| AI teammate | The agent that handles tickets |
| Support agent | Human who handles escalations in the ops console |
| Support lead | Views metrics |
| Voice platform (Bolna) | Places the call, runs speech in and out, and calls our tool endpoints mid-call |
| Email service (Resend) | Sends confirmations, acknowledgements and emergency alerts |
| Simulated systems | Payments, settlements, devices (implemented as `tm_*` tables and tool functions) |

## 2. Functional requirements

### 2.1 Merchant call
| ID | Requirement | Pri |
|---|---|---|
| FR-101 | The merchant can pick a demo merchant profile (no login in the MVP). | M |
| FR-102 | The merchant enters a phone number (with country code) and an email address for the confirmation, and presses *Call me*; the teammate calls that number. The email is required and validated. | M |
| FR-103 | The screen shows the call state (calling, on the call, finished), each step the agent takes in plain words, the confirmation, and the transcript afterwards. | M |
| FR-104 | During the call the merchant can answer the agent's question and the agent continues on the same ticket. | M |
| FR-105 | When escalated, the merchant is told a person will follow up, and receives an acknowledgement email. | M |
| FR-106 | Voice in Hindi and English: the transcriber and the voice are set to Hindi, and the agent mirrors the merchant's language. | M |
| FR-107 | An inbound number the merchant can dial. | C |
| FR-108 | On an emergency, the live call is transferred to a human support number when one is configured (FR-1007). | M |

### 2.2 Agent behaviour
| ID | Requirement | Pri |
|---|---|---|
| FR-201 | On each ticket, the agent loads merchant profile, recent transactions, settlements, device status and previous tickets. | M |
| FR-202 | The agent classifies the ticket (settlement delay, failed payment, refund, device fault, other) and stores the category. | M |
| FR-203 | The agent decides among resolve, ask merchant, or escalate, following the decision policy in AGENT_DESIGN. | M |
| FR-204 | The agent uses tools for every fact and action; it never invents amounts, dates or statuses (BR-09). | M |
| FR-205 | The agent asks at most one clarifying question per missing detail (BR-08). | M |
| FR-206 | The agent stops after a configurable step limit (default 8) and escalates automatically if no terminal action was taken. A call that ends before the ticket is resolved or escalated also escalates (`call_dropped`). | M |
| FR-207 | The agent escalates immediately on fraud, a hacked account, legal threat, or abusive or distressed language (BR-07). | M |
| FR-209 | The agent only handles Paytm merchant support. An off-topic request is declined once without using a tool and without answering it; a second off-topic message closes the ticket as `out_of_scope`; it is never escalated to a human for being off-topic (BR-11). | M |
| FR-210 | A message that mixes an off-topic part and a real issue gets the real issue handled and only the rest declined. | M |
| FR-208 | The final reply to the merchant is built from tool results and states only confirmed outcomes. | M |

### 2.3 Tools and actions
| ID | Requirement | Pri |
|---|---|---|
| FR-301 | `get_settlement_status`: returns the merchant's recent settlements with status, expected date and hold reason. | M |
| FR-302 | `get_transaction` and `list_recent_transactions`: return transactions that belong to the ticket's merchant only. | M |
| FR-303 | `get_device_status`: returns the merchant's device and status. | M |
| FR-304 | `initiate_refund`: refunds a transaction, subject to BR-01 to BR-04; on success marks the transaction `refunded`. | M |
| FR-305 | `raise_device_replacement`: creates a replacement request only when the device is faulty. | M |
| FR-306 | `send_notification`: sends the merchant a confirmation email at the address on the ticket and records it. Without an address it is only logged, and the result says so; if the email fails, the call is a blocked action so the agent cannot claim it was sent (BR-12). | M |
| FR-307 | `ask_merchant` (chat path only): posts a clarifying question and sets the ticket to `awaiting_merchant`. On a call the agent asks aloud. | M |
| FR-308 | `resolve_ticket`: closes the ticket with a category and summary, `resolved_by = ai`. | M |
| FR-309 | `escalate_to_human`: creates an escalation and sets the ticket to `escalated`. | M |
| FR-310 | The merchant id is never a tool parameter; it is taken from the ticket (BR-06). | M |
| FR-311 | The same write action on the same ticket and transaction is not executed twice (idempotency). | S |

### 2.4 Guardrails
| ID | Requirement | Pri |
|---|---|---|
| FR-401 | A refund above the configured limit is refused by the tool with an error telling the agent to escalate (BR-02). | M |
| FR-402 | A second refund on the same transaction is refused (BR-03). | M |
| FR-403 | A refund on an ineligible transaction state is refused (BR-04). | M |
| FR-404 | A replacement on a healthy device is refused. | M |
| FR-405 | Every refused action is logged with `allowed = false` and its reason (BR-10). | M |
| FR-406 | The refund limit is configurable by environment variable. | M |

### 2.5 Escalation and human handoff
| ID | Requirement | Pri |
|---|---|---|
| FR-501 | An escalation stores: reason, one-paragraph summary, steps attempted, recommended next action. | M |
| FR-502 | The ops console lists open escalations with their summary and the full action trace. | M |
| FR-503 | A support agent can resolve an escalation with a note, which closes the ticket with `resolved_by = human` and messages the merchant. | M |
| FR-504 | A support agent can approve a recommended refund from the console, executed through the same guarded tool path. | S |

### 2.6 Ops console
| ID | Requirement | Pri |
|---|---|---|
| FR-601 | List all tickets with merchant, category, status, who resolved, and created and closed time. | M |
| FR-602 | Ticket detail shows the conversation and every agent step (tool, arguments, result, allowed or blocked). | M |
| FR-603 | Live update of ticket status and steps (polling is acceptable). | S |
| FR-604 | Metrics view: auto-resolution rate, escalation rate with reasons, average time to resolution, blocked actions count. | M |
| FR-605 | Charts for the metrics. | C |

### 2.7 Data and seed
| ID | Requirement | Pri |
|---|---|---|
| FR-701 | A seed set of demo merchants, transactions, settlements and devices covers every eval scenario. | M |
| FR-702 | The seed can be reset to a known state for repeatable demos and evals. | M |
| FR-703 | All data lives in new `tm_*` tables only; existing COOLops tables are not modified. | M |

### 2.8 Evaluation
| ID | Requirement | Pri |
|---|---|---|
| FR-801 | An eval script runs the 12 scenarios in DEMO_AND_EVALS against the real model and compares outcomes with expectations. A scenario that escalated only because the model was unavailable is not counted as a pass. | M |
| FR-802 | The script prints auto-resolution rate, correct-decision rate, blocked or unsafe action counts and average time. | M |
| FR-803 | The scenarios include a prompt-injection attempt, a double-refund attempt, and two off-topic cases. | M |

### 2.9 Voice channel
| ID | Requirement | Pri |
|---|---|---|
| FR-901 | `POST /api/v1/calls` dials the merchant through Bolna and creates a voice ticket and a call record. Outside development it only dials numbers on `DEMO_CALL_ALLOWLIST` (empty means off), at most 3 calls a minute (BR-13). If Bolna fails, no ticket is left behind. | M |
| FR-902 | The Bolna agent acts only through `POST /api/v1/voice/tools/{tool}`, which requires a bearer secret and runs the same guarded tools as the chat path. | M |
| FR-903 | Each tool call is verified with Bolna: the call must be a live execution of this app's agent, and a call this app placed. The merchant is taken from the call record, never from what the caller says (BR-06). | M |
| FR-904 | A ticket that is resolved or escalated accepts no further tool calls. | M |
| FR-905 | The Bolna status webhook is re-verified with Bolna before anything is stored; it records status, duration and transcript, and escalates a call that ended unresolved. | M |
| FR-906 | `python -m app.apply_agent` writes the voice prompt, tools, webhook, Hindi transcriber and Hindi voice into this app's Bolna agent, and never into another app's agent. | M |
| FR-907 | The agent never asks for OTPs, PINs, passwords or card numbers (BR-14). | M |

### 2.10 Email, emergencies and alerts
| ID | Requirement | Pri |
|---|---|---|
| FR-1001 | When a ticket resolves, the code itself emails the merchant an acknowledgement, unless one was already sent on the ticket or the ticket was closed as out of scope. | M |
| FR-1002 | When a ticket escalates, the code emails the merchant an acknowledgement with the ticket number. | M |
| FR-1003 | A mail failure never blocks resolving or escalating a ticket. | M |
| FR-1004 | A reply that mentions an email or SMS is replaced by the confirmed outcomes unless an email was really sent (BR-12). | M |
| FR-1005 | An emergency escalation (`fraud_or_legal`, `abusive_or_distressed`) emails the human support inbox (`SUPPORT_ALERT_EMAIL`) an urgent message with the summary, steps attempted and recommended action, and marks the escalation as alerted. | M |
| FR-1006 | After every call, the merchant's side of the transcript is screened for fraud or legal wording in English and Hindi. If the agent had not escalated, the ticket is reopened and escalated, and support is alerted (BR-15). The agent's own words are not screened. | M |
| FR-1007 | With `SUPPORT_TRANSFER_NUMBER` set, an emergency escalation on a live call is transferred to that number through Bolna's transfer tool. Other escalations stay callbacks. The destination is fixed in the agent's configuration, the app records only what Bolna reports (requested, attempted, transferred, failed), and a failed or unanswered transfer emails support to call the merchant back now. | M |

## 3. Key workflows

Each workflow below is a phone call. The merchant speaks; the agent's words are spoken too.

**W1: Failed payment, customer debited (auto-resolve)**
1. Merchant: "Customer paid but I did not get it."
2. Agent lists recent transactions, finds a failed one with the customer debited, amount at most the limit.
3. Agent calls `initiate_refund`, then `send_notification` (a real email), then `resolve_ticket`.
4. Agent tells the merchant the refund was initiated and that a confirmation is in their email. The ticket is `resolved`, `resolved_by = ai`.

**W2: Vague message (clarify, then resolve)**
1. Merchant: "Where is my money?"
2. Agent finds two possible settlements and asks which one, by amount or date. On the chat path this is `ask_merchant` and the ticket is `awaiting_merchant`.
3. Merchant answers. Agent looks up the settlement, explains, sends the confirmation, then resolves.

**W3: High-value refund (escalate)**
1. Merchant: "Refund this 15,000 payment."
2. Agent attempts `initiate_refund`. The guardrail refuses it and logs `allowed = false`.
3. Agent calls `escalate_to_human` with the reason, summary, attempts and recommendation; the merchant is told a person will follow up and gets an acknowledgement email.
4. Support agent reviews in the console and resolves. The merchant is notified.

**W4: Emergency (escalate and alert)**
1. Merchant: "Someone hacked my account and took 20,000. I will go to the police."
2. Agent stops, calls `escalate_to_human` with reason `fraud_or_legal`, and tells the merchant a person will call back.
3. The code emails the urgent case package to the human support inbox and an acknowledgement to the merchant.
4. If the agent had missed it, the post-call transcript screen reopens the ticket and escalates it.

**W5: Off-topic (decline, then carry on or close)**
1. Merchant: "What's the weather today? Also, where is my settlement?"
2. Agent declines the weather politely, handles the settlement as in W1, and closes the ticket normally.
3. If the whole call is off-topic, the agent redirects once and, if the merchant continues, closes the ticket as `out_of_scope`. No human is involved.

## 4. API requirements
Endpoints are listed in ARCHITECTURE.md. Requirements: JSON bodies, validated input, clear error codes, no secrets or stack traces in responses, `/readyz` checks the database.

## 5. Non-functional requirements
| ID | Requirement |
|---|---|
| NFR-01 | AI-closed tickets complete in under 30 seconds in normal conditions. |
| NFR-02 | Every agent action is auditable from the database alone. |
| NFR-03 | Secrets come from environment variables and are never committed or logged. |
| NFR-04 | Logs exclude merchant phone numbers, email addresses and message content. Only the last four digits of a phone number are stored, and the contact email is never returned by the API. |
| NFR-05 | If the LLM is unavailable or returns invalid output, the ticket is escalated with the reason, not left hanging. Rate limits are waited out with retries first. |
| NFR-06 | Migrations are reversible and affect only `tm_*` tables. |
| NFR-07 | The UI works on a laptop screen and is usable at phone width. |

## 6. Traceability
| Business objective | Requirements |
|---|---|
| O1 Resolve routine tickets | FR-201 to FR-208, FR-301 to FR-309 |
| O2 Right decision | FR-203, FR-207, FR-801, FR-802 |
| O3 No unsafe action | FR-310, FR-401 to FR-405, FR-803 |
| O4 Useful handoffs | FR-501 to FR-503 |
| O5 Faster resolution | FR-206, FR-604, NFR-01 |
| O6 Stay in domain | FR-209, FR-210, FR-803 |
| O7 Emergencies reach a human | FR-207, FR-1005, FR-1006 |

## 7. Open questions
1. Is the INR 2,000 refund limit appropriate for the demo story? (It is a configurable assumption.)
2. Does the console need human approval of the recommended refund (FR-504) in the demo, or only resolve with a note? (Not built: over-limit refunds are blocked by design.)
3. Should the merchant dial an inbound number (FR-107) instead of receiving a call?
4. A tighter latency budget: a faster model, or thinking mode off at some cost in accuracy?
