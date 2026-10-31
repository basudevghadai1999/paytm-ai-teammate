# Agent Design

Principle (carried over from COOLops): **the LLM only proposes; deterministic code decides what is allowed.** Safety rules live in code, not in the prompt.

## Two paths, one set of guardrails
- **Voice (the product):** a Bolna agent talks to the merchant and calls our tool endpoints. It cannot act except through `POST /api/v1/voice/tools/{tool}`, which runs each call through `app/tools.py`.
- **Chat (tests and evals):** our own loop in `app/agent.py` drives the same tools without a phone, so the policy can be evaluated repeatably against a real model.

## Chat agent loop
1. Load ticket, merchant profile, recent transactions and settlements, and past tickets as context.
2. Screen the merchant's message for fraud or legal wording (English and Hindi). A match escalates immediately, with no model call.
3. Call the model with the system prompt, conversation, and tool definitions.
4. If the model requests tools, run each through the guardrail layer, log it to `tm_actions`, and feed the result back.
5. Stop when the model calls a terminal tool (`resolve_ticket`, `escalate_to_human`), asks the merchant a question (ticket becomes `awaiting_merchant`), or hits the step limit.
6. Step limit (default 8) with no terminal action means automatic escalation. An unavailable or invalid model means escalation too. The agent never loops forever and never ends silently.

## Voice call handling
- The merchant is identified by the call this app placed (`tm_calls`), never by what the caller says. Each tool call is verified with Bolna: the call must be a live execution of our agent and one we dialled.
- `ask_merchant` is not offered on a call: the agent simply asks aloud.
- A call that ends before the ticket is resolved or escalated escalates as `call_dropped`.
- After the call, the merchant's side of the transcript is screened for fraud or legal wording. If the agent missed it, the ticket is reopened and escalated.
- The prompt asks for short spoken sentences, Hindi or English to match the merchant, and never asking for OTPs, PINs or card numbers.

## Tools
| Tool | Type | Notes |
|---|---|---|
| `get_settlement_status` | read | Latest settlements for this merchant |
| `get_transaction` | read | Transaction by id, must belong to this merchant |
| `list_recent_transactions` | read | Helps find a payment the merchant describes loosely |
| `get_device_status` | read | Soundbox status |
| `initiate_refund` | write | Guarded, see below |
| `raise_device_replacement` | write | Only if the device status is faulty |
| `send_notification` | write | A real confirmation email to the address on the ticket. The result says `channel: email` or `simulated` (no address); a mail failure is reported as a blocked action so the agent cannot claim it was sent |
| `ask_merchant` | clarify | Chat path only. Sets `awaiting_merchant`; once per ticket |
| `resolve_ticket` | terminal | Requires a summary and category (`out_of_scope` allowed) |
| `escalate_to_human` | terminal | Requires reason, summary, steps attempted, recommended action |

The tool schema has **no merchant id parameter**. The merchant id is bound server-side, so the model cannot read or act on another merchant.

## Scope (stay in the domain)
The teammate only handles Paytm merchant support: settlements, payments and refunds, the soundbox, and the merchant's own account issues on those. For anything else (weather, jokes, general knowledge, other companies, advice) it declines **once**, in one or two friendly sentences, without answering and without using a tool, and offers what it can do. If the merchant stays off-topic it closes the ticket politely as `out_of_scope`. It never escalates to a human just because someone is off-topic. A message that mixes an off-topic part with a real issue gets the real issue handled and only the rest declined. Out-of-scope tickets are counted separately and kept out of the auto-resolution rate.

## Decision policy
| Situation | Decision |
|---|---|
| Settlement `pending` and expected date in the future | Resolve: explain and send a confirmation |
| Settlement `on_hold` for KYC or risk | Escalate: a human must review |
| Transaction failed, customer debited, amount at most the limit | Refund and resolve |
| Refund request, transaction successful, amount at most the limit | Refund and resolve |
| Amount above the limit | Escalate with a recommendation |
| Device faulty | Raise replacement and resolve |
| Missing key detail, several plausible matches | Ask the merchant once, then escalate if still unclear |
| Fraud, hacked account, legal threat, abusive or distressed merchant | **Emergency:** escalate immediately and alert human support by email |
| Off-topic request | Decline once, then close as `out_of_scope` |
| Tool errors repeatedly, or the model cannot decide | Escalate |

## Guardrails (enforced in code)
- **Refund limit:** `AUTO_REFUND_LIMIT_INR` (default 2000). Above it the tool refuses and tells the agent to escalate. The refusal is logged with `allowed = false`.
- **No double refund:** a transaction already `refunded` cannot be refunded again (row-locked, so concurrent calls cannot both pass).
- **Ownership:** every lookup and action is scoped to the ticket's merchant.
- **State check:** a refund requires `success` or (`failed` and `customer_debited`). Replacement requires a faulty device.
- **Idempotency:** the same notification on the same ticket is not sent twice.
- **Claims check:** a reply that mentions a refund, a replacement, or an email/SMS is replaced by the confirmed outcomes unless a tool result backs it up.
- **Closed means closed:** a ticket that is resolved or escalated accepts no more tool calls.
- **Calls:** only allowlisted numbers can be dialled outside development; a secret is required on tool endpoints; a call is verified with Bolna before any tool runs.
- **No sensitive data in logs:** `hide_parameters`, only the last four digits of a phone number stored, the contact email never returned by the API.

## Emergencies and escalation
**Live transfer (emergencies only).** When `SUPPORT_TRANSFER_NUMBER` is set, an emergency escalation on a live call (`fraud_or_legal`, `abusive_or_distressed`) answers the agent with `transfer: true`, and the agent then calls Bolna's built-in `transfer_call_support` tool, which bridges the call to that number. Every other escalation, and every emergency when no number is set, stays a callback. The destination lives in the agent's own configuration, so the model can never choose where a call goes. The app records what Bolna reports about the transfer leg (`requested`, `attempted`, `transferred`, `failed`) and never shows a request as a completed transfer. If nobody picks up, or the call ends before it connects, the support inbox gets an urgent "call the merchant back now" email with the merchant's number, taken from Bolna's record and not stored here.

Emergency reasons (`fraud_or_legal`, `abusive_or_distressed`) escalate straight away. Besides the case package below, the human support inbox gets an urgent email with the summary, steps tried and recommended action. The merchant gets an acknowledgement email.

Every escalation stores: reason code, one-paragraph case summary, steps already attempted, and a recommended next action. A human sees the case in the console without re-reading the call. When the human resolves it, the ticket closes with `resolved_by = human` and the note goes to the merchant.

## Prompt
Short and role-based: who the agent is, scope, tone, the instruction to use tools for every fact, never invent amounts or dates, and escalate when unsure. Policy numbers are not in the prompt; the tools enforce them. The chat and voice prompts share the scope and decision-guide text (`app/agent.py`), so they cannot drift apart.

## Observability
Every step (tool, args, result, allowed) is stored in `tm_actions` and shown in the ops console, together with the call status, duration and transcript. This is also the evidence for the metrics.
