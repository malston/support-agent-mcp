"""MCP result objects -- the content the model reasons over at recovery time.

Two builders carry the contract:
  - `mcp_error`: isError=True, with _meta {error_category, retryable, code}
  - `mcp_ok`:    isError=False, with _meta {error_category=None, retryable=False, code, ...}

The recovery prose is written for the MODEL: what happened, whether to retry, what
to do instead. Because the access-style errors (timeout / unreachable / invalid id /
not-found) are shared by more than one tool, the recovery text names the **calling
tool** -- passed in by the handler -- so it never directs the model to the wrong
tool. `error_category` + `retryable` are the recovery contract and must survive
propagation unflattened (see propagation.py).
"""

from typing import Literal

ErrorCategory = Literal["transient", "validation", "business", "permission"]


def mcp_error(text: str, *, category: ErrorCategory, retryable: bool, code: str) -> dict:
    return {
        "content": [{"type": "text", "text": text}],
        "isError": True,
        "_meta": {"error_category": category, "retryable": retryable, "code": code},
    }


def mcp_ok(text: str, *, code: str, **meta: object) -> dict:
    return {
        "content": [{"type": "text", "text": text}],
        "isError": False,
        "_meta": {"error_category": None, "retryable": False, "code": code, **meta},
    }


# ---- generic, tool-aware builders ------------------------------------------

def timeout_error(*, service: str, identifier: str, tool: str, code: str) -> dict:
    return mcp_error(
        f"The {service} timed out before returning {identifier}. This is a "
        "temporary problem on our side -- nothing is wrong with your request. Wait "
        f"a moment, then call {tool} again with the same arguments.",
        category="transient", retryable=True, code=code,
    )


def invalid_id_error(*, field: str, received: str, tool: str, code: str, hint: str = "") -> dict:
    shown = received if received else "an empty value"
    must_be = f" and must be {hint}" if hint else ""
    return mcp_error(
        f"{field} is required{must_be}; received {shown}. Re-call {tool} with a "
        f"valid {field}. Do NOT retry with the same empty value -- a verbatim retry "
        "will fail the same way.",
        category="validation", retryable=True, code=code,
    )


def unreachable_error(*, service: str, identifier: str, tool: str, code: str) -> dict:
    # ACCESS FAILURE: the query did not run. isError True; never claim absence.
    return mcp_error(
        f"Could not reach the {service} to look up {identifier} -- the query did "
        f"not run, so whether {identifier} exists is UNKNOWN. Do NOT report that "
        f"{identifier} does not exist. This is a temporary infrastructure failure; "
        f"wait and retry {tool} shortly.",
        category="transient", retryable=True, code=code,
    )


def not_found_result(*, label: str, identifier: str, next_hint: str, code: str) -> dict:
    # VALID EMPTY: the query ran and returned nothing. isError is False.
    return mcp_ok(
        f"No {label} found with {identifier}. The lookup ran successfully; there is "
        f"simply no such {label}. {next_hint}",
        code=code,
    )


# ---- order-tool wrappers ---------------------------------------------------

def order_timeout(order_id: str, tool: str) -> dict:
    return timeout_error(
        service="orders service", identifier=f"order #{order_id}", tool=tool,
        code="ORDERS_UPSTREAM_TIMEOUT",
    )


def invalid_order_id(received: str, tool: str) -> dict:
    return invalid_id_error(
        field="order_id", received=received, tool=tool, code="INVALID_ORDER_ID",
        hint='the numeric order number (for example "12345")',
    )


def orders_db_unreachable(order_id: str, tool: str) -> dict:
    return unreachable_error(
        service="orders database", identifier=f"order #{order_id}", tool=tool,
        code="ORDERS_DB_UNREACHABLE",
    )


def order_not_found(order_id: str) -> dict:
    return not_found_result(
        label="order", identifier=f"ID {order_id}", code="ORDER_NOT_FOUND",
        next_hint=(
            "Confirm the order number with the customer, or call get_customer to "
            "list this customer's order_ids."
        ),
    )


# ---- customer-tool wrappers ------------------------------------------------

def customer_timeout(customer_id: str, tool: str) -> dict:
    return timeout_error(
        service="customer service", identifier=f"customer {customer_id}", tool=tool,
        code="CUSTOMERS_UPSTREAM_TIMEOUT",
    )


def invalid_customer_id(received: str, tool: str) -> dict:
    return invalid_id_error(
        field="customer_id", received=received, tool=tool, code="INVALID_CUSTOMER_ID",
    )


def customers_db_unreachable(customer_id: str, tool: str) -> dict:
    return unreachable_error(
        service="customer database", identifier=f"customer {customer_id}", tool=tool,
        code="CUSTOMERS_DB_UNREACHABLE",
    )


def customer_not_found(customer_id: str) -> dict:
    return not_found_result(
        label="customer", identifier=f"ID {customer_id}", code="CUSTOMER_NOT_FOUND",
        next_hint="Confirm the customer id with the requester.",
    )


# ---- refund-tool wrappers (business / permission) --------------------------

def already_refunded(order_id: str, refund_id: str, date: str) -> dict:
    return mcp_error(
        f"Order #{order_id} was already fully refunded on {date} (refund_id "
        f"{refund_id}) and cannot be refunded again. This is a final business-rule "
        "outcome; retrying will not change it. If the customer disputes the existing "
        "refund, hand off to a human billing agent instead of re-attempting the refund.",
        category="business", retryable=False, code="ALREADY_REFUNDED",
    )


def refund_no_such_order(order_id: str, tool: str) -> dict:
    return mcp_error(
        f"Cannot refund order #{order_id}: no such order exists. The order was "
        "found to be absent, so there is nothing to refund -- this is a failed "
        "intent, not a retryable error. Confirm the order id with lookup_order "
        "before attempting a refund; do not re-call issue_refund with the same id.",
        category="business", retryable=False, code="REFUND_NO_SUCH_ORDER",
    )


def refund_forbidden() -> dict:
    return mcp_error(
        "You are not authorized to issue refunds. issue_refund requires the "
        "billing.refund scope, which this caller does not hold. Do NOT retry -- the "
        "same credentials will fail identically. Hand off to an agent or human "
        "operator that holds refund authority.",
        category="permission", retryable=False, code="REFUND_FORBIDDEN",
    )
