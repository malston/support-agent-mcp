"""Deliverable 3: four categorized errors, each with correct isError + _meta.

The handlers return these objects (they never throw); the category dictates
recovery. The rubric's sharp edge is the BUSINESS error: a failed intent
("already refunded") is isError:true / retryable:false -- NOT a valid empty result.
"""

from support_agent.backend import StubBackend
from support_agent.handlers import issue_refund, lookup_order

ORDER = {
    "order_id": "12345", "status": "shipped", "line_items": [],
    "totals": {"grand_total": 42.0}, "shipment": {"carrier": "UPS", "tracking": "1Z"},
    "customer_id": "cust-1",
}


def _be(**kw) -> StubBackend:
    return StubBackend(orders={"12345": ORDER}, **kw)


def _text(result: dict) -> str:
    return result["content"][0]["text"]


def test_transient_timeout_is_retryable():
    r = lookup_order({"order_id": "12345"}, _be(timeout=True))
    assert r["isError"] is True
    assert r["_meta"]["error_category"] == "transient"
    assert r["_meta"]["retryable"] is True


def test_validation_missing_order_id_is_fixable_then_retryable():
    r = lookup_order({"order_id": ""}, _be())
    assert r["isError"] is True
    assert r["_meta"]["error_category"] == "validation"
    assert r["_meta"]["retryable"] is True
    # prose must steer the model to FIX args, not replay the same bad call
    assert "do not retry with the same" in _text(r).lower()


def test_business_already_refunded_is_error_not_empty_result():
    backend = StubBackend(orders={"12345": ORDER}, refunded={"12345": ("rf_88c2", "2026-05-02")})
    r = issue_refund({"order_id": "12345"}, backend)
    assert r["isError"] is True           # a failed intent IS an error ...
    assert r["_meta"]["error_category"] == "business"
    assert r["_meta"]["retryable"] is False  # ... and retrying cannot help
    assert "already" in _text(r).lower()


def test_permission_unauthorized_is_not_retryable():
    r = issue_refund({"order_id": "12345"}, _be(authorized=False))
    assert r["isError"] is True
    assert r["_meta"]["error_category"] == "permission"
    assert r["_meta"]["retryable"] is False


def test_every_error_object_carries_the_meta_contract():
    r = lookup_order({"order_id": ""}, _be())
    assert isinstance(r["content"], list) and r["content"][0]["type"] == "text"
    for key in ("error_category", "retryable", "code"):
        assert key in r["_meta"]


def test_successful_lookup_is_not_an_error():
    r = lookup_order({"order_id": "12345"}, _be())
    assert r["isError"] is False
    assert r["_meta"]["error_category"] is None


def test_shared_error_recovery_text_names_the_calling_tool():
    # Regression: the shared validation error is reused by both handlers; the
    # recovery prose must name the tool that was actually called.
    from_lookup = lookup_order({"order_id": ""}, _be())["content"][0]["text"]
    from_refund = issue_refund({"order_id": ""}, _be())["content"][0]["text"]
    assert "lookup_order" in from_lookup
    assert "issue_refund" in from_refund
    assert "lookup_order" not in from_refund


def test_refund_on_a_nonexistent_order_is_a_business_failure_not_success():
    # The write-side confident lie: a refund must not be minted for a missing order.
    r = issue_refund({"order_id": "00000"}, _be())  # 00000 not in the orders
    assert r["isError"] is True
    assert r["_meta"]["error_category"] == "business"
    assert r["_meta"]["retryable"] is False
    assert r["_meta"]["code"] == "REFUND_NO_SUCH_ORDER"


def test_refund_transient_branches_are_categorized():
    timed_out = issue_refund({"order_id": "12345"}, _be(timeout=True))
    assert timed_out["isError"] is True
    assert timed_out["_meta"]["error_category"] == "transient"

    unreachable = issue_refund({"order_id": "12345"}, _be(unreachable=True))
    assert unreachable["isError"] is True
    assert unreachable["_meta"]["error_category"] == "transient"
    assert unreachable["_meta"]["code"] == "ORDERS_DB_UNREACHABLE"


def test_handlers_do_not_throw_on_none_args():
    # The never-throw contract holds in the handler, not just in dispatch.
    assert lookup_order(None, _be())["_meta"]["error_category"] == "validation"
    assert issue_refund(None, _be())["_meta"]["error_category"] == "validation"
