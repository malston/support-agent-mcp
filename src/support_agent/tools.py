"""The three support-agent tool definitions -- the primary routing mechanism.

A `Tool` carries the four description components as prose (what / when / when-not /
returns+params) AND the structured trigger phrases the offline router scores on.
The prose and the triggers are the same content in two forms: `render_description`
is what the live model reads; `when_triggers` / `when_not_triggers` are what the
deterministic `router.route` scores. Keeping them on one object keeps them honest
-- the boundary the model reads is the boundary the router enforces.

The ambiguous pair is `lookup_order` / `get_customer`. Their `when_not` lines name
each other (`boundary_targets`), so neither reads as the generic catch-all.
"""

from pydantic import BaseModel, Field


class Tool(BaseModel):
    """An MCP tool definition. The description is prompt engineering for routing."""

    name: str
    what: str
    when: str
    when_not: str
    returns: str
    params: str
    # Router signals (lowercased substrings matched against the request):
    when_triggers: list[str] = Field(default_factory=list)
    when_not_triggers: list[str] = Field(default_factory=list)
    # The sibling tool(s) this tool's WHEN-NOT line redirects colliding requests to:
    boundary_targets: list[str] = Field(default_factory=list)

    def render_description(self) -> str:
        """The four-component prose the model sees at selection time."""
        return (
            f"{self.what}\n\n"
            f"WHEN TO USE: {self.when}\n\n"
            f"WHEN NOT TO USE: {self.when_not}\n\n"
            f"RETURNS: {self.returns}\n"
            f"KEY PARAMS: {self.params}"
        )


LOOKUP_ORDER = Tool(
    name="lookup_order",
    what=(
        "Retrieves the status, line items, shipment tracking, and totals for a "
        "SINGLE order, identified by its order ID (e.g. \"12345\" / order #12345)."
    ),
    when=(
        "the request references an order -- an order number or \"#\", \"my order\", "
        "order status, \"where is my package\", tracking, what was in an order, or "
        "an order total. If the user names or implies a specific order, this is the tool."
    ),
    when_not=(
        "do NOT use to look up the PERSON who placed the order -- their email, phone, "
        "shipping address, loyalty tier, or account history. That is `get_customer`. "
        "This tool is keyed by order_id; it does not accept a customer id or a name. "
        "If you have only a customer's name or email and no order id, call "
        "`get_customer` first to get their order_ids, then call this."
    ),
    returns=(
        "{ order_id, status, line_items[], totals, shipment{carrier,tracking}, "
        "customer_id }. Note it returns customer_id -- the handle you pass to "
        "`get_customer` if the user then asks about the person."
    ),
    params="order_id (required, string, the numeric order number).",
    when_triggers=[
        "order #", "order#", "#", "order status", "status of order", "my order",
        "order number", "where is my", "where's my", "tracking", "shipment",
        "what was in", "order total",
    ],
    when_not_triggers=[
        "email", "phone number", "their address", "loyalty", "lifetime value",
        "the customer's", "this customer's", "contact info", "account history",
    ],
    boundary_targets=["get_customer"],
)

GET_CUSTOMER = Tool(
    name="get_customer",
    what=(
        "Retrieves a CUSTOMER's profile -- contact details (email, phone, "
        "addresses), loyalty tier, lifetime value, and the LIST of order ids they "
        "have placed -- identified by customer ID."
    ),
    when=(
        "the request is about the person or the account -- their email or contact "
        "info, address on file, loyalty status, lifetime value, or \"what orders "
        "does this customer have\" when you need to DISCOVER their order ids."
    ),
    when_not=(
        "do NOT use to get the status, contents, tracking, or total of a specific "
        "order, EVEN IF the user gives an order number. A request that names an "
        "order (#12345, \"my order's status\", \"where's my package\", tracking) "
        "goes to `lookup_order`. This tool is keyed by customer_id; it does not "
        "accept an order_id and returns nothing about a single order's status."
    ),
    returns=(
        "{ customer_id, email, phone, addresses[], loyalty_tier, lifetime_value, "
        "order_ids[] }."
    ),
    params="customer_id (required, string).",
    when_triggers=[
        "email", "phone number", "their address", "address on file", "loyalty",
        "lifetime value", "contact info", "the customer's", "this customer's",
        "account history", "who is the customer", "what orders does",
    ],
    when_not_triggers=[
        "order #", "order#", "#", "order status", "status of order", "my order",
        "where is my", "where's my", "tracking", "order total",
    ],
    boundary_targets=["lookup_order"],
)

ISSUE_REFUND = Tool(
    name="issue_refund",
    what=(
        "Issues a monetary refund against a specific, already-placed order. This is "
        "a STATE-CHANGING financial action: it moves money and cannot be undone from "
        "inside this tool."
    ),
    when=(
        "ONLY when the user has explicitly asked for a refund AND you have a concrete "
        "order_id plus either an amount or an intent to refund the full order. The "
        "order must already exist (confirm with `lookup_order` if unsure)."
    ),
    when_not=(
        "do NOT use to CHECK whether an order is eligible for a refund or to read "
        "its details (status, totals, line items) -- that is a read; use "
        "`lookup_order`. Do NOT use to look up payment or contact details -- use "
        "`get_customer`. Never call this \"to see what would happen\" or to preview: "
        "there is no dry-run; calling it executes the refund."
    ),
    returns=(
        "on success { refund_id, order_id, amount_refunded, status:\"refunded\" }; "
        "on failure a categorized error (already refunded -> business, retryable "
        "false; caller lacks refund scope -> permission)."
    ),
    params=(
        "order_id (required), amount (optional; omit = full-order refund), "
        "reason (optional, free text)."
    ),
    when_triggers=["refund", "give back the money", "reverse the charge", "money back"],
    when_not_triggers=["is it refundable", "refund status", "can i refund", "would happen"],
    boundary_targets=["lookup_order"],
)

SUPPORT_TOOLS: list[Tool] = [LOOKUP_ORDER, GET_CUSTOMER, ISSUE_REFUND]


# The distractor surface: naive "Retrieves [entity] information" getters with NO
# mutual boundaries. A customer getter that also reads as covering the customer's
# orders is exactly the collision the real descriptions defeat. Used by the demo
# and the routing test to show the boundaries are load-bearing.
NAIVE_LOOKUP_ORDER = Tool(
    name="lookup_order",
    what="Retrieves order information.",
    when="use to get information about an order.",
    when_not="(no boundary)",
    returns="order information.",
    params="order_id.",
    when_triggers=["order"],
)

NAIVE_GET_CUSTOMER = Tool(
    name="get_customer",
    what="Retrieves customer information.",
    when="use to get information about a customer and their orders.",
    when_not="(no boundary)",
    returns="customer information.",
    params="customer_id.",
    when_triggers=["order", "customer"],
)

NAIVE_TOOLS: list[Tool] = [NAIVE_LOOKUP_ORDER, NAIVE_GET_CUSTOMER]

_BY_NAME = {t.name: t for t in SUPPORT_TOOLS}


def get_tool(name: str) -> Tool:
    return _BY_NAME[name]


# The shared input schema for the surface -- the union of params across the three
# tools. One canonical definition consumed by both the MCP server (server.py) and
# the live model router (live.py).
TOOL_INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "order_id": {"type": "string"},
        "customer_id": {"type": "string"},
        "amount": {"type": "number"},
        "reason": {"type": "string"},
    },
}
