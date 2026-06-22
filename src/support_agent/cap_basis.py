"""resolve_cap_basis -- a tool for the Domain 1 contract reviewer (cross-domain).

A formula cap ("liability shall not exceed the fees paid in the trailing 12
months") references an external figure. Resolving it is a Domain 2 tool problem,
and it is the SAME access-failure-vs-valid-empty pattern as lookup_order, pointed
at a fee service:

  - fee service unreachable -> access failure: isError True, transient.
  - no fees on record       -> valid empty: isError False, resolved_basis 0.

The confident lie to avoid is collapsing "unreachable" into "fees = $0", which
makes an unbounded cap read as zero exposure and clears the reviewer's send gate
on a fabricated number. So the access failure carries NO resolved_basis at all.

What the contract coordinator then DOES with an unresolved cap -- escalate rather
than fabricate a clean "no exposure" verdict -- is Domain 5 (load-bearing
failure). It is flagged there, not solved here. This module's only job is to
return a categorized, truthful UNKNOWN instead of a fake zero.
"""

from typing import Protocol

from support_agent import errors


class FeeServiceUnreachableError(Exception):
    """The fee service could not be reached; the lookup did NOT run."""


class FeeService(Protocol):
    def trailing_fees(self, account_id: str) -> float | None: ...


class StubFeeService:
    def __init__(self, *, fees: dict[str, float] | None = None, unreachable: bool = False):
        self._fees = fees or {}
        self._unreachable = unreachable

    def trailing_fees(self, account_id: str) -> float | None:
        if self._unreachable:
            raise FeeServiceUnreachableError
        return self._fees.get(account_id)  # None == no fees on record (genuine empty)


def fee_service_unreachable(account_id: str) -> dict:
    return errors.mcp_error(
        f"Could not reach the fee service to resolve trailing-12-month fees for "
        f"account {account_id} -- the lookup did not run, so the cap basis is "
        "UNKNOWN. Do NOT treat this as $0. Return this error upstream with its "
        "category intact so the contract coordinator can escalate instead of "
        "computing a cap from a missing number.",
        category="transient", retryable=True, code="FEE_SERVICE_UNREACHABLE",
    )


def no_fees_on_record(account_id: str) -> dict:
    return errors.mcp_ok(
        "No fees recorded for this account. The fee service responded successfully; "
        "the trailing-12-month fee total is genuinely $0. A fee-based cap therefore "
        "resolves to $0 -- this means a near-zero liability ceiling, so confirm it "
        "is intended before relying on it.",
        code="NO_FEES_ON_RECORD",
        resolved_basis=0,
    )


def resolve_cap_basis(args: dict, fee_service: FeeService) -> dict:
    account_id = str(args.get("account_id") or "").strip()
    if not account_id:
        return errors.mcp_error(
            "account_id is required to resolve a fee-based cap basis; received an "
            "empty value. Re-call resolve_cap_basis with the account id.",
            category="validation", retryable=True, code="INVALID_ACCOUNT_ID",
        )

    try:
        fees = fee_service.trailing_fees(account_id)
    except FeeServiceUnreachableError:
        return fee_service_unreachable(account_id)

    if fees is None:
        return no_fees_on_record(account_id)

    return errors.mcp_ok(
        f"Trailing-12-month fees for account {account_id} resolve to ${fees:,.2f}.",
        code="CAP_BASIS_RESOLVED",
        resolved_basis=fees,
    )
