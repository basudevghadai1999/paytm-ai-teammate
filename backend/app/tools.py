"""Agent tools. Every guardrail lives here, in code: the model only proposes (BR-01 to BR-10).

The merchant id is never a tool parameter. It comes from the ticket (BR-06, FR-310).
"""
import json
import re
from dataclasses import dataclass
from typing import Any, Callable

from app.core.config import settings
from app import mailer
from app.core.db import Db

CATEGORIES = ["settlement_delay", "failed_payment", "refund_request", "device_fault", "other"]
ESCALATION_REASONS = [
    "refund_above_limit", "settlement_on_hold", "fraud_or_legal", "abusive_or_distressed",
    "unclear_request", "ineligible_request", "tool_failure", "step_limit", "llm_unavailable", "call_dropped", "other",
]
MAX_CLARIFICATIONS = 1  # BR-08
EMERGENCY_REASONS = {"fraud_or_legal", "abusive_or_distressed"}  # also alert the human support inbox

MERCHANT_ESCALATION_NOTE = (
    "I've passed this to our support team with all the details, so you won't need to explain it again. "
    "A person will follow up with you soon."
)


class Refused(Exception):
    """A guardrail blocked the call. The model sees the message and must adapt or escalate."""

    def __init__(self, message: str, must_escalate: bool = False):
        super().__init__(message)
        self.must_escalate = must_escalate


@dataclass
class Ctx:
    d: Db
    ticket_id: int
    merchant_id: str
    step: int


def _s(v: dict) -> str:
    return json.dumps(v, default=str)


def _clean(v: Any) -> Any:
    return json.loads(json.dumps(v, default=str))


# ---------- reads ----------

def get_settlement_status(c: Ctx, a: dict) -> dict:
    rows = c.d.all("select id, amount_inr, expected_date, status, hold_reason from tm_settlements"
                   " where merchant_id = :m order by expected_date desc limit 5", m=c.merchant_id)
    return {"settlements": rows}


def get_transaction(c: Ctx, a: dict) -> dict:
    row = c.d.one("select id, amount_inr, mode, status, customer_debited, customer_name, created_at from tm_transactions"
                  " where id = :t and merchant_id = :m", t=str(a["transaction_id"]), m=c.merchant_id)
    if not row:
        raise Refused("No such transaction for this merchant.")
    return {"transaction": row}


def list_recent_transactions(c: Ctx, a: dict) -> dict:
    n = max(1, min(int(a.get("limit", 10)), 20))
    rows = c.d.all("select id, amount_inr, mode, status, customer_debited, customer_name, created_at from tm_transactions"
                   " where merchant_id = :m order by created_at desc limit :n", m=c.merchant_id, n=n)
    return {"transactions": rows}


def get_device_status(c: Ctx, a: dict) -> dict:
    row = c.d.one("select device_id, device_status from tm_merchants where id = :m", m=c.merchant_id)
    if not row or not row["device_id"]:
        raise Refused("No device registered for this merchant.")
    return {"device": row}


# ---------- writes ----------

def initiate_refund(c: Ctx, a: dict) -> dict:
    # lock the row so two concurrent refunds cannot both pass the checks
    t = c.d.one("select id, amount_inr, status, customer_debited from tm_transactions"
                " where id = :t and merchant_id = :m for update", t=str(a["transaction_id"]), m=c.merchant_id)
    if not t:
        raise Refused("No such transaction for this merchant.")
    if t["status"] == "refunded":  # BR-03
        raise Refused("This transaction has already been refunded. It cannot be refunded twice.")
    if not (t["status"] == "success" or (t["status"] == "failed" and t["customer_debited"])):  # BR-04
        raise Refused("Refunds are only allowed for a successful transaction, or a failed one where the customer was debited.")
    if t["amount_inr"] > settings.auto_refund_limit_inr:  # BR-01, BR-02
        raise Refused(
            f"Amount INR {t['amount_inr']} is above the automatic refund limit of INR {settings.auto_refund_limit_inr}. "
            "Escalate to a human with a recommendation.", must_escalate=True)
    c.d.run("update tm_transactions set status = 'refunded' where id = :t", t=t["id"])
    return {"refund_id": f"RFD-{t['id']}", "transaction_id": t["id"], "amount_inr": t["amount_inr"], "status": "initiated"}


def raise_device_replacement(c: Ctx, a: dict) -> dict:
    m = c.d.one("select device_id, device_status from tm_merchants where id = :m for update", m=c.merchant_id)
    if not m or not m["device_id"]:
        raise Refused("No device registered for this merchant.")
    if m["device_status"] != "faulty":  # FR-404; also makes the call idempotent
        raise Refused(f"Device status is '{m['device_status']}', not faulty. A replacement cannot be raised.")
    c.d.run("update tm_merchants set device_status = 'replacement_requested' where id = :m", m=c.merchant_id)
    return {"request_id": f"RPL-{m['device_id']}", "device_id": m["device_id"], "status": "replacement_requested"}


def _contact(c: Ctx) -> str | None:
    return (c.d.one("select contact_email from tm_tickets where id = :t", t=c.ticket_id) or {}).get("contact_email")


def _record(c: Ctx, text: str, channel: str, provider_id: str | None = None) -> None:
    c.d.run("insert into tm_messages (ticket_id, role, kind, content, channel, provider_id) values (:t, 'agent', 'notification', :c, :ch, :p)",
            t=c.ticket_id, c=text, ch=channel, p=provider_id)


def send_notification(c: Ctx, a: dict) -> dict:
    text = str(a["message"]).strip()
    if not text:
        raise Refused("Notification message is empty.")
    dup = c.d.one("select id from tm_messages where ticket_id = :t and kind = 'notification' and content = :c",
                  t=c.ticket_id, c=text)
    if dup:
        raise Refused("This exact notification was already sent on this ticket.")
    to = _contact(c)
    if to and mailer.configured():
        try:
            pid = mailer.send(to, f"Your Paytm support update (ticket #{c.ticket_id})", text)
        except mailer.MailError:
            raise Refused("The confirmation email could not be sent. Do not tell the merchant an email was sent.")
        _record(c, text, "email", pid)
        return {"sent": True, "channel": "email"}
    _record(c, text, "simulated")
    return {"sent": True, "channel": "simulated",
            "note": "No email address on file, so this was only logged. Do not tell the merchant an email or SMS was sent."}


def _ack_email(c: Ctx, subject: str, text: str) -> None:
    """Acknowledgement the code sends itself, so it never depends on the model. Best effort: a mail failure never blocks the ticket."""
    to = _contact(c)
    if not to or not mailer.configured():
        return
    if c.d.one("select 1 as x from tm_messages where ticket_id = :t and channel = 'email'", t=c.ticket_id):
        return  # the merchant already has an email about this ticket
    try:
        pid = mailer.send(to, subject, text)
    except mailer.MailError:
        return
    _record(c, text, "email", pid)


def _alert_support(c: Ctx, esc_id: int, reason: str, summary: str, steps: list, rec: str) -> None:
    if reason not in EMERGENCY_REASONS or not settings.support_alert_email or not mailer.configured():
        return
    m = c.d.one("select m.name, m.city from tm_tickets t join tm_merchants m on m.id = t.merchant_id where t.id = :t", t=c.ticket_id)
    body = (f"Emergency escalation, ticket #{c.ticket_id}\nMerchant: {m['name']} ({m['city']})\nReason: {reason.replace('_', ' ')}\n\n"
            f"Summary: {summary}\n\nSteps attempted: {'; '.join(map(str, steps)) or 'none'}\n\nRecommended action: {rec}\n\n"
            f"Open the ops console to review the full call and agent steps: {settings.public_base_url}")
    try:
        mailer.send(settings.support_alert_email, f"[URGENT] Paytm support escalation #{c.ticket_id}: {reason.replace('_', ' ')}", body)
    except mailer.MailError:
        return
    c.d.run("update tm_escalations set alerted_at = now() where id = :e", e=esc_id)


def ask_merchant(c: Ctx, a: dict) -> dict:
    q = str(a["question"]).strip()
    if not q:
        raise Refused("Question is empty.")
    asked = c.d.one("select count(*) as n from tm_actions where ticket_id = :t and tool = 'ask_merchant' and allowed",
                    t=c.ticket_id)["n"]
    if asked >= MAX_CLARIFICATIONS:  # BR-08
        raise Refused("You have already asked the merchant a clarifying question on this ticket. Escalate instead.",
                      must_escalate=True)
    c.d.run("insert into tm_messages (ticket_id, role, content) values (:t, 'agent', :c)", t=c.ticket_id, c=q)
    c.d.run("update tm_tickets set status = 'awaiting_merchant' where id = :t", t=c.ticket_id)
    return {"status": "awaiting_merchant"}


def _confirmed_outcomes(c: Ctx) -> list[str]:
    """Plain-language statements backed by successful write results on this ticket (BR-09)."""
    out = []
    for r in c.d.all("select tool, result from tm_actions where ticket_id = :t and allowed"
                     " and tool in ('initiate_refund','raise_device_replacement') order by id", t=c.ticket_id):
        res = r["result"]
        if r["tool"] == "initiate_refund":
            out.append(f"A refund of INR {res['amount_inr']} has been initiated for transaction {res['transaction_id']}.")
        else:
            out.append(f"A replacement request ({res['request_id']}) has been raised for your device.")
    return out


def _claims_ok(c: Ctx, reply: str) -> bool:
    low = reply.lower()
    kinds = {r["tool"] for r in c.d.all("select tool from tm_actions where ticket_id = :t and allowed", t=c.ticket_id)}
    if "refund" in low and "initiate_refund" not in kinds:
        return False
    if "replacement" in low and "raise_device_replacement" not in kinds:
        return False
    if re.search(r"e-?mail|sms|text message", low) and not c.d.one(
            "select 1 as x from tm_messages where ticket_id = :t and channel = 'email'", t=c.ticket_id):
        return False
    return True


def resolve_ticket(c: Ctx, a: dict) -> dict:
    cat = a.get("category")
    if cat not in CATEGORIES:
        raise Refused(f"category must be one of {CATEGORIES}.")
    summary = str(a.get("summary", "")).strip()
    reply = str(a.get("reply_to_merchant", "")).strip()
    if not summary or not reply:
        raise Refused("summary and reply_to_merchant are required.")
    if not _claims_ok(c, reply):  # BR-09: never claim an action no tool result confirms
        confirmed = _confirmed_outcomes(c)
        reply = " ".join(confirmed) if confirmed else "Thanks for reaching out. Your query has been reviewed and closed."
    c.d.run("insert into tm_messages (ticket_id, role, content) values (:t, 'agent', :c)", t=c.ticket_id, c=reply)
    c.d.run("update tm_tickets set status = 'resolved', category = :cat, resolution_summary = :s,"
            " resolved_by = 'ai', closed_at = now() where id = :t", t=c.ticket_id, cat=cat, s=summary)
    _ack_email(c, f"Your Paytm support request is resolved (ticket #{c.ticket_id})", reply)
    return {"status": "resolved", "reply": reply}


def escalate_to_human(c: Ctx, a: dict) -> dict:
    reason = a.get("reason")
    if reason not in ESCALATION_REASONS:
        raise Refused(f"reason must be one of {ESCALATION_REASONS}.")
    summary = str(a.get("summary", "")).strip()
    rec = str(a.get("recommended_action", "")).strip()
    steps = a.get("steps_attempted")
    if not summary or not rec or not isinstance(steps, list):
        raise Refused("summary, steps_attempted (list) and recommended_action are required.")
    cat = a.get("category") if a.get("category") in CATEGORIES else None
    esc = c.d.one("insert into tm_escalations (ticket_id, reason, summary, attempted_steps, recommended_action)"
                  " values (:t, :r, :s, cast(:st as jsonb), :rec) returning id", t=c.ticket_id, r=reason, s=summary, st=_s(steps), rec=rec)
    # fixed wording: the model must not promise outcomes to the merchant (FR-105)
    c.d.run("insert into tm_messages (ticket_id, role, content) values (:t, 'agent', :c)", t=c.ticket_id, c=MERCHANT_ESCALATION_NOTE)
    c.d.run("update tm_tickets set status = 'escalated', category = coalesce(:cat, category) where id = :t",
            t=c.ticket_id, cat=cat)
    _ack_email(c, f"We have your Paytm support request (ticket #{c.ticket_id})",
               MERCHANT_ESCALATION_NOTE + f"\n\nYour ticket number is {c.ticket_id}.")
    _alert_support(c, esc["id"], reason, summary, steps, rec)
    return {"status": "escalated", "reason": reason}


READ_TOOLS = {"get_settlement_status", "get_transaction", "list_recent_transactions", "get_device_status"}
TERMINAL_TOOLS = {"resolve_ticket", "escalate_to_human"}
HANDLERS: dict[str, Callable[[Ctx, dict], dict]] = {
    f.__name__: f for f in (
        get_settlement_status, get_transaction, list_recent_transactions, get_device_status, initiate_refund,
        raise_device_replacement, send_notification, ask_merchant, resolve_ticket, escalate_to_human)
}


def _fn(name: str, desc: str, props: dict, required: list[str]) -> dict:
    return {"type": "function", "function": {"name": name, "description": desc,
            "parameters": {"type": "object", "properties": props, "required": required}}}


_STR = {"type": "string"}
TOOL_SCHEMAS = [
    _fn("get_settlement_status", "Latest settlements for this merchant (status, amount, expected date, hold reason).", {}, []),
    _fn("get_transaction", "Look up one of this merchant's transactions by id.", {"transaction_id": _STR}, ["transaction_id"]),
    _fn("list_recent_transactions", "Recent transactions, newest first. Use to find a payment the merchant describes loosely.",
        {"limit": {"type": "integer", "description": "1 to 20, default 10"}}, []),
    _fn("get_device_status", "Status of this merchant's soundbox (active, faulty, replacement_requested).", {}, []),
    _fn("initiate_refund", "Refund a transaction. Guarded by policy; may be refused.",
        {"transaction_id": _STR, "reason": _STR}, ["transaction_id"]),
    _fn("raise_device_replacement", "Raise a soundbox replacement. Only allowed when the device status is faulty.",
        {"reason": _STR}, []),
    _fn("send_notification", "Send the merchant a written confirmation by email. The result says whether it was really emailed (channel email) or only logged (channel simulated).", {"message": _STR}, ["message"]),
    _fn("ask_merchant", "Ask the merchant ONE clarifying question when key information is missing. Pauses the ticket.",
        {"question": _STR}, ["question"]),
    _fn("resolve_ticket", "Close the ticket. Only after the needed actions are done and confirmed by tool results.",
        {"category": {"type": "string", "enum": CATEGORIES}, "summary": {"type": "string", "description": "Internal summary"},
         "reply_to_merchant": {"type": "string", "description": "Final message to the merchant; state only confirmed outcomes"}},
        ["category", "summary", "reply_to_merchant"]),
    _fn("escalate_to_human", "Hand the ticket to a human with a full case package.",
        {"reason": {"type": "string", "enum": ESCALATION_REASONS}, "category": {"type": "string", "enum": CATEGORIES},
         "summary": {"type": "string", "description": "One paragraph case summary"},
         "steps_attempted": {"type": "array", "items": _STR}, "recommended_action": _STR},
        ["reason", "summary", "steps_attempted", "recommended_action"]),
]


def execute(c: Ctx, name: str, args: dict) -> tuple[dict, bool]:
    """Run one tool through the guardrails and write it to tm_actions (BR-10). Returns (result, allowed)."""
    allowed = True
    handler = HANDLERS.get(name)
    try:
        if handler is None:
            raise Refused(f"Unknown tool '{name}'.")
        result = handler(c, args)
    except Refused as e:
        allowed, result = False, {"error": str(e), "must_escalate": e.must_escalate}
    except (KeyError, TypeError, ValueError):
        allowed, result = False, {"error": "Invalid or missing arguments for this tool."}
    result = _clean(result)
    c.d.run("insert into tm_actions (ticket_id, step, tool, args, result, allowed)"
            " values (:t, :s, :tool, cast(:a as jsonb), cast(:r as jsonb), :al)",
            t=c.ticket_id, s=c.step, tool=name, a=_s(args), r=_s(result), al=allowed)
    return result, allowed
