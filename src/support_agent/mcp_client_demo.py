"""MCP client over the protocol, offline: `python -m support_agent.mcp_client_demo`.

A plain MCP client -- no model, no API key. It launches `support_agent.server`
and talks to it over the standard MCP protocol: `list_tools` (the contract every
client sees) and one `call_tool`. This is the standard-interface point shown, not
asserted: implement a client once and it reaches any server that speaks the
protocol -- N apps x M tools collapses to N + M, no per-tool integration.

It is model-independent on purpose. The MCP transport exposes and invokes tools;
a *model* is only needed to *decide* which tool to call -- that is the live
routing path (`live_demo.py`). So this proves the standard interface with zero
credits. The live, model-driven client of the same server is Claude Code (see the
runbook). The `mcp` SDK is imported lazily, mirroring `server.py`, so this module
stays importable without the live extras.

Needs the live extras for the `mcp` SDK, but no key:

    make install-live
    make mcp-demo
"""

import asyncio
import sys


async def run() -> dict:
    """Connect to the server over MCP; return the tool contract + one call result."""
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    params = StdioServerParameters(command=sys.executable, args=["-m", "support_agent.server"])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            listed = await session.list_tools()
            result = await session.call_tool("lookup_order", {"order_id": "12345"})
            return {
                "tools": [(tool.name, tool.description) for tool in listed.tools],
                "call": {
                    "isError": result.isError,
                    "text": [block.text for block in result.content],
                    "meta": dict(result.meta or {}),
                },
            }


def main() -> None:
    out = asyncio.run(run())
    print("=== MCP client over the protocol (offline -- no model, no key) ===")
    print("list_tools -- the contract every client sees:")
    for name, description in out["tools"]:
        print(f"  {name}: {description.splitlines()[0]}")
    call = out["call"]
    print("\ncall_tool('lookup_order', {'order_id': '12345'}):")
    print(f"  isError={call['isError']}  code={call['meta'].get('code')}")
    print(f"  {call['text'][0]}")


if __name__ == "__main__":
    main()
