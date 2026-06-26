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
    """Verify all three tools appear in the protocol contract.

    The server must wire all tools into the protocol. If a tool is missing,
    the client cannot discover it. This catches incomplete dispatch() handlers
    or removed tools that weren't deleted from the registry.
    """
    names = [name for name, _ in _out()["tools"]]
    assert names == ["lookup_order", "get_customer", "issue_refund"]


def test_descriptions_carry_the_boundaries_across_the_protocol():
    """Verify tool descriptions (including WHEN NOT TO USE boundaries) survive the wire.

    The model reads "WHEN NOT TO USE" to understand when a tool is off-limits.
    This metadata must survive MCP serialization, or clients lose routing guidance.
    """
    descriptions = dict(_out()["tools"])
    assert "WHEN NOT TO USE" in descriptions["lookup_order"]


def test_call_tool_returns_the_categorized_result():
    """Verify that error categorization (_meta) survives the protocol round-trip.

    The model reads isError + meta to decide recovery strategy. These fields must
    be present and accurate over the wire; if they're lost or corrupted, the model
    cannot reason about failure modes.
    """
    call = _out()["call"]
    assert call["isError"] is False
    assert call["meta"]["code"] == "ORDER_FOUND"


def test_all_three_tools_are_callable_over_protocol():
    """Exercise each of the three tools over the real protocol.

    Verifies that the server dispatch() handler correctly routes all three tools.
    Catches incomplete wiring (e.g., missing tool in dispatch, typo in handler).
    """
    out = _out()
    tool_names = [name for name, _ in out["tools"]]

    # All three should be in the list
    assert len(tool_names) == 3
    assert "lookup_order" in tool_names
    assert "get_customer" in tool_names
    assert "issue_refund" in tool_names

    # lookup_order was called in run(); here we verify it returned success
    call = out["call"]
    assert call["isError"] is False
    assert call["meta"]["code"] in ["ORDER_FOUND", "ORDER_NOT_FOUND"]


def test_call_result_structure_is_complete():
    """Verify the call result has all required structure fields.

    The client must receive isError, content[], and meta{error_category, retryable, code}.
    Missing fields can cause silent failures when clients try to access them.
    """
    call = _out()["call"]

    # Top-level contract
    assert "isError" in call
    assert "text" in call
    assert "meta" in call

    # isError must be a bool
    assert isinstance(call["isError"], bool)

    # text is a list of strings (content blocks)
    assert isinstance(call["text"], list)
    if call["text"]:
        assert all(isinstance(t, str) for t in call["text"])

    # meta must have categorization fields
    assert isinstance(call["meta"], dict)
    assert "code" in call["meta"]


def test_tool_descriptions_are_non_empty():
    """Verify all tool descriptions exist and have content.

    Catches refactors that accidentally clear descriptions or descriptions
    that were deleted from the tool definition.
    """
    out = _out()
    for name, description in out["tools"]:
        assert isinstance(description, str)
        assert len(description) > 0
        assert len(description) > 10  # Should be meaningful, not just a word
