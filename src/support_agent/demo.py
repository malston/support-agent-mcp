"""Runnable offline demo: `python -m support_agent.demo` (no API key).

Four sections, each demonstrating one deliverable against the real code:

  - routing:    the headline request, with mutual boundaries vs. naive getters
  - errors:     the four categories, with their isError / retryable / code
  - access:     valid-empty vs. access-failure (the distinguishing isError)
  - cap basis:  the cross-domain resolve_cap_basis look-alike pair
"""

from support_agent.backend import StubBackend
from support_agent.cap_basis import StubFeeService, resolve_cap_basis
from support_agent.handlers import issue_refund, lookup_order
from support_agent.router import route
from support_agent.tools import NAIVE_TOOLS, SUPPORT_TOOLS

ORDER = {
    "order_id": "12345", "status": "shipped", "line_items": [{"sku": "A1", "qty": 1}],
    "totals": {"grand_total": 42.0}, "shipment": {"carrier": "UPS", "tracking": "1Z999"},
    "customer_id": "cust-1",
}


def _orders() -> StubBackend:
    return StubBackend(orders={"12345": ORDER})


def _meta(result: dict) -> str:
    m = result["_meta"]
    return (
        f"isError={str(result['isError']):5}  category={str(m['error_category']):11}"
        f"  retryable={str(m['retryable']):5}  code={m['code']}"
    )


def routing_demo() -> None:
    print("=== routing: \"check order #12345 status\" ===")
    real = route("check order #12345 status", SUPPORT_TOOLS)
    naive = route("check order #12345 status", NAIVE_TOOLS)
    print(f"  with mutual boundaries -> {real.tool}")
    naive_outcome = naive.tool if naive.tool else f"AMBIGUOUS ({naive.reason})"
    print(f"  with naive getters     -> {naive_outcome}")


def errors_demo() -> None:
    print("=== four error categories ===")
    refunded = StubBackend(orders={"12345": ORDER}, refunded={"12345": ("rf_88c2", "2026-05-02")})
    cases = [
        ("transient", lookup_order({"order_id": "12345"}, StubBackend(timeout=True))),
        ("validation", lookup_order({"order_id": ""}, _orders())),
        ("business", issue_refund({"order_id": "12345"}, refunded)),
        ("permission", issue_refund({"order_id": "12345"}, StubBackend(authorized=False))),
    ]
    for label, result in cases:
        print(f"  {label:11} {_meta(result)}")


def access_vs_empty_demo() -> None:
    print("=== access failure vs. valid empty (same request, opposite meaning) ===")
    absent = lookup_order({"order_id": "99999"}, _orders())
    unreachable = lookup_order({"order_id": "99999"}, StubBackend(unreachable=True))
    print(f"  order absent    {_meta(absent)}")
    print(f"  db unreachable  {_meta(unreachable)}")


def _basis(result: dict) -> object:
    return result["_meta"].get("resolved_basis", "NONE")


def cap_basis_demo() -> None:
    print("=== cross-domain resolve_cap_basis ===")
    empty = resolve_cap_basis({"account_id": "newco"}, StubFeeService(fees={}))
    down = resolve_cap_basis({"account_id": "acme-corp"}, StubFeeService(unreachable=True))
    print(f"  no fees (valid) {_meta(empty)}  resolved_basis={_basis(empty)}")
    print(f"  fee svc down    {_meta(down)}  resolved_basis={_basis(down)}")


def main() -> None:
    for section in (routing_demo, errors_demo, access_vs_empty_demo, cap_basis_demo):
        section()
        print()


if __name__ == "__main__":
    main()
