"""The e-commerce backend seam.

`OrdersBackend` is the protocol the handlers depend on; `StubBackend` is the
deterministic double the tests and offline demo drive (no network, no API key).
Its constructor flags let a test stage each distinct condition the handlers must
categorize: a timeout, an outage, a genuinely-absent order, an already-refunded
order, and an unauthorized caller.

The handlers translate these into categorized MCP results. The backend itself only
signals *what happened* -- it raises for the failure modes and returns None for a
genuine miss; deciding the error CATEGORY is the handler's job.
"""

from typing import Protocol


class BackendTimeoutError(Exception):
    """Upstream took too long; the call may succeed on retry (transient)."""


class BackendUnreachableError(Exception):
    """The datastore could not be reached; the query did NOT run (access failure)."""


class AlreadyRefundedError(Exception):
    """Domain rule: this order was already refunded (business)."""

    def __init__(self, refund_id: str, date: str):
        super().__init__(f"already refunded ({refund_id} on {date})")
        self.refund_id = refund_id
        self.date = date


class OrderNotFoundError(Exception):
    """Domain rule: refund target order does not exist (business).

    A read can return None for a genuine miss, but a refund against a missing
    order is a failed intent -- the backend must not mint a refund for it.
    """


class NotAuthorizedError(Exception):
    """Caller lacks the scope for this action (permission)."""


class OrdersBackend(Protocol):
    def get_order(self, order_id: str) -> dict | None: ...
    def refund(self, order_id: str, amount: float | None) -> dict: ...


class CustomersBackend(Protocol):
    def get_customer(self, customer_id: str) -> dict | None: ...


class StubBackend:
    def __init__(
        self,
        *,
        orders: dict[str, dict] | None = None,
        customers: dict[str, dict] | None = None,
        unreachable: bool = False,
        timeout: bool = False,
        refunded: dict[str, tuple[str, str]] | None = None,
        authorized: bool = True,
    ):
        self._orders = orders or {}
        self._customers = customers or {}
        self._unreachable = unreachable
        self._timeout = timeout
        self._refunded = refunded or {}
        self._authorized = authorized

    def get_order(self, order_id: str) -> dict | None:
        if self._timeout:
            raise BackendTimeoutError
        if self._unreachable:
            raise BackendUnreachableError
        return self._orders.get(order_id)  # None == genuine miss, not a failure

    def get_customer(self, customer_id: str) -> dict | None:
        if self._timeout:
            raise BackendTimeoutError
        if self._unreachable:
            raise BackendUnreachableError
        return self._customers.get(customer_id)  # None == genuine miss, not a failure

    def refund(self, order_id: str, amount: float | None) -> dict:
        if self._timeout:
            raise BackendTimeoutError
        if self._unreachable:
            raise BackendUnreachableError
        if not self._authorized:  # permission is checked before existence
            raise NotAuthorizedError
        if order_id not in self._orders:
            raise OrderNotFoundError(order_id)
        if order_id in self._refunded:
            refund_id, date = self._refunded[order_id]
            raise AlreadyRefundedError(refund_id, date)
        return {
            "refund_id": "rf_new001",
            "order_id": order_id,
            "amount_refunded": amount,
            "status": "refunded",
        }
