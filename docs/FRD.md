# Functional Requirements Document (FRD): Paytm AI Teammate

Companion to [BRD.md](BRD.md). Business rules (BR-xx) are defined there. Design detail is in [AGENT_DESIGN.md](AGENT_DESIGN.md) and [ARCHITECTURE.md](ARCHITECTURE.md).

Priority: **M** = must have, **S** = should have, **C** = could have (stretch).

## 1. Actors

| Actor | Description |
|---|---|
| Merchant | Raises tickets and replies in chat |
| AI teammate | The agent that handles tickets |
| Support agent | Human who handles escalations in the ops console |
| Support lead | Views metrics |
| Simulated systems | Payments, settlements, devices, notifications (implemented as `tm_*` tables and tool functions) |

## 2. Functional requirements

### 2.1 Merchant chat
| ID | Requirement | Pri |
|---|---|---|
| FR-101 | The merchant can pick a demo merchant profile (no login in the MVP). | M |
| FR-102 | The merchant can submit a free-text issue, which creates a ticket. | M |
| FR-103 | The merchant sees the AI's reply and ticket status (`open`, `awaiting_merchant`, `resolved`, `escalated`). | M |
| FR-104 | The merchant can reply to a clarifying question and the agent resumes the same ticket. | M |
| FR-105 | When escalated, the merchant is told a human will follow up. | M |
| FR-106 | Voice input. | C |

### 2.2 Agent behaviour
| ID | Requirement | Pri |
|---|---|---|
| FR-201 | On each ticket, the agent loads merchant profile, recent transactions, settlements, device status and previous tickets. | M |
| FR-202 | The agent classifies the ticket (settlement delay, failed payment, refund, device fault, other) and stores the category. | M |
| FR-203 | The agent decides among resolve, ask merchant, or escalate, following the decision policy in AGENT_DESIGN. | M |
| FR-204 | The agent uses tools for every fact and action; it never invents amounts, dates or statuses (BR-09). | M |
| FR-205 | The agent asks at most one clarifying question per missing detail (BR-08). | M |
| FR-206 | The agent stops after a configurable step limit (default 8) and escalates automatically if no terminal action was taken. | M |
| FR-207 | The agent escalates immediately on fraud, legal threat, or abusive or distressed language (BR-07). | M |
| FR-208 | The final reply to the merchant is built from tool results and states only confirmed outcomes. | M |

### 2.3 Tools and actions
| ID | Requirement | Pri |
|---|---|---|
| FR-301 | `get_settlement_status`: returns the merchant's recent settlements with status, expected date and hold reason. | M |
| FR-302 | `get_transaction` and `list_recent_transactions`: return transactions that belong to the ticket's merchant only. | M |
| FR-303 | `get_device_status`: returns the merchant's device and status. | M |
| FR-304 | `initiate_refund`: refunds a transaction, subject to BR-01 to BR-04; on success marks the transaction `refunded`. | M |
| FR-305 | `raise_device_replacement`: creates a replacement request only when the device is faulty. | M |
| FR-306 | `send_notification`: records a simulated message to the merchant. | M |
| FR-307 | `ask_merchant`: posts a clarifying question and sets the ticket to `awaiting_merchant`. | M |
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
| FR-801 | An eval script runs the scenarios in DEMO_AND_EVALS against the real agent and compares outcomes with expectations. | M |
| FR-802 | The script prints auto-resolution rate, correct-decision rate, blocked or unsafe action counts and average time. | M |
| FR-803 | The scenarios include a prompt-injection attempt and a double-refund attempt. | M |

## 3. Key workflows

**W1: Failed payment, customer debited (auto-resolve)**
1. Merchant: "Customer paid but I did not get it."
2. Agent lists recent transactions, finds a failed one with the customer debited, amount at most the limit.
3. Agent calls `initiate_refund`, then `send_notification`, then `resolve_ticket`.
4. Merchant sees a reply stating the refund was initiated. Ticket is `resolved`, `resolved_by = ai`.

**W2: Vague message (clarify, then resolve)**
1. Merchant: "Where is my money?"
2. Agent finds two possible settlements, calls `ask_merchant` for the date or amount. Ticket is `awaiting_merchant`.
3. Merchant answers. Agent resumes, looks up the settlement, explains and notifies, then resolves.

**W3: High-value refund (escalate)**
1. Merchant: "Refund this 15,000 payment."
2. Agent attempts `initiate_refund`. The guardrail refuses it and logs `allowed = false`.
3. Agent calls `escalate_to_human` with the reason, summary, attempts and recommendation.
4. Support agent reviews in the console and resolves. The merchant is notified.

## 4. API requirements
Endpoints are listed in ARCHITECTURE.md. Requirements: JSON bodies, validated input, clear error codes, no secrets or stack traces in responses, `/readyz` checks the database.

## 5. Non-functional requirements
| ID | Requirement |
|---|---|
| NFR-01 | AI-closed tickets complete in under 30 seconds in normal conditions. |
| NFR-02 | Every agent action is auditable from the database alone. |
| NFR-03 | Secrets come from environment variables and are never committed or logged. |
| NFR-04 | Logs exclude merchant phone numbers and message content. |
| NFR-05 | If the LLM is unavailable or returns invalid output, the ticket is escalated with the reason, not left hanging. |
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

## 7. Open questions
1. Is the INR 2,000 refund limit appropriate for the demo story? (It is a configurable assumption.)
2. Does the console need human approval of the recommended refund (FR-504) in the demo, or only resolve with a note?
3. Chat only, or add voice (FR-106) as a stretch?
