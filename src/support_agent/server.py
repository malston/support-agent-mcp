"""The MCP server entrypoint declared in .mcp.json (`python -m support_agent.server`).

This is the real-SDK path, in the optional `live` Poetry group (install with
`--with live`), exactly like `live.py`'s model path. The `mcp` SDK is imported
lazily so the offline test suite -- which exercises `dispatch` directly -- needs
neither the SDK nor an API key.

Two layers, mirroring the rest of the example:
  - `dispatch` is the pure, offline-testable core: it maps a tool name to its
    handler over a backend and returns the categorized MCP result dict.
  - `build_server` / `main` are the thin SDK glue: a low-level `Server` whose
    `list_tools` returns the real `render_description()` text (the selection
    mechanism reaching an actual MCP surface) and whose `call_tool` wraps a
    `dispatch` result in a `CallToolResult`, preserving `isError` and `_meta`.

This demo server serves in-memory sample data via `StubBackend`. A real deployment
would build the backend from the ${VAR} values in .mcp.json (ORDERS_DB_URL /
ORDERS_API_KEY); the seam is `demo_backend()`.
"""

from support_agent import errors, handlers
from support_agent.backend import StubBackend
from support_agent.tools import SUPPORT_TOOLS, TOOL_INPUT_SCHEMA

DEMO_ORDERS = {
    "12345": {
        "order_id": "12345", "status": "shipped", "line_items": [{"sku": "A1", "qty": 1}],
        "totals": {"grand_total": 42.0}, "shipment": {"carrier": "UPS", "tracking": "1Z999"},
        "customer_id": "cust-1",
    },
}

DEMO_CUSTOMERS = {
    "cust-1": {
        "customer_id": "cust-1", "email": "casey@example.com", "phone": "+1-555-0100",
        "addresses": [], "loyalty_tier": "gold", "lifetime_value": 1280.0,
        "order_ids": ["12345"],
    },
}


def demo_backend() -> StubBackend:
    """The seam: a real deployment swaps this for a backend built from env."""
    return StubBackend(orders=DEMO_ORDERS, customers=DEMO_CUSTOMERS)


def dispatch(name: str, arguments: dict, backend: StubBackend) -> dict:
    """Pure core: route a tool call to its handler. Returns an MCP result dict."""
    if name == "lookup_order":
        return handlers.lookup_order(arguments, backend)
    if name == "get_customer":
        return handlers.get_customer(arguments, backend)
    if name == "issue_refund":
        return handlers.issue_refund(arguments, backend)
    return errors.mcp_error(
        f"Unknown tool {name!r}. Call one of: "
        f"{', '.join(t.name for t in SUPPORT_TOOLS)}.",
        category="validation", retryable=False, code="UNKNOWN_TOOL",
    )


def build_server():
    """Construct the low-level MCP Server. Lazy-imports the `mcp` SDK."""
    import mcp.types as types
    from mcp.server.lowlevel import Server

    server = Server("support-agent")
    backend = demo_backend()

    @server.list_tools()
    async def list_tools() -> list:
        return [
            types.Tool(
                name=tool.name,
                description=tool.render_description(),
                inputSchema=TOOL_INPUT_SCHEMA,
            )
            for tool in SUPPORT_TOOLS
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict):
        result = dispatch(name, arguments or {}, backend)
        return types.CallToolResult(
            content=[types.TextContent(type="text", text=b["text"]) for b in result["content"]],
            isError=result["isError"],
            _meta=result["_meta"],
        )

    return server


def main() -> None:
    """Run the server over stdio. Requires the `live` group (`--with live`)."""
    import asyncio

    import mcp.server.stdio
    from mcp.server.lowlevel import NotificationOptions
    from mcp.server.models import InitializationOptions

    server = build_server()

    async def _run() -> None:
        async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="support-agent",
                    server_version="0.1.0",
                    capabilities=server.get_capabilities(
                        notification_options=NotificationOptions(),
                        experimental_capabilities={},
                    ),
                ),
            )

    asyncio.run(_run())


if __name__ == "__main__":
    main()
