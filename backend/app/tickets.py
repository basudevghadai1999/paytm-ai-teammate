from app.core.config import settings
from app.core.db import Db


def create_ticket(d: Db, merchant_id: str, message: str, email: str | None = None) -> int:
    t = d.one("insert into tm_tickets (merchant_id, contact_email) values (:m, :e) returning id", m=merchant_id, e=email)
    d.run("insert into tm_messages (ticket_id, role, content) values (:t, 'merchant', :c)", t=t["id"], c=message)
    return t["id"]


def ticket_detail(d: Db, ticket_id: int) -> dict | None:
    t = d.one("select t.*, m.name as merchant_name from tm_tickets t join tm_merchants m on m.id = t.merchant_id"
              " where t.id = :t", t=ticket_id)
    if not t:
        return None
    t["has_email"] = bool(t.pop("contact_email", None))  # the address itself is never returned
    t["messages"] = d.all("select id, role, kind, channel, content, created_at from tm_messages where ticket_id = :t order by id", t=ticket_id)
    t["actions"] = d.all("select id, step, tool, args, result, allowed, created_at from tm_actions where ticket_id = :t order by id",
                         t=ticket_id)
    t["call"] = d.one("select status, phone_last4, transcript, duration_seconds, created_at, ended_at from tm_calls"
                      " where ticket_id = :t order by id desc limit 1", t=ticket_id)
    t["escalation"] = d.one("select * from tm_escalations where ticket_id = :t order by id desc limit 1", t=ticket_id)
    return t


def list_tickets(d: Db, limit: int = 100) -> list[dict]:
    return d.all(
        "select t.id, t.merchant_id, m.name as merchant_name, t.channel, t.status, t.category, t.resolved_by, t.created_at, t.closed_at,"
        " coalesce((select content from tm_messages where ticket_id = t.id and role = 'merchant' order by id limit 1), 'Voice call') as first_message,"
        " (select reason from tm_escalations where ticket_id = t.id order by id desc limit 1) as escalation_reason"
        " from tm_tickets t join tm_merchants m on m.id = t.merchant_id order by t.id desc limit :n", n=limit)


def resolve_escalation(d: Db, escalation_id: int, note: str) -> bool:
    e = d.one("select id, ticket_id from tm_escalations where id = :e and status = 'open' for update", e=escalation_id)
    if not e:
        return False
    d.run("update tm_escalations set status = 'resolved', resolution_note = :n, resolved_at = now() where id = :e",
          n=note, e=escalation_id)
    d.run("insert into tm_messages (ticket_id, role, content) values (:t, 'human', :c)", t=e["ticket_id"], c=note)
    d.run("update tm_tickets set status = 'resolved', resolved_by = 'human', closed_at = now(),"
          " resolution_summary = :n where id = :t", t=e["ticket_id"], n=note)
    return True


def metrics(d: Db) -> dict:
    c = d.one("select count(*) as total,"
              " count(*) filter (where resolved_by = 'ai') as resolved_ai,"
              " count(*) filter (where resolved_by = 'human') as resolved_human,"
              " count(*) filter (where status = 'escalated') as escalated_open,"
              " count(*) filter (where status in ('open','awaiting_merchant')) as in_progress,"
              " avg(extract(epoch from closed_at - created_at)) filter (where resolved_by = 'ai') as avg_ai_seconds"
              " from tm_tickets")
    reasons = d.all("select reason, count(*) as n from tm_escalations group by reason order by n desc")
    blocked = d.one("select count(*) as n from tm_actions where not allowed")["n"]
    # defence in depth: an executed refund above the limit would mean a guardrail failed
    unsafe = d.one("select count(*) as n from tm_actions where tool = 'initiate_refund' and allowed"
                   " and (result->>'amount_inr')::int > :lim", lim=settings.auto_refund_limit_inr)["n"]
    total = c["total"]
    return {
        "total_tickets": total, "resolved_by_ai": c["resolved_ai"], "resolved_by_human": c["resolved_human"],
        "escalated_open": c["escalated_open"], "in_progress": c["in_progress"],
        "auto_resolution_rate": (c["resolved_ai"] / total) if total else None,
        "avg_ai_resolution_seconds": float(c["avg_ai_seconds"]) if c["avg_ai_seconds"] is not None else None,
        "escalations_by_reason": reasons, "blocked_actions": blocked, "unsafe_actions": unsafe,
        "refund_limit_inr": settings.auto_refund_limit_inr,
    }
