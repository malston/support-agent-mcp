"""The headline routing test (deliverable 2 / 5).

"check order #12345 status" MUST route to lookup_order, never to get_customer.

`route` is a deterministic stand-in for the model's tool selection (the live
analog, ModelRouter in live.py, uses tool_choice="auto" against the real model).
The point under test is NOT the router -- it is the *descriptions*: the same
request, scored by the same router, routes correctly with the real boundaried
descriptions and goes AMBIGUOUS with naive "retrieves X information" ones. That
delta is the proof the boundaries are load-bearing.
"""

from support_agent.router import route
from support_agent.tools import NAIVE_TOOLS, SUPPORT_TOOLS


def test_headline_check_order_status_routes_to_order_tool():
    result = route("check order #12345 status", SUPPORT_TOOLS)
    assert result.tool == "lookup_order"
    assert result.ambiguous is False


def test_customer_email_routes_to_customer_tool():
    result = route("what's this customer's email", SUPPORT_TOOLS)
    assert result.tool == "get_customer"


def test_refund_request_routes_to_mutation():
    result = route("I want a refund on order 12345", SUPPORT_TOOLS)
    assert result.tool == "issue_refund"


def test_naive_descriptions_misroute_the_headline_request():
    # The distractor: without mutual boundaries, "check order #12345 status"
    # collides -- a customer getter that also claims orders is just as plausible.
    result = route("check order #12345 status", NAIVE_TOOLS)
    assert result.tool != "lookup_order"
    assert result.ambiguous is True


def test_boundary_disqualifies_the_sibling_not_just_outscores_it():
    # get_customer must be DISQUALIFIED by its when-not boundary, so even if the
    # request leaned customer-ish, an order request can never land on it.
    result = route("check order #12345 status", SUPPORT_TOOLS)
    assert result.tool == "lookup_order"
    assert "get_customer" in result.disqualified
