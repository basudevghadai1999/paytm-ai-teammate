"""Voice channel (Bolna). Mid-call the Bolna agent calls our tool endpoints; every call goes through the same guarded
app.tools.execute as chat. The merchant is bound from the call row we created when we dialled, never from the caller's words."""
import hmac
import re
import time

from fastapi import APIRouter, Body, Header, HTTPException
from pydantic import BaseModel

from app import bolna
from app.core.config import settings
from app.core.db import db
from app.tools import MERCHANT_ESCALATION_NOTE, Ctx, execute

router = APIRouter(prefix="/api/v1")
E164 = re.compile(r"^\+[1-9]\d{7,14}$")
UNFILLED = re.compile(r"^%\(\w+\)[sif]$")  # a Bolna placeholder the model never filled
TERMINAL = {"completed", "call-disconnected", "no-answer", "busy", "failed", "canceled", "cancelled", "stopped", "error", "balance-low"}
_calls_log: list[float] = []
_verified: dict[str, str] = {}  # telephony call id -> Bolna execution id, so a call is confirmed with Bolna once


class NewCall(BaseModel):
    merchant_id: str
    phone: str


def _norm(s: str) -> str:
    return str(s).lower().replace("_", "-")


def _allowed_numbers() -> set[str]:
    return {n.strip() for n in settings.demo_call_allowlist.split(",") if n.strip()}


@router.post("/calls", status_code=201)
def start_call(body: NewCall) -> dict:
    """Dial a merchant. Anyone can reach this endpoint, so outside development only allowlisted numbers can be called."""
    phone = body.phone.replace(" ", "")
    if not E164.match(phone):
        raise HTTPException(422, "Enter the number with country code, for example +919876543210")
    allow = _allowed_numbers()
    if allow and phone not in allow or (not allow and settings.environment == "production"):
        raise HTTPException(403, "Calls to this number are not enabled for the demo")
    if not (settings.bolna_api_key and settings.bolna_paytm_agent_id):
        raise HTTPException(503, "Voice calling is not configured")
    now = time.time()
    _calls_log[:] = [t for t in _calls_log if now - t < 60]
    if len(_calls_log) >= 3:
        raise HTTPException(429, "Too many calls; try again in a minute")
    _calls_log.append(now)

    with db() as d:
        m = d.one("select id, name, owner_name from tm_merchants where id = :m", m=body.merchant_id)
        if not m:
            raise HTTPException(404, "Unknown merchant")
        t = d.one("insert into tm_tickets (merchant_id, channel) values (:m, 'voice') returning id", m=m["id"])
    try:
        eid = bolna.place_call(phone, {"merchant_name": m["name"], "owner_name": m["owner_name"]})
    except bolna.BolnaError:
        with db() as d:  # nothing happened yet: do not leave an empty ticket behind
            d.run("delete from tm_tickets where id = :t", t=t["id"])
        raise HTTPException(502, "Could not place the call")
    with db() as d:
        d.run("insert into tm_calls (ticket_id, merchant_id, provider_call_id, phone_last4) values (:t, :m, :c, :l)",
              t=t["id"], m=m["id"], c=eid, l=phone[-4:])
    return {"ticket_id": t["id"], "call_id": eid}


def _check_secret(authorization: str | None) -> None:
    secret = settings.bolna_webhook_secret
    given = (authorization or "").removeprefix("Bearer ").strip()
    if not secret or not hmac.compare_digest(given, secret):
        raise HTTPException(403, "Bad credential")


def _verified_execution(call_id: str | None) -> dict:
    """The id must resolve at Bolna to a live execution of OUR agent, and be a call this app placed."""
    if not call_id or UNFILLED.match(str(call_id)):
        raise HTTPException(422, "call_id required")
    try:
        ex = bolna.resolve_execution(str(call_id))
    except bolna.BolnaError:
        raise HTTPException(502, "Cannot verify the call right now")
    if not ex or ex.get("agent_id") != settings.bolna_paytm_agent_id:
        raise HTTPException(403, "Unknown call id")
    return ex


@router.post("/voice/tools/{tool}")
def voice_tool(tool: str, body: dict = Body(...), authorization: str | None = Header(default=None)) -> dict:
    _check_secret(authorization)
    if tool not in bolna.VOICE_TOOLS:
        raise HTTPException(404, "Unknown tool")
    call_id = str(body.get("call_id") or "")
    eid = _verified.get(call_id)
    if not eid:
        ex = _verified_execution(call_id)
        if _norm(ex.get("status", "")) in TERMINAL:
            raise HTTPException(403, "Call has already ended")
        eid = _verified[call_id] = str(ex["id"])
    with db() as d:
        call = d.one("select ticket_id, merchant_id from tm_calls where provider_call_id = :c", c=eid)
        if not call:
            raise HTTPException(403, "Not a call placed by this app")
        t = d.one("select status from tm_tickets where id = :t for update", t=call["ticket_id"])
        if t["status"] in ("resolved", "escalated"):
            return {"ok": False, "error": "This ticket is already closed.", "say": "This request is already closed."}
        declared = next(x["function"]["parameters"]["properties"] for x in bolna.TOOL_SCHEMAS if x["function"]["name"] == tool)
        args = {k: v for k, v in body.items() if k in declared and v not in (None, "") and not UNFILLED.match(str(v))}
        step = d.one("select coalesce(max(step), 0) + 1 as s from tm_actions where ticket_id = :t", t=call["ticket_id"])["s"]
        result, ok = execute(Ctx(d, call["ticket_id"], call["merchant_id"], step), tool, args)
    out = {"ok": ok, **result}
    if ok and tool == "escalate_to_human":
        out["say"] = MERCHANT_ESCALATION_NOTE
    return out


@router.post("/voice/events")
def call_event(body: dict = Body(...)) -> dict:
    """Bolna status webhook. The body is only a hint: status and transcript are re-read from Bolna before anything is stored."""
    eid = str(body.get("id") or body.get("execution_id") or "")
    if not eid:
        raise HTTPException(422, "missing execution id")
    with db() as d:
        call = d.one("select ticket_id, merchant_id from tm_calls where provider_call_id = :c", c=eid)
    if not call:
        raise HTTPException(403, "Unknown call id")
    try:
        ex = bolna.get_execution(eid)
    except bolna.BolnaError:
        raise HTTPException(502, "Cannot verify the call right now")
    if not ex or ex.get("agent_id") != settings.bolna_paytm_agent_id:
        raise HTTPException(403, "Unknown call id")
    status = str(ex.get("status") or "unknown")
    terminal = _norm(status) in TERMINAL
    tel = ex.get("telephony_data") or {}
    try:
        dur = int(float(tel.get("duration") or ex.get("conversation_time") or 0)) or None
    except (TypeError, ValueError):
        dur = None
    with db() as d:
        if terminal:
            d.run("update tm_calls set status = :s, transcript = coalesce(transcript, :tr), duration_seconds = coalesce(duration_seconds, :du),"
                  " ended_at = coalesce(ended_at, now()) where provider_call_id = :c",
                  s=status, tr=str(ex.get("transcript") or "") or None, du=dur, c=eid)
        else:  # a late 'ringing' never moves a finished call backwards
            d.run("update tm_calls set status = :s where provider_call_id = :c and ended_at is null", s=status, c=eid)
        t = d.one("select status from tm_tickets where id = :t for update", t=call["ticket_id"])
        if terminal and t["status"] in ("open", "awaiting_merchant"):  # hung up or never answered: never end silently
            step = d.one("select coalesce(max(step), 0) + 1 as s from tm_actions where ticket_id = :t", t=call["ticket_id"])["s"]
            execute(Ctx(d, call["ticket_id"], call["merchant_id"], step), "escalate_to_human", {
                "reason": "call_dropped",
                "summary": f"The call ended ({status}) before the ticket was resolved or escalated.",
                "steps_attempted": [a["tool"] for a in d.all("select tool from tm_actions where ticket_id = :t and allowed order by id", t=call["ticket_id"])] or ["None"],
                "recommended_action": "Call the merchant back or review the call transcript."})
    return {"ok": True}
