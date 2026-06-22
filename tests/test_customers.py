"""get_customer handler: the second read tool, same access-vs-empty discipline.

Added with the MCP server so all three tools on the surface are executable. Mirrors
lookup_order: validation / timeout / unreachable / valid-empty / found, and the
recovery prose names get_customer (not lookup_order).
"""

from support_agent.backend import StubBackend
from support_agent.handlers import get_customer

CUSTOMER = {
    "customer_id": "cust-1", "email": "casey@example.com",
    "order_ids": ["12345"], "loyalty_tier": "gold",
}


def _be(**kw) -> StubBackend:
    return StubBackend(customers={"cust-1": CUSTOMER}, **kw)


def _text(result: dict) -> str:
    return result["content"][0]["text"]


def test_customer_found_is_ok():
    r = get_customer({"customer_id": "cust-1"}, _be())
    assert r["isError"] is False
    assert r["_meta"]["code"] == "CUSTOMER_FOUND"


def test_missing_customer_id_is_validation_naming_get_customer():
    r = get_customer({"customer_id": ""}, _be())
    assert r["isError"] is True
    assert r["_meta"]["error_category"] == "validation"
    assert "do not retry with the same" in _text(r).lower()
    assert "get_customer" in _text(r)
    assert "lookup_order" not in _text(r)


def test_customer_absent_is_a_valid_empty_result():
    r = get_customer({"customer_id": "ghost"}, _be())
    assert r["isError"] is False
    assert r["_meta"]["code"] == "CUSTOMER_NOT_FOUND"
    assert "no customer found" in _text(r).lower()


def test_customer_db_unreachable_is_an_access_failure():
    r = get_customer({"customer_id": "ghost"}, _be(unreachable=True))
    assert r["isError"] is True
    assert r["_meta"]["error_category"] == "transient"
    assert r["_meta"]["code"] == "CUSTOMERS_DB_UNREACHABLE"
    assert "no customer found" not in _text(r).lower()
    assert "unknown" in _text(r).lower()
