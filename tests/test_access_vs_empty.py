"""Deliverable 4: access-failure vs. valid-empty-result.

These two look alike ("we have no order to show you") but mean opposite things.
The distinguishing bit is isError. Collapsing them is the confident-lie failure:
the agent tells the customer "no such order" when the database was merely down.
"""

from support_agent.backend import StubBackend
from support_agent.handlers import lookup_order

ORDER = {
    "order_id": "12345", "status": "shipped", "line_items": [],
    "totals": {}, "shipment": {}, "customer_id": "cust-1",
}


def _be(**kw) -> StubBackend:
    return StubBackend(orders={"12345": ORDER}, **kw)


def _text(result: dict) -> str:
    return result["content"][0]["text"]


def test_order_genuinely_absent_is_a_valid_empty_result():
    r = lookup_order({"order_id": "99999"}, _be())
    assert r["isError"] is False                 # the query SUCCEEDED, zero rows
    assert r["_meta"]["code"] == "ORDER_NOT_FOUND"
    assert "no order found" in _text(r).lower()


def test_db_unreachable_is_an_access_failure():
    r = lookup_order({"order_id": "99999"}, _be(unreachable=True))
    assert r["isError"] is True                  # the query did NOT run
    assert r["_meta"]["error_category"] == "transient"
    assert r["_meta"]["retryable"] is True
    assert r["_meta"]["code"] == "ORDERS_DB_UNREACHABLE"


def test_the_two_are_distinguishable_by_iserror():
    absent = lookup_order({"order_id": "99999"}, _be())
    unreachable = lookup_order({"order_id": "99999"}, _be(unreachable=True))
    assert absent["isError"] != unreachable["isError"]


def test_unreachable_never_asserts_the_order_does_not_exist():
    # The confident lie defended: an outage must not render as "no such order".
    r = lookup_order({"order_id": "99999"}, _be(unreachable=True))
    assert "no order found" not in _text(r).lower()
    assert "unknown" in _text(r).lower()
