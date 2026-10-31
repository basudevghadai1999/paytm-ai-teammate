# Agent Design

Principle (carried over from COOLops): **the LLM only proposes; deterministic code decides what is allowed.** Safety rules live in code, not in the prompt.

## Agent loop
1. Load ticket, merchant profile, recent transactions and settlements, and past tickets as context.
2. Call the model with the system prompt, conversation, and tool definitions.
3. If the model requests tools, run each through the guardrail layer, log it to `tm_actions`, and feed the result back.
4. Stop when the model calls a terminal tool (`resolve_ticket`, `escalate_to_human`), replies with a question for the merchant (ticket becomes `awaiting_merchant`), or hits the step limit.
5. Step limit (default 8) with no terminal action means automatic escalation. The agent never loops forever and never ends silently.

## Tools
| Tool | Type | Notes |
|---|---|---|
| `get_settlement_status` | read | Latest settlements for this merchant |
| `get_transaction` | read | Transaction by id, must belong to this merchant |
| `list_recent_transactions` | read | Helps find a payment the merchant describes loosely |
| `get_device_status` | read | Soundbox status |
| `initiate_refund` | write | Guarded, see below |
| `raise_device_replacement` | write | Only if the device status is faulty |
| `send_notification` | write | Message to the merchant, simulated SMS or WhatsApp |
| `ask_merchant` | clarify | Sets `awaiting_merchant`, used when information is missing |
| `resolve_ticket` | terminal | Requires a summary and category |
| `escalate_to_human` | terminal | Requires reason, summary, steps attempted, recommended action |

The tool schema has **no merchant id parameter**. The merchant id is bound server-side from the ticket, so the model cannot read or act on another merchant.

## Decision policy
| Situation | Decision |
|---|---|
| Settlement `pending` and expected date in the future | Resolve: explain and notify |
| Settlement `on_hold` for KYC or risk | Escalate: a human must review |
| Transaction failed, customer debited, amount at most the limit | Refund and resolve |
| Refund request, transaction successful, amount at most the limit | Refund and resolve |
| Amount above the limit | Escalate with a recommendation |
| Device faulty | Raise replacement and resolve |
| Missing key detail (which transaction? which date?) | Ask the merchant once, then escalate if still unclear |
| Merchant mentions fraud, legal threat, or is abusive or distressed | Escalate immediately |
| Tool errors repeatedly, or the model cannot decide | Escalate |

## Guardrails (enforced in code)
- **Refund limit:** `AUTO_REFUND_LIMIT_INR` (default 2000). Above it the tool refuses and returns an error that tells the agent to escalate. The refusal is logged with `allowed = false`.
- **No double refund:** a transaction already `refunded` cannot be refunded again.
- **Ownership:** every lookup and action is scoped to the ticket's merchant.
- **State check:** a refund requires `success` or (`failed` and `customer_debited`). Replacement requires a faulty device.
- **Idempotency:** the same write on the same ticket is not executed twice.
- **Claims check:** replies must not state an action succeeded unless a tool result confirms it. The final reply is generated from tool results.
- **No sensitive data in logs:** same approach as COOLops (`hide_parameters`).

## Escalation package
Every escalation stores: reason code, one-paragraph case summary, steps already attempted, and a recommended next action. A human sees the case in the console without re-reading the whole chat. When the human resolves it, the ticket closes with `resolved_by = human`.

## Prompt
Short and role-based: who the agent is, tone (brief, clear, India-appropriate English, no jargon), the instruction to use tools for every fact, never invent amounts or dates, and escalate when unsure. Policy numbers are not in the prompt; the tools enforce them.

## Observability
Every step (tool, args, result, allowed) is stored in `tm_actions` and shown live in the ops console. This is also the evidence for the metrics.
