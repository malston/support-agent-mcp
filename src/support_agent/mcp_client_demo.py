"""MCP client over the protocol, offline: `python -m support_agent.mcp_client_demo`.

A plain MCP client -- no model, no API key. It launches `support_agent.server`
and talks to it over the standard MCP protocol: `list_tools` (the contract every
client sees) and one `call_tool`. This is the standard-interface point shown, not
asserted: implement a client once and it reaches any server that speaks the
protocol -- N apps x M tools collapses to N + M, no per-tool integration.

It is model-independent on purpose. The MCP transport exposes and invokes tools;
a *model* is only needed to *decide* which tool to call -- that is the live
routing path (`live_demo.py`). So this proves the standard interface with zero
credits. It exercises tool listing and invocation across the protocol boundary,
demonstrating that the MCP contract is consistent regardless of which client
implements it. The live, model-driven client of the same server is Claude Code
(see the runbook). The `mcp` SDK is imported lazily, mirroring `server.py`, so
this module stays importable without the live extras.

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
    try:
        async with stdio_client(params) as (read, write):
            try:
                async with ClientSession(read, write) as session:
                    try:
                        await session.initialize()
                    except Exception as e:
                        raise RuntimeError(f"Failed to initialize MCP session: {e}") from e

                    try:
                        listed = await session.list_tools()
                    except Exception as e:
                        raise RuntimeError(f"Failed to list tools: {e}") from e

                    try:
                        result = await session.call_tool("lookup_order", {"order_id": "12345"})
                    except Exception as e:
                        raise RuntimeError(f"Failed to call tool: {e}") from e

                    return {
                        "tools": [(tool.name, tool.description) for tool in listed.tools],
                        "call": {
                            "isError": result.isError,
                            "text": [block.text for block in result.content],
                            "meta": dict(result.meta or {}),
                        },
                    }
            except Exception as e:
                raise RuntimeError(f"MCP session error: {e}") from e
    except FileNotFoundError as e:
        raise RuntimeError(
            f"Failed to start server: Python module not found. "
            f"Ensure support_agent.server is installed. ({e})"
        ) from e
    except Exception as e:
        raise RuntimeError(f"Failed to connect to MCP server: {e}") from e


def main() -> None:
    try:
        out = asyncio.run(run())
    except RuntimeError as e:
        print(f"Error: {e}")
        return
    except Exception as e:
        print(f"Unexpected error: {type(e).__name__}: {e}")
        return

    try:
        print("=== MCP client over the protocol (offline -- no model, no key) ===")
        print("list_tools -- the contract every client sees:")
        if not isinstance(out.get("tools"), list):
            print("Error: Invalid response structure (tools)")
            return
        for name, description in out["tools"]:
            lines = description.splitlines()
            if not lines:
                print(f"  {name}: (no description)")
            else:
                print(f"  {name}: {lines[0]}")

        call = out.get("call")
        if not isinstance(call, dict):
            print("Error: Invalid response structure (call)")
            return
        print("\ncall_tool('lookup_order', {'order_id': '12345'}):")
        print(f"  isError={call.get('isError')}  code={call.get('meta', {}).get('code')}")
        text_blocks = call.get("text", [])
        if text_blocks:
            print(f"  {text_blocks[0]}")
        else:
            print("  (no text content)")
    except Exception as e:
        print(f"Error processing results: {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
