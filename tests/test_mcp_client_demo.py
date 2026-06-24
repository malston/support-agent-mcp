"""The MCP client reaches the same tool contract over the protocol (no model).

Unlike the rest of the suite, this needs the `mcp` SDK (the live extras), so it
skips cleanly when they are not installed -- `make test` stays green without them.
It exercises the real server over the real protocol; there are no mocks.
"""

import asyncio

import pytest

pytest.importorskip("mcp")  # the protocol client needs the live extras; skip if absent

from support_agent.mcp_client_demo import run  # noqa: E402


def _out() -> dict:
    return asyncio.run(run())


def test_lists_the_three_tools_over_the_protocol():
    names = [name for name, _ in _out()["tools"]]
    assert names == ["lookup_order", "get_customer", "issue_refund"]


def test_descriptions_carry_the_boundaries_across_the_protocol():
    # The same render_description() the offline router scored crosses the wire:
    # the description IS the contract every client sees.
    descriptions = dict(_out()["tools"])
    assert "WHEN NOT TO USE" in descriptions["lookup_order"]


def test_call_tool_returns_the_categorized_result():
    call = _out()["call"]
    assert call["isError"] is False
    assert call["meta"]["code"] == "ORDER_FOUND"
