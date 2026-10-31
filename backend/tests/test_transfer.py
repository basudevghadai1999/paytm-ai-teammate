import pytest
from fastapi.testclient import TestClient

from app import bolna, mailer, voice
from app.core.config import settings
from app.core.db import db
from app.main import app

AGENT, SECRET, DEST = "agent-paytm", "s3cret", "+919811122233"
AUTH = {"Authorization": f"Bearer {SECRET}"}
client = TestClient(app)


@pytest.fixture(autouse=True)
def env(monkeypatch):
    for k, v in dict(bolna_paytm_agent_id=AGENT, bolna_webhook_secret=SECRET, bolna_api_key="k", demo_call_allowlist="+919876543210",
                     support_transfer_number=DEST, support_alert_email="support@example.com").items():
        monkeypatch.setattr(settings, k, v)
    voice._verified.clear(); voice._calls_log.clear()


@pytest.fixture
def bolna_calls(monkeypatch):
    store: dict = {}
    monkeypatch.setattr(bolna, "get_execution", lambda eid: store.get(eid))
    monkeypatch.setattr(bolna, "resolve_execution", lambda cid: store.get(cid) or next((e for e in store.values() if e["telephony_data"]["provider_call_id"] == cid), None))

    def place(phone, ud):
        eid = f"ex{len(store) + 1}"
        store[eid] = {"id": eid, "agent_id": AGENT, "status": "in-progress", "user_number": "+919876543210", "telephony_data": {"provider_call_id": f"tel-{eid}"}}
        return eid
    monkeypatch.setattr(bolna, "place_call", place)
    return store


@pytest.fixture
def outbox(monkeypatch):
    sent: list[dict] = []
    monkeypatch.setattr(mailer, "configured", lambda: True)
    monkeypatch.setattr(mailer, "send", lambda to, subject, text: sent.append({"to": to, "subject": subject, "text": text}) or "id")
    return sent


def start(merchant="M-DEEPAK"):
    r = client.post("/api/v1/calls", json={"merchant_id": merchant, "phone": "+919876543210", "email": "owner@example.com"})
    assert r.status_code == 201
    return r.json()["ticket_id"]


def escalate(reason, call_id="tel-ex1"):
    return client.post("/api/v1/voice/tools/escalate_to_human", headers=AUTH, json={
        "call_id": call_id, "reason": reason, "summary": "s", "steps_attempted": ["none"], "recommended_action": "call back"}).json()


def status():
    with db() as d:
        return d.one("select transfer_status, transfer_failure from tm_calls")


def test_an_emergency_asks_the_agent_to_transfer(bolna_calls, outbox):
    start()
    r = escalate("fraud_or_legal")
    assert r["ok"] and r["transfer"] is True and r["transfer_tool"] == "transfer_call_support" and "connecting you" in r["say"]
    assert status()["transfer_status"] == "requested"


@pytest.mark.parametrize("reason", ["refund_above_limit", "settlement_on_hold", "unclear_request", "other"])
def test_other_escalations_stay_a_callback(bolna_calls, outbox, reason):
    start()
    r = escalate(reason)
    assert r["ok"] and r["transfer"] is False and "call" not in r.get("transfer_tool", "") and "person will follow up" in r["say"]
    assert status()["transfer_status"] is None


def test_without_a_support_number_even_an_emergency_is_a_callback(bolna_calls, outbox, monkeypatch):
    monkeypatch.setattr(settings, "support_transfer_number", "")
    start()
    assert escalate("fraud_or_legal")["transfer"] is False
    assert status()["transfer_status"] is None


def test_a_malformed_number_is_treated_as_not_configured(monkeypatch):
    monkeypatch.setattr(settings, "support_transfer_number", "98765")
    assert bolna.transfer_number() is None


def test_the_transfer_tool_and_prompt_exist_only_with_a_number(monkeypatch):
    names = [t["name"] for t in bolna.tool_definitions("https://x.example.com")]
    assert "transfer_call_support" in names and len(names) == 10
    t = next(t for t in bolna.tool_definitions("https://x.example.com") if t["name"] == "transfer_call_support")
    assert t["value"]["param"]["call_transfer_number"] == DEST and "emergenc" not in str(t["parameters"]).lower()
    assert "call transfer_call_support" in bolna.voice_prompt()
    monkeypatch.setattr(settings, "support_transfer_number", "")
    assert "transfer_call_support" not in [t["name"] for t in bolna.tool_definitions("https://x.example.com")]
    assert "transfer_call_support" not in bolna.voice_prompt()


def no_failure_alert(outbox) -> bool:
    return not any("not transferred" in m["subject"] for m in outbox)


def event(bolna_calls, **ex):
    bolna_calls["ex1"].update(ex)
    assert client.post("/api/v1/voice/events", json={"id": "ex1"}).status_code == 200


@pytest.mark.parametrize("data,expected", [
    ({"status": "ringing"}, "attempted"),
    ({"status": "in-progress"}, "transferred"),
    ({"status": "completed", "duration": "42"}, "transferred"),
])
def test_bolnas_report_moves_the_transfer_forward(bolna_calls, outbox, data, expected):
    start(); escalate("fraud_or_legal")
    event(bolna_calls, transfer_call_data=data)
    assert status()["transfer_status"] == expected and no_failure_alert(outbox)


def test_a_request_alone_is_never_shown_as_transferred(bolna_calls, outbox):
    start(); escalate("fraud_or_legal")
    event(bolna_calls, status="in-progress")  # Bolna says nothing about a transfer leg yet
    assert status()["transfer_status"] == "requested"


def test_an_unanswered_transfer_alerts_support_to_call_back(bolna_calls, outbox):
    start(); escalate("fraud_or_legal")
    event(bolna_calls, transfer_call_data={"status": "no-answer"})
    s = status()
    assert s["transfer_status"] == "failed" and "no-answer" in s["transfer_failure"]
    mail = next(m for m in outbox if "not transferred" in m["subject"])
    assert mail["to"] == "support@example.com" and "+919876543210" in mail["text"] and "Deepak" in mail["text"]
    with db() as d:  # the merchant's number is emailed to support only, never stored
        assert "9876543210" not in str(d.all("select * from tm_calls"))


def test_a_call_that_ends_with_no_connected_transfer_is_a_failure(bolna_calls, outbox):
    start(); escalate("fraud_or_legal")
    event(bolna_calls, status="call-disconnected", transcript="user: hi")
    assert status()["transfer_status"] == "failed" and any("not transferred" in m["subject"] for m in outbox)


def test_a_finished_transfer_does_not_move_again(bolna_calls, outbox):
    start(); escalate("fraud_or_legal")
    event(bolna_calls, transfer_call_data={"status": "in-progress"})
    event(bolna_calls, status="call-disconnected", transfer_call_data={"status": "no-answer"})
    assert status()["transfer_status"] == "transferred" and no_failure_alert(outbox)


def test_ticket_detail_shows_the_transfer(bolna_calls, outbox):
    tid = start(); escalate("fraud_or_legal")
    event(bolna_calls, transfer_call_data={"status": "in-progress"})
    # the API needs a session when sign-in is on; here it is off
    assert client.get(f"/api/v1/tickets/{tid}").json()["call"]["transfer_status"] == "transferred"
