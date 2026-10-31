import pytest
from fastapi.testclient import TestClient

from app import bolna, mailer, voice
from app.core.config import settings
from app.core.db import db
from app.main import app
from app.tickets import create_ticket
from app.tools import Ctx, execute

client = TestClient(app)


class Outbox(list):
    """Mail sent during a test; set .failing to simulate a Resend outage."""
    failing = False

    def fail(self, v: bool) -> None:
        self.failing = v


@pytest.fixture
def outbox(monkeypatch):
    sent = Outbox()
    monkeypatch.setattr(mailer, "configured", lambda: True)

    def send(to, subject, text):
        if sent.failing:
            raise mailer.MailError("down")
        sent.append({"to": to, "subject": subject, "text": text})
        return f"mail-{len(sent)}"

    monkeypatch.setattr(mailer, "send", send)
    monkeypatch.setattr(settings, "support_alert_email", "support@example.com")
    return sent


def ticket(merchant="M-PRIYA", email="owner@example.com") -> int:
    with db() as d:
        return create_ticket(d, merchant, "help", email)


def run(tid, tool, merchant="M-PRIYA", **args):
    with db() as d:
        step = d.one("select coalesce(max(step),0)+1 as s from tm_actions where ticket_id=:t", t=tid)["s"]
        return execute(Ctx(d, tid, merchant, step), tool, args)


def test_send_notification_emails_the_address_on_file(outbox):
    tid = ticket()
    res, ok = run(tid, "send_notification", message="Your refund of INR 850 was started.")
    assert ok and res["channel"] == "email"
    assert outbox[0]["to"] == "owner@example.com" and "refund" in outbox[0]["text"]
    with db() as d:
        m = d.one("select channel, provider_id from tm_messages where kind='notification'")
        assert m == {"channel": "email", "provider_id": "mail-1"}


def test_without_an_address_it_is_logged_not_emailed(outbox):
    tid = ticket(email=None)
    res, ok = run(tid, "send_notification", message="Hello")
    assert ok and res["channel"] == "simulated" and "Do not tell" in res["note"] and outbox == []


def test_email_failure_is_blocked_so_the_agent_cannot_claim_it(outbox):
    outbox.fail(True)
    res, ok = run(ticket(), "send_notification", message="Hello")
    assert not ok and "could not be sent" in res["error"]
    with db() as d:
        assert d.one("select count(*) as n from tm_messages where kind='notification'")["n"] == 0


def test_resolve_sends_one_acknowledgement_email(outbox):
    tid = ticket()
    run(tid, "initiate_refund", transaction_id="TXN-2001")
    run(tid, "resolve_ticket", category="failed_payment", summary="s", reply_to_merchant="A refund of INR 850 has been initiated.")
    assert len(outbox) == 1 and "resolved" in outbox[0]["subject"]


def test_no_second_email_when_the_agent_already_sent_one(outbox):
    tid = ticket()
    run(tid, "send_notification", message="Refund started.")
    run(tid, "resolve_ticket", category="other", summary="s", reply_to_merchant="Done, closing your ticket.")
    assert len(outbox) == 1


def test_email_claim_is_stripped_when_no_email_was_sent(outbox):
    tid = ticket(email=None)
    res, ok = run(tid, "resolve_ticket", category="other", summary="s", reply_to_merchant="I have sent a confirmation to your email.")
    assert ok and "email" not in res["reply"].lower()


def test_emergency_escalation_alerts_human_support(outbox):
    tid = ticket()
    res, ok = run(tid, "escalate_to_human", reason="fraud_or_legal", summary="Merchant reports a hack.",
                  steps_attempted=[], recommended_action="Call back now.")
    assert ok
    to = {m["to"] for m in outbox}
    assert to == {"owner@example.com", "support@example.com"}
    urgent = next(m for m in outbox if m["to"] == "support@example.com")
    assert "URGENT" in urgent["subject"] and "Call back now." in urgent["text"]
    with db() as d:
        assert d.one("select alerted_at from tm_escalations")["alerted_at"] is not None


def test_ordinary_escalation_does_not_alert_support(outbox):
    tid = ticket("M-RAHUL")
    run(tid, "escalate_to_human", "M-RAHUL", reason="refund_above_limit", summary="s", steps_attempted=[], recommended_action="r")
    assert {m["to"] for m in outbox} == {"owner@example.com"}


def test_a_mail_outage_never_blocks_the_ticket(outbox):
    outbox.fail(True)
    tid = ticket()
    _, ok = run(tid, "escalate_to_human", reason="fraud_or_legal", summary="s", steps_attempted=[], recommended_action="r")
    assert ok
    with db() as d:
        assert d.one("select status from tm_tickets where id=:t", t=tid)["status"] == "escalated"


# --- post-call safety net -------------------------------------------------

AGENT = "agent-paytm"


@pytest.fixture
def ended_call(monkeypatch, outbox):
    monkeypatch.setattr(settings, "bolna_paytm_agent_id", AGENT)
    monkeypatch.setattr(settings, "bolna_api_key", "k")
    with db() as d:
        tid = create_ticket(d, "M-DEEPAK", "", "owner@example.com")
        d.run("update tm_tickets set channel='voice' where id=:t", t=tid)
        d.run("insert into tm_calls (ticket_id, merchant_id, provider_call_id) values (:t,'M-DEEPAK','ex1')", t=tid)

    def make(transcript):
        monkeypatch.setattr(bolna, "get_execution", lambda eid: {
            "id": "ex1", "agent_id": AGENT, "status": "completed", "transcript": transcript, "telephony_data": {"duration": "30"}})
    return tid, make


def test_fraud_said_on_a_call_escalates_even_after_the_agent_resolved(ended_call, outbox):
    tid, make = ended_call
    run(tid, "resolve_ticket", "M-DEEPAK", category="other", summary="s", reply_to_merchant="All sorted.")
    make("assistant: How can I help?\nuser: Someone hacked my account and I will go to the police\nassistant: All sorted.")
    assert client.post("/api/v1/voice/events", json={"id": "ex1"}).status_code == 200
    with db() as d:
        t = d.one("select status, resolved_by from tm_tickets where id=:t", t=tid)
        assert t["status"] == "escalated" and t["resolved_by"] is None
        assert d.one("select reason from tm_escalations")["reason"] == "fraud_or_legal"
    assert any(m["to"] == "support@example.com" for m in outbox)


def test_the_agents_own_words_do_not_trigger_the_screen(ended_call):
    tid, make = ended_call
    run(tid, "resolve_ticket", "M-DEEPAK", category="other", summary="s", reply_to_merchant="Done.")
    make("assistant: Please do not share OTPs, that could be fraud.\nuser: Okay thanks, my settlement is late")
    client.post("/api/v1/voice/events", json={"id": "ex1"})
    with db() as d:
        assert d.one("select status from tm_tickets where id=:t", t=tid)["status"] == "resolved"


def test_hindi_fraud_words_are_caught(ended_call):
    tid, make = ended_call
    make("user: मेरे साथ धोखा हुआ है और मैं पुलिस के पास जाऊंगा")
    client.post("/api/v1/voice/events", json={"id": "ex1"})
    with db() as d:
        assert d.one("select status from tm_tickets where id=:t", t=tid)["status"] == "escalated"


def test_out_of_scope_close_sends_no_acknowledgement_email(outbox):
    tid = ticket()
    _, ok = run(tid, "resolve_ticket", category="out_of_scope", summary="s", reply_to_merchant="I can only help with Paytm support.")
    assert ok and outbox == []
