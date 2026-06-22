"""Deliverable 1 + 2: the description is the selection mechanism, and the
ambiguous pair's boundaries point at each other by name.

These tests are over the *artifact* (the rendered description string and its
structured boundary metadata), because that string is exactly what the model
reads at selection time.
"""

from support_agent.tools import SUPPORT_TOOLS, get_tool

FOUR_COMPONENTS = ["WHEN TO USE", "WHEN NOT TO USE", "RETURNS", "KEY PARAMS"]


def test_support_surface_is_three_tools():
    # ~4-5 tools per agent is the budget; this surface is a lean three.
    assert {t.name for t in SUPPORT_TOOLS} == {"lookup_order", "get_customer", "issue_refund"}


def test_every_description_carries_all_four_components():
    for tool in SUPPORT_TOOLS:
        rendered = tool.render_description()
        assert tool.what.strip(), f"{tool.name} missing 'what'"
        for marker in FOUR_COMPONENTS:
            assert marker in rendered, f"{tool.name} description missing {marker!r}"


def test_ambiguous_pair_boundaries_point_at_each_other():
    order = get_tool("lookup_order")
    customer = get_tool("get_customer")
    # structured: each names the other as the place to redirect colliding requests
    assert order.boundary_targets == ["get_customer"]
    assert customer.boundary_targets == ["lookup_order"]
    # prose: the sibling is actually named in the WHEN NOT line the model reads
    assert "get_customer" in order.when_not
    assert "lookup_order" in customer.when_not


def test_boundary_is_mutual_not_one_sided():
    # A one-sided boundary leaks: the unbounded tool still reads as a catch-all.
    # Assert neither side has an empty boundary.
    for name in ("lookup_order", "get_customer"):
        tool = get_tool(name)
        assert tool.boundary_targets, f"{name} has no boundary -- it reads as a catch-all"
        assert tool.when_not_triggers, f"{name} has no when-not triggers to disqualify it"


def test_mutation_is_not_overloaded_and_warns_against_dry_run():
    refund = get_tool("issue_refund")
    # single clean trigger -- it refunds; it does not also "refund OR credit OR replace"
    assert refund.boundary_targets == ["lookup_order"]  # "to CHECK refundability, use lookup_order"
    rendered = refund.render_description().lower()
    assert "no dry-run" in rendered or "no dry run" in rendered or "executes" in rendered
