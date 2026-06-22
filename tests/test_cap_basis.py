"""Cross-domain extension: resolve_cap_basis for the Domain 1 contract reviewer.

Same access-failure-vs-valid-empty pattern as deliverable 4, pointed at a fee
service. The confident lie to avoid: collapsing "unreachable" into "fees = $0",
which makes an unbounded formula cap read as zero exposure.
"""

from support_agent.cap_basis import StubFeeService, resolve_cap_basis


def _text(result: dict) -> str:
    return result["content"][0]["text"]


def test_fee_service_unreachable_is_an_access_failure():
    r = resolve_cap_basis({"account_id": "acme-corp"}, StubFeeService(unreachable=True))
    assert r["isError"] is True
    assert r["_meta"]["error_category"] == "transient"
    assert r["_meta"]["retryable"] is True
    assert r["_meta"]["code"] == "FEE_SERVICE_UNREACHABLE"
    assert "unknown" in _text(r).lower()
    assert "do not treat this as $0" in _text(r).lower()


def test_no_fees_on_record_is_a_valid_empty_result_resolving_to_zero():
    r = resolve_cap_basis({"account_id": "newco"}, StubFeeService(fees={}))
    assert r["isError"] is False
    assert r["_meta"]["code"] == "NO_FEES_ON_RECORD"
    assert r["_meta"]["resolved_basis"] == 0
    assert "no fees recorded" in _text(r).lower()


def test_actual_fees_resolve_to_the_number():
    r = resolve_cap_basis({"account_id": "acme-corp"}, StubFeeService(fees={"acme-corp": 250000.0}))
    assert r["isError"] is False
    assert r["_meta"]["resolved_basis"] == 250000.0


def test_missing_account_id_is_a_validation_error():
    r = resolve_cap_basis({"account_id": ""}, StubFeeService(fees={}))
    assert r["isError"] is True
    assert r["_meta"]["error_category"] == "validation"
    assert r["_meta"]["retryable"] is True
    assert r["_meta"]["code"] == "INVALID_ACCOUNT_ID"


def test_unreachable_and_empty_are_distinguishable_and_unreachable_has_no_number():
    unreachable = resolve_cap_basis({"account_id": "x"}, StubFeeService(unreachable=True))
    empty = resolve_cap_basis({"account_id": "x"}, StubFeeService(fees={}))
    assert unreachable["isError"] != empty["isError"]
    # the confident lie defended: an outage must never resolve to a basis number
    assert "resolved_basis" not in unreachable["_meta"]
    assert empty["_meta"]["resolved_basis"] == 0
