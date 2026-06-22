"""Tool handlers: turn a backend outcome into a categorized MCP result.

Handlers NEVER throw -- a thrown exception escapes the tool-use loop and the model
cannot recover from it. Every failure mode is returned as a result object with
isError set, so the failure stays inside the loop as content the model acts on.

Each handler passes its OWN tool name into the shared error builders, so the
recovery prose names the right tool for the context.

The mapping each handler enforces:
  - missing/blank args        -> validation
  - backend timeout           -> transient
  - backend unreachable       -> access failure (transient, but "UNKNOWN", not "absent")
  - genuine miss (None)       -> valid empty result (isError False)
  - domain-rule block         -> business (retryable False)
  - missing scope             -> permission (retryable False)
"""

from support_agent import errors
from support_agent.backend import (
    AlreadyRefundedError,
    BackendTimeoutError,
    BackendUnreachableError,
    CustomersBackend,
    NotAuthorizedError,
    OrderNotFoundError,
    OrdersBackend,
)


def lookup_order(args: dict, backend: OrdersBackend) -> dict:
    tool = "lookup_order"
    args = args or {}  # the never-throw contract lives here, not in the caller
    order_id = str(args.get("order_id") or "").strip()
    if not order_id:
        return errors.invalid_order_id(str(args.get("order_id") or ""), tool)

    try:
        order = backend.get_order(order_id)
    except BackendTimeoutError:
        return errors.order_timeout(order_id, tool)
    except BackendUnreachableError:
        return errors.orders_db_unreachable(order_id, tool)

    if order is None:
        return errors.order_not_found(order_id)  # valid empty -- NOT an error

    return errors.mcp_ok(
        f"Order #{order_id}: status {order.get('status', 'unknown')}, total "
        f"{order.get('totals', {}).get('grand_total', 'n/a')}.",
        code="ORDER_FOUND",
        order=order,
    )


def get_customer(args: dict, backend: CustomersBackend) -> dict:
    tool = "get_customer"
    args = args or {}
    customer_id = str(args.get("customer_id") or "").strip()
    if not customer_id:
        return errors.invalid_customer_id(str(args.get("customer_id") or ""), tool)

    try:
        customer = backend.get_customer(customer_id)
    except BackendTimeoutError:
        return errors.customer_timeout(customer_id, tool)
    except BackendUnreachableError:
        return errors.customers_db_unreachable(customer_id, tool)

    if customer is None:
        return errors.customer_not_found(customer_id)  # valid empty -- NOT an error

    return errors.mcp_ok(
        f"Customer {customer_id}: {customer.get('email', 'n/a')}.",
        code="CUSTOMER_FOUND",
        customer=customer,
    )


def issue_refund(args: dict, backend: OrdersBackend) -> dict:
    tool = "issue_refund"
    args = args or {}
    order_id = str(args.get("order_id") or "").strip()
    if not order_id:
        return errors.invalid_order_id(str(args.get("order_id") or ""), tool)

    try:
        result = backend.refund(order_id, args.get("amount"))
    except NotAuthorizedError:
        return errors.refund_forbidden()
    except OrderNotFoundError:
        return errors.refund_no_such_order(order_id, tool)
    except AlreadyRefundedError as exc:
        return errors.already_refunded(order_id, exc.refund_id, exc.date)
    except BackendTimeoutError:
        return errors.order_timeout(order_id, tool)
    except BackendUnreachableError:
        return errors.orders_db_unreachable(order_id, tool)

    return errors.mcp_ok(
        f"Refund {result['refund_id']} issued against order #{order_id}.",
        code="REFUND_ISSUED",
        refund=result,
    )
