import pytest
from fastapi.testclient import TestClient

from app import bolna, voice
from app.core.config import settings
from app.core.db import db
from app.main import app

AGENT, SECRET = "agent-paytm", "s3cret"
AUTH = {"Authorization": f"Bearer {SECRET}"}
client = TestClient(app)


@pytest.fixture(autouse=True)
def voice_env(monkeypatch):
    monkeypatch.setattr(settings, "bolna_paytm_agent_id", AGENT)
    monkeypatch.setattr(settings, "bolna_webhook_secret", SECRET)
    monkeypatch.setattr(settings, "bolna_api_key", "k")
    monkeypatch.setattr(settings, "demo_call_allowlist", "+919876543210")
    voice._verified.clear()
    voice._calls_log.clear()


@pytest.fixture
def executions(monkeypatch):
    """Fake Bolna: execution id -> payload. The telephony call id is 'tel-<id>'."""
    store: dict = {}

    def get_execution(eid):
        return store.get(eid)

    def resolve(call_id):
        return store.get(call_id) or next((e for e in store.values() if e["telephony_data"]["provider_call_id"] == call_id), None)

    monkeypatch.setattr(bolna, "get_execution", get_execution)
    monkeypatch.setattr(bolna, "resolve_execution", resolve)
    monkeypatch.setattr(bolna, "place_call", lambda phone, ud: _place(store, ud))
    return store


def _place(store, ud):
    eid = f"ex{len(store) + 1}"
    store[eid] = {"id": eid, "agent_id": AGENT, "status": "in-progress", "telephony_data": {"provider_call_id": f"tel-{eid}"}}
    return eid


def start(merchant="M-PRIYA", phone="+919876543210"):
    r = client.post("/api/v1/calls", json={"merchant_id": merchant, "phone": phone})
    return r


def tool(name, call_id, **args):
    return client.post(f"/api/v1/voice/tools/{name}", json={"call_id": call_id, **args}, headers=AUTH)


def test_call_creates_voice_ticket_and_call(executions):
    r = start()
    assert r.status_code == 201
    with db() as d:
        t = d.one("select channel, status from tm_tickets where id = :t", t=r.json()["ticket_id"])
        assert t["channel"] == "voice"
        assert d.one("select phone_last4 from tm_calls")["phone_last4"] == "3210"


def test_call_refused_for_number_outside_allowlist(executions):
    assert start(phone="+919000000000").status_code == 403
    assert start(phone="98765").status_code == 422
    assert executions == {}


def test_production_with_empty_allowlist_disables_calls(executions, monkeypatch):
    monkeypatch.setattr(settings, "demo_call_allowlist", "")
    monkeypatch.setattr(settings, "environment", "production")
    assert start().status_code == 403


def test_bolna_failure_leaves_no_ticket(monkeypatch):
    def boom(*a):
        raise bolna.BolnaError("down")
    monkeypatch.setattr(bolna, "place_call", boom)
    assert start().status_code == 502
    with db() as d:
        assert d.one("select count(*) as n from tm_tickets")["n"] == 0


def test_tools_need_the_secret(executions):
    start()
    r = client.post("/api/v1/voice/tools/get_settlement_status", json={"call_id": "tel-ex1"})
    assert r.status_code == 403


def test_tool_call_uses_call_merchant_not_caller_input(executions):
    start("M-PRIYA")
    # a model-supplied merchant id is ignored: the merchant comes from the call row
    r = tool("list_recent_transactions", "tel-ex1", merchant_id="M-RAHUL")
    ids = {t["id"] for t in r.json()["transactions"]}
    assert ids == {"TXN-2001", "TXN-2002", "TXN-2003"}


def test_refund_by_voice_then_resolve(executions):
    start("M-PRIYA")
    assert tool("initiate_refund", "tel-ex1", transaction_id="TXN-2001").json()["ok"] is True
    r = tool("resolve_ticket", "tel-ex1", category="failed_payment", summary="refunded",
             reply_to_merchant="A refund of INR 850 has been initiated.")
    assert r.json()["ok"] is True
    with db() as d:
        assert d.one("select status, resolved_by from tm_tickets")["resolved_by"] == "ai"
    assert tool("get_settlement_status", "tel-ex1").json()["ok"] is False  # closed tickets accept no more actions


def test_guardrail_applies_on_voice(executions):
    start("M-RAHUL")
    r = tool("initiate_refund", "tel-ex1", transaction_id="TXN-5001").json()
    assert r["ok"] is False and r["must_escalate"] is True


def test_unknown_or_foreign_call_rejected(executions):
    start()
    assert tool("get_settlement_status", "nope").status_code == 403
    executions["ex9"] = {"id": "ex9", "agent_id": "someone-else", "status": "in-progress", "telephony_data": {"provider_call_id": "tel-ex9"}}
    assert tool("get_settlement_status", "tel-ex9").status_code == 403
    executions["ex8"] = {"id": "ex8", "agent_id": AGENT, "status": "in-progress", "telephony_data": {"provider_call_id": "tel-ex8"}}
    assert tool("get_settlement_status", "tel-ex8").status_code == 403  # genuine Bolna call, but not placed by this app


def test_ended_call_rejected(executions):
    start()
    executions["ex1"]["status"] = "completed"
    assert tool("get_settlement_status", "tel-ex1").status_code == 403


def test_hangup_before_resolution_escalates(executions):
    start()
    tool("get_settlement_status", "tel-ex1")
    executions["ex1"].update(status="call-disconnected", transcript="assistant: hello\nuser: hi", telephony_data={"provider_call_id": "tel-ex1", "duration": "12"})
    assert client.post("/api/v1/voice/events", json={"id": "ex1"}).json() == {"ok": True}
    with db() as d:
        assert d.one("select status from tm_tickets")["status"] == "escalated"
        assert d.one("select reason from tm_escalations")["reason"] == "call_dropped"
        c = d.one("select transcript, duration_seconds from tm_calls")
        assert c["duration_seconds"] == 12 and "hello" in c["transcript"]
    client.post("/api/v1/voice/events", json={"id": "ex1"})  # replay: no second escalation
    with db() as d:
        assert d.one("select count(*) as n from tm_escalations")["n"] == 1


def test_event_for_unknown_call_rejected(executions):
    assert client.post("/api/v1/voice/events", json={"id": "ghost"}).status_code == 403


def test_ticket_detail_includes_call(executions):
    r = start()
    d = client.get(f"/api/v1/tickets/{r.json()['ticket_id']}").json()
    assert d["channel"] == "voice" and d["call"]["phone_last4"] == "3210"
