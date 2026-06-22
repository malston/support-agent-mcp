"""Principle: categories must survive propagation.

A subagent that calls resolve_cap_basis and hands the result up must preserve
error_category + retryable, so the coordinator's recovery stays deterministic. A
subagent that flattens the result to "it failed" destroys that contract -- the
coordinator can no longer tell retry-and-continue from escalate.
"""

from support_agent.cap_basis import StubFeeService
from support_agent.propagation import (
    coordinator_receive,
    flatten_to_failed,
    subagent_resolve_cap,
)


def test_category_and_retryable_survive_subagent_to_coordinator():
    result = subagent_resolve_cap("acme-corp", StubFeeService(unreachable=True))
    received = coordinator_receive(result)
    assert received.resolved is False
    assert received.error_category == "transient"
    assert received.retryable is True
    assert received.code == "FEE_SERVICE_UNREACHABLE"


def test_valid_empty_propagates_as_resolved_zero_not_an_error():
    result = subagent_resolve_cap("newco", StubFeeService(fees={}))
    received = coordinator_receive(result)
    assert received.resolved is True
    assert received.error_category is None
    assert received.basis == 0


def test_flattening_destroys_the_recovery_contract():
    # The distractor: collapsing the categorized error to a bare string.
    result = subagent_resolve_cap("acme-corp", StubFeeService(unreachable=True))
    flat = flatten_to_failed(result)
    assert flat == "it failed"
    assert "transient" not in flat and "retry" not in flat
