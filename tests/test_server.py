"""The MCP server's pure core (`dispatch`), tested offline without the `mcp` SDK.

The SDK glue (`build_server`/`main`) is the optional live path -- like live.py's
model router, it is not covered by the no-key suite. `dispatch` is the part that
maps a tool name to its handler and returns the categorized result, so every tool
on the surface is verified to be wired.
"""

from support_agent.server import demo_backend, dispatch
from support_agent.tools import SUPPORT_TOOLS


def test_dispatch_lookup_order():
    r = dispatch("lookup_order", {"order_id": "12345"}, demo_backend())
    assert r["isError"] is False
    assert r["_meta"]["code"] == "ORDER_FOUND"


def test_dispatch_get_customer():
    r = dispatch("get_customer", {"customer_id": "cust-1"}, demo_backend())
    assert r["isError"] is False
    assert r["_meta"]["code"] == "CUSTOMER_FOUND"


def test_dispatch_issue_refund():
    r = dispatch("issue_refund", {"order_id": "12345"}, demo_backend())
    assert r["isError"] is False
    assert r["_meta"]["code"] == "REFUND_ISSUED"


def test_dispatch_unknown_tool_is_a_categorized_error():
    r = dispatch("nope", {}, demo_backend())
    assert r["isError"] is True
    assert r["_meta"]["code"] == "UNKNOWN_TOOL"


def test_every_tool_on_the_surface_is_dispatchable():
    backend = demo_backend()
    args = {"order_id": "12345", "customer_id": "cust-1"}
    for tool in SUPPORT_TOOLS:
        result = dispatch(tool.name, args, backend)
        assert result["_meta"]["code"] != "UNKNOWN_TOOL", f"{tool.name} not wired"
