from app.agent import run_ticket
from app.core.db import db
from app.llm import LLMError
from app.tickets import create_ticket, metrics
from tests.conftest import ScriptedLLM, call, msg


def new_ticket(merchant: str, text: str) -> int:
    with db() as d:
        return create_ticket(d, merchant, text)


def ticket(tid: int) -> dict:
    with db() as d:
        return d.one("select * from tm_tickets where id=:t", t=tid)


def test_refund_flow_resolves_by_ai():
    tid = new_ticket("M-PRIYA", "customer paid but I did not get it")
    llm = ScriptedLLM([
        msg(call("list_recent_transactions")),
        msg(call("initiate_refund", transaction_id="TXN-2001")),
        msg(call("resolve_ticket", category="failed_payment", summary="refunded failed txn",
                 reply_to_merchant="A refund of INR 850 has been initiated for transaction TXN-2001.")),
    ])
    run_ticket(tid, llm)
    t = ticket(tid)
    assert t["status"] == "resolved" and t["resolved_by"] == "ai" and t["closed_at"]


def test_high_value_refund_escalates_with_package():
    tid = new_ticket("M-RAHUL", "refund this 15,000 payment")
    llm = ScriptedLLM([
        msg(call("initiate_refund", transaction_id="TXN-5001")),
        msg(call("escalate_to_human", reason="refund_above_limit", summary="Merchant wants INR 15000 refunded.",
                 steps_attempted=["initiate_refund TXN-5001 blocked"], recommended_action="Verify and approve manually.")),
    ])
    run_ticket(tid, llm)
    assert ticket(tid)["status"] == "escalated"
    with db() as d:
        e = d.one("select * from tm_escalations where ticket_id=:t", t=tid)
        assert e["reason"] == "refund_above_limit" and e["recommended_action"]
        assert d.one("select status from tm_transactions where id='TXN-5001'")["status"] == "success"


def test_fraud_escalates_without_calling_model():
    tid = new_ticket("M-DEEPAK", "This is fraud! I will go to the police.")
    llm = ScriptedLLM([])
    run_ticket(tid, llm)
    assert llm.calls == 0 and ticket(tid)["status"] == "escalated"


def test_llm_error_escalates():
    tid = new_ticket("M-SHARMA", "where is my settlement")
    run_ticket(tid, ScriptedLLM([LLMError("down")]))
    t = ticket(tid)
    assert t["status"] == "escalated"
    with db() as d:
        assert d.one("select reason from tm_escalations where ticket_id=:t", t=tid)["reason"] == "llm_unavailable"


def test_step_limit_escalates():
    tid = new_ticket("M-SHARMA", "settlement?")
    run_ticket(tid, ScriptedLLM([msg(call("get_settlement_status")) for _ in range(20)]))
    with db() as d:
        assert d.one("select reason from tm_escalations where ticket_id=:t", t=tid)["reason"] == "step_limit"


def test_clarify_then_resume():
    tid = new_ticket("M-JOSEPH", "where is my money?")
    run_ticket(tid, ScriptedLLM([msg(call("get_settlement_status")), msg(call("ask_merchant", question="Which amount?"))]))
    assert ticket(tid)["status"] == "awaiting_merchant"
    with db() as d:
        d.run("insert into tm_messages (ticket_id, role, content) values (:t, 'merchant', 'the 8200 one')", t=tid)
    run_ticket(tid, ScriptedLLM([msg(call("resolve_ticket", category="settlement_delay", summary="explained",
                                          reply_to_merchant="Your INR 8200 settlement is expected tomorrow."))]))
    assert ticket(tid)["status"] == "resolved"


def test_metrics_counts():
    tid = new_ticket("M-RAHUL", "refund 15,000")
    run_ticket(tid, ScriptedLLM([msg(call("initiate_refund", transaction_id="TXN-5001")),
                                 msg(call("escalate_to_human", reason="refund_above_limit", summary="s",
                                          steps_attempted=[], recommended_action="r"))]))
    with db() as d:
        m = metrics(d)
    assert m["total_tickets"] == 1 and m["blocked_actions"] == 1 and m["unsafe_actions"] == 0
    assert m["escalations_by_reason"][0]["reason"] == "refund_above_limit"


def test_out_of_scope_close_is_excluded_from_the_rate():
    tid = new_ticket("M-SHARMA", "tell me a joke")
    run_ticket(tid, ScriptedLLM([msg(call("resolve_ticket", category="out_of_scope", summary="off topic",
                                          reply_to_merchant="I can only help with Paytm settlements, payments and soundbox. How can I help?"))]))
    assert ticket(tid)["status"] == "resolved"
    other = new_ticket("M-SHARMA", "where is my settlement")
    run_ticket(other, ScriptedLLM([msg(call("resolve_ticket", category="settlement_delay", summary="s", reply_to_merchant="Expected tomorrow."))]))
    with db() as d:
        m = metrics(d)
    assert m["total_tickets"] == 1 and m["out_of_scope"] == 1 and m["resolved_by_ai"] == 1 and m["auto_resolution_rate"] == 1.0


def test_prompts_carry_the_scope_rule():
    from app import bolna
    from app.agent import SYSTEM_PROMPT
    for p in (SYSTEM_PROMPT, bolna.VOICE_PROMPT):
        assert "Scope:" in p and "out_of_scope" in p and "do not answer it" in p
