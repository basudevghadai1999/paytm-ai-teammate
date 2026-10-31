from app.core.db import db
from app.tickets import create_ticket
from app.tools import Ctx, execute


def run(merchant: str, tool: str, **args):
    with db() as d:
        tid = create_ticket(d, merchant, "hi")
        return execute(Ctx(d, tid, merchant, 1), tool, args), tid


def test_refund_success_marks_refunded():
    (res, ok), _ = run("M-KUMAR", "initiate_refund", transaction_id="TXN-3001")
    assert ok and res["amount_inr"] == 1200
    with db() as d:
        assert d.one("select status from tm_transactions where id='TXN-3001'")["status"] == "refunded"


def test_refund_failed_debited_allowed():
    (res, ok), _ = run("M-PRIYA", "initiate_refund", transaction_id="TXN-2001")
    assert ok and res["status"] == "initiated"


def test_refund_above_limit_blocked_and_logged():
    (res, ok), tid = run("M-RAHUL", "initiate_refund", transaction_id="TXN-5001")
    assert not ok and res["must_escalate"]
    with db() as d:
        assert d.one("select status from tm_transactions where id='TXN-5001'")["status"] == "success"
        row = d.one("select allowed from tm_actions where ticket_id=:t", t=tid)
        assert row["allowed"] is False


def test_double_refund_blocked():
    run("M-KUMAR", "initiate_refund", transaction_id="TXN-3001")
    (res, ok), _ = run("M-KUMAR", "initiate_refund", transaction_id="TXN-3001")
    assert not ok and "already been refunded" in res["error"]


def test_other_merchants_transaction_not_visible():
    (res, ok), _ = run("M-KUMAR", "initiate_refund", transaction_id="TXN-5001")
    assert not ok and "No such transaction" in res["error"]
    (res, ok), _ = run("M-KUMAR", "get_transaction", transaction_id="TXN-5001")
    assert not ok


def test_replacement_only_when_faulty():
    (res, ok), _ = run("M-SHARMA", "raise_device_replacement")
    assert not ok
    (res, ok), _ = run("M-ANITA", "raise_device_replacement")
    assert ok
    (res, ok), _ = run("M-ANITA", "raise_device_replacement")  # idempotent: second call refused
    assert not ok


def test_ask_merchant_once():
    with db() as d:
        tid = create_ticket(d, "M-JOSEPH", "where is my money")
        _, ok = execute(Ctx(d, tid, "M-JOSEPH", 1), "ask_merchant", {"question": "Which settlement?"})
        assert ok
        res, ok = execute(Ctx(d, tid, "M-JOSEPH", 2), "ask_merchant", {"question": "And which date?"})
        assert not ok and res["must_escalate"]


def test_resolve_strips_unconfirmed_refund_claim():
    with db() as d:
        tid = create_ticket(d, "M-SHARMA", "settlement?")
        res, ok = execute(Ctx(d, tid, "M-SHARMA", 1), "resolve_ticket", {
            "category": "settlement_delay", "summary": "s", "reply_to_merchant": "Your refund has been processed."})
        assert ok and "refund" not in res["reply"].lower()


def test_unknown_tool_and_bad_args():
    (res, ok), _ = run("M-KUMAR", "drop_tables")
    assert not ok
    (res, ok), _ = run("M-KUMAR", "get_transaction")  # missing transaction_id
    assert not ok
