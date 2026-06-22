# Domain 2 Build Exercise -- Support-Agent MCP Tool & Error Design

## Prompt

See [build prompt](../.prompts/domain2-build-exercise.prompt.md).

## Response

These are MCP tool definitions and MCP result objects -- the descriptions are the
`description` field of a `tools` entry, and the error objects are the shape a tool
handler returns (`content` + `isError`, with category metadata in `_meta`). The
agent never sees your handler code; it sees the description (at selection time) and
the result object (at recovery time). Both are prompt engineering aimed at a
decision the model makes.

One thing up front, because you asked me to push back where your instructions force
a principle violation: **they don't.** The spec is tight. The single place I
_sharpen_ rather than reject is the word **`retryable`** on the validation error.
You wrote "retryable true (after fixing args)," which is the right behavior, but the
parenthetical is load-bearing and I'm going to make it explicit in the field's
contract: `retryable` means **"can recovery-by-retry succeed?"**, not "retry the
identical call." For validation that is `true` _only because the agent first changes
the arguments_ -- a verbatim retry of a malformed call fails identically. A
coordinator that reads `retryable: true` and replays the same bytes would loop
forever. I'm keeping your value (`true`) and pinning the semantics so the field
stays deterministic across propagation. Flagging it so it doesn't read as me
redefining your schema.

Here are the deliverables.

---

## 1. The three tool definitions

The surface is **two crisp read-only lookups plus one high-stakes mutation** --
three tools, comfortably inside the ~4-5-per-agent budget where routing stays sharp
(degradation sets in nearer ~18). That budget headroom is deliberate: the two reads
are cheap, low-stakes, and shareable across other agents; the mutation is the
expensive one and stays tightly scoped to a single owner.

Each description carries all four components: **what it does / when to use it / when
NOT to use it / what it returns + key params.** The "when NOT" lines on the
ambiguous pair point at each other _by name_ -- that mutual boundary is what stops
either tool from reading as the generic catch-all (deliverable 2 proves it).

### Tool A -- `lookup_order` (the order tool, read-only)

```text
name: lookup_order
description: |
  Retrieves the status, line items, shipment tracking, and totals for a SINGLE
  order, identified by its order ID (e.g. "12345" / order #12345).

  WHEN TO USE: the request references an order -- an order number or "#", "my
  order", order status, "where is my package", tracking, what was in an order, or
  an order total. If the user names or implies a specific order, this is the tool.

  WHEN NOT TO USE: do NOT use to look up the PERSON who placed the order -- their
  email, phone, shipping address, loyalty tier, or account history. That is
  `get_customer`. This tool is keyed by `order_id`; it does not accept a customer
  id or a name. If you have only a customer's name or email and no order id, call
  `get_customer` first to get their order_ids, then call this.

  RETURNS: { order_id, status, line_items[], totals, shipment{carrier,tracking},
  customer_id }. Note it returns `customer_id` -- that is the handle you pass to
  `get_customer` if the user then asks about the person.
  KEY PARAMS: order_id (required, string, the numeric order number).
```

### Tool B -- `get_customer` (the customer tool, read-only)

```text
name: get_customer
description: |
  Retrieves a CUSTOMER's profile -- contact details (email, phone, addresses),
  loyalty tier, lifetime value, and the LIST of order ids they have placed --
  identified by customer ID.

  WHEN TO USE: the request is about the person or the account -- their email or
  contact info, address on file, loyalty status, lifetime value, or "what orders
  does this customer have" when you need to DISCOVER their order ids.

  WHEN NOT TO USE: do NOT use to get the status, contents, tracking, or total of a
  specific order, EVEN IF the user gives an order number. A request that names an
  order (#12345, "my order's status", "where's my package", tracking) goes to
  `lookup_order`. This tool is keyed by `customer_id`; it does not accept an
  order_id and returns nothing about a single order's status.

  RETURNS: { customer_id, email, phone, addresses[], loyalty_tier,
  lifetime_value, order_ids[] }.
  KEY PARAMS: customer_id (required, string).
```

### Tool C -- `issue_refund` (the mutation, state-changing)

```text
name: issue_refund
description: |
  Issues a monetary refund against a specific, already-placed order. This is a
  STATE-CHANGING financial action: it moves money and cannot be undone from
  inside this tool.

  WHEN TO USE: ONLY when the user has explicitly asked for a refund AND you have a
  concrete `order_id` plus either an `amount` or an intent to refund the full
  order. The order must already exist (confirm with `lookup_order` if unsure).

  WHEN NOT TO USE: do NOT use to CHECK whether an order is refundable or to read
  its current refund status -- that is a read; use `lookup_order`. Do NOT use to
  look up payment or contact details -- use `get_customer`. Never call this "to
  see what would happen" or to preview: there is no dry-run; calling it executes
  the refund.

  RETURNS on success: { refund_id, order_id, amount_refunded, status:"refunded" }.
  RETURNS on failure: a categorized error object (e.g. already refunded ->
  business, retryable false; caller lacks refund scope -> permission).
  KEY PARAMS: order_id (required), amount (optional; omit = full-order refund),
  reason (optional, free text).
```

Note the mutation is **not overloaded.** It does one thing (refund an order); it
does not also "issue store credit or refund or replacement depending on a param."
That would be the _split_ case from the principles -- one tool with three triggers
the model has to disambiguate from a param value. Keeping `issue_refund` a single
clean trigger is the correct direction here; the ambiguous pair is a _sharpen_ case
(deliverable 2), and the mutation is a _don't-overload_ case. Different problems,
different fixes.

---

## 2. Mutual disambiguation -- and the proof

The naive descriptions ("Retrieves order information" / "Retrieves customer
information") collide because **both read as generic getters**, and "check order
#12345 status" plausibly matches either -- an order _belongs to_ a customer, so a
customer getter looks like a reasonable place to find it. The fix is not a better
name (the name is not the selection mechanism); it is a **mutual boundary**: each
tool's "WHEN NOT TO USE" names the other tool and hands the colliding request to it.

Why **both** sides need the boundary, not one: if only `lookup_order` said "not for
customer info," `get_customer` would still read as an open-ended "retrieves customer
information" getter -- and since the order's owner is a customer, the model can still
grab `get_customer` for "check order #12345 status." A one-sided boundary plugs one
tool and leaves the other a catch-all. Both boundaries together mean **neither tool
is the default**; each request has exactly one home.

**Proof -- "check order #12345 status" routes to `lookup_order`:**
The request names an order and asks for status. `lookup_order`'s WHEN TO USE matches
head-on ("order status", "an order number or #"). `get_customer`'s WHEN NOT TO USE
fires explicitly: "do NOT use to get the status of a specific order, EVEN IF the
user gives an order number ... a request that names an order (#12345 ...) goes to
`lookup_order`." Both signals point the same way. Order tool wins.

**Proof -- "what's this customer's email" routes to `get_customer`:**
`get_customer`'s WHEN TO USE matches ("their email or contact info").
`lookup_order`'s WHEN NOT TO USE fires: "do NOT use to look up the PERSON ... their
email ... that is `get_customer`." Again both signals agree. Customer tool wins.

### `tool_choice` is not how any of this works

The routing above is done entirely by **descriptions**, with `tool_choice: "auto"`
-- the model decides whether to call a tool and which one. I am deliberately _not_
reaching for `tool_choice` to fix routing, because forcing a tool fixes exactly one
request and breaks every other one: force `lookup_order` and "what's this customer's
email" now misroutes the other way. The three modes and when each is right:

- **`auto`** (this server's default): model chooses whether to call a tool at all.
  Correct for a support agent that also just talks to the user.
- **`any`**: model must call _some_ tool but picks which. Right when every turn must
  result in a tool call, wrong here (some turns are plain answers).
- **forced** (`{type:"tool", name:"..."}`): the designer names the exact tool. Right
  only for a known, constrained step -- e.g. a sub-step that _must_ produce a refund
  -- never as a substitute for descriptions that route correctly on their own.

---

## 3. The four categorized error responses

Each is a full MCP result object. Three invariants hold across all four:

- **`isError` is always present and is the loop's branch signal.** The handler
  _returns_ the error; it never throws. A thrown exception escapes the tool-use loop
  and the model cannot reason about or recover from it. `isError: true` keeps the
  failure _inside_ the loop as content the model reads and acts on.
- **`_meta.error_category` + `_meta.retryable` are the recovery contract**, and they
  must survive propagation -- a subagent that flattens any of these to "it failed"
  destroys a coordinator's ability to recover deterministically.
- **The prose is written for the model to act on**, not for a log file: it says what
  happened, whether to retry, and what to do instead.

`retryable` semantics (the refinement from the top): **`retryable` answers "can
recovery-by-retry succeed?"** Transient -> yes, retry the same call. Validation ->
yes, _but only after changing the arguments_ (a verbatim retry fails identically).
Business / permission -> no, retrying cannot help; change strategy or escalate.

### 3a. Transient -- temporary, retry helps

```json
{
  "content": [
    {
      "type": "text",
      "text": "The orders service timed out before returning order #12345. This is a temporary problem on our side -- nothing is wrong with your request. Wait a moment, then call lookup_order again with the same arguments."
    }
  ],
  "isError": true,
  "_meta": {
    "error_category": "transient",
    "retryable": true,
    "code": "ORDERS_UPSTREAM_TIMEOUT"
  }
}
```

### 3b. Validation -- malformed input

```json
{
  "content": [
    {
      "type": "text",
      "text": "order_id is required and must be the numeric order number (for example \"12345\"); received an empty value. Re-call lookup_order with a valid order_id. Do NOT retry with the same empty value -- a verbatim retry will fail the same way."
    }
  ],
  "isError": true,
  "_meta": {
    "error_category": "validation",
    "retryable": true,
    "code": "INVALID_ORDER_ID"
  }
}
```

`retryable: true` here means "fixable then retryable," and the prose says so out
loud so the model corrects the argument rather than replaying the bad call.

### 3c. Business -- valid request, a domain rule blocks it

```json
{
  "content": [
    {
      "type": "text",
      "text": "Order #12345 was already fully refunded on 2026-05-02 (refund_id rf_88c2) and cannot be refunded again. This is a final business-rule outcome; retrying will not change it. If the customer disputes the existing refund, hand off to a human billing agent instead of re-attempting the refund."
    }
  ],
  "isError": true,
  "_meta": {
    "error_category": "business",
    "retryable": false,
    "code": "ALREADY_REFUNDED"
  }
}
```

This is the one the rubric watches: **`isError: true`, `retryable: false`.** The
request was well-formed and the caller was authorized -- it still _failed_, because
intent collided with a domain rule. That is a real failure, not a "query returned
nothing." Modeling "already refunded" as a valid empty result (`isError: false`)
would let the agent cheerfully report success on an action that never happened.

### 3d. Permission -- caller not authorized

```json
{
  "content": [
    {
      "type": "text",
      "text": "You are not authorized to issue refunds. issue_refund requires the billing.refund scope, which this caller does not hold. Do NOT retry -- the same credentials will fail identically. Hand off to an agent or human operator that holds refund authority."
    }
  ],
  "isError": true,
  "_meta": {
    "error_category": "permission",
    "retryable": false,
    "code": "REFUND_FORBIDDEN"
  }
}
```

---

## 4. Access-failure vs. valid-empty-result

These two look almost identical to a careless handler -- both are "we have no order
to show you" -- but they mean opposite things, and the distinguishing bit is
**`isError`.**

### 4a. Valid empty result -- the order genuinely does not exist

```json
{
  "content": [
    {
      "type": "text",
      "text": "No order found with ID 99999. The lookup ran successfully; there is simply no such order. Confirm the order number with the customer, or call get_customer to list this customer's order_ids."
    }
  ],
  "isError": false,
  "_meta": {
    "error_category": null,
    "retryable": false,
    "code": "ORDER_NOT_FOUND"
  }
}
```

`isError: false` -- the **query succeeded**; the answer is "zero rows." The agent
can truthfully tell the customer this order does not exist.

### 4b. Access failure -- the orders database is unreachable

```json
{
  "content": [
    {
      "type": "text",
      "text": "Could not reach the orders database to look up order #99999 -- the query did not run, so whether order #99999 exists is UNKNOWN. Do NOT report that order #99999 does not exist. This is a temporary infrastructure failure; wait and retry lookup_order shortly."
    }
  ],
  "isError": true,
  "_meta": {
    "error_category": "transient",
    "retryable": true,
    "code": "ORDERS_DB_UNREACHABLE"
  }
}
```

### The confident-lie failure if you make them identical

If the outage returned the _same_ shape as 4a -- `isError: false`, content "no order
found" -- the model has no way to tell "we looked and it isn't there" from "we
couldn't look." It will do the agreeable, fluent thing: tell the customer **"there's
no order #99999 on your account"** when the truth is the database was down. That is a
confident lie manufactured from an outage -- the most dangerous failure mode,
because it is indistinguishable from a correct answer at the point of delivery. The
`isError` split forces the loop to branch: `false` -> answer the user; `true` +
`transient` -> retry, and never assert non-existence. **Absence of evidence
(empty result) and failure to gather evidence (access failure) must never share a
representation.**

---

## 5. `.mcp.json` -- project scope, `${VAR}` expansion, zero secrets

Declared at **project scope** so it is committed and shared via git; every secret
comes from each developer's own environment through `${VAR}` expansion. The
committed file carries _structure_ (which server, how to launch it, which env keys
it needs) -- never a credential value. A hardcoded key here would be leaked into git
history permanently, readable by anyone who ever clones the repo.

```json
{
  "mcpServers": {
    "support-agent": {
      "command": "python",
      "args": ["-m", "support_agent.server"],
      "env": {
        "ORDERS_API_KEY": "${SUPPORT_ORDERS_API_KEY}",
        "ORDERS_DB_URL": "${SUPPORT_ORDERS_DB_URL}",
        "REFUND_SIGNING_SECRET": "${SUPPORT_REFUND_SIGNING_SECRET}"
      }
    }
  }
}
```

- **`${VAR}` expansion** on all three secret-bearing values (an API key, a database
  URL that embeds credentials, and a refund-signing secret). Claude Code expands
  `${VAR}` from the environment at load time; `${VAR:-default}` is also supported,
  but a _default_ is deliberately not used for any secret -- a default credential is
  just a hardcoded credential with extra steps.
- **Zero secrets in the file.** Grep it for a key value and you find variable names,
  not credentials. The values live in each user's shell / `.env` (which is
  gitignored); a committed `.env.example` documents the three variable names without
  values, mirroring the Domain 1 example.

---

## Cross-domain extension -- `resolve_cap_basis` for the Domain 1 reviewer

The Domain 1 contract reviewer flags numeric liability caps with deterministic
arithmetic (`$5,000,000 > $1M`). Real caps are often **formulas** tied to external
data -- "liability shall not exceed the fees paid in the trailing 12 months," "2x
annual contract value." Resolving the figure a formula references is a Domain 2 tool
problem, and it is **the same access-failure-vs-valid-empty pattern as deliverable
4**, pointed at a fee service instead of an orders database. This is a tool _for the
Domain 1 reviewer to call_, not a fourth tool on the support-agent surface.

`resolve_cap_basis` fetches the figure (trailing fees, contract value). Its two
look-alike responses:

### Fee service unreachable -> access failure

```json
{
  "content": [
    {
      "type": "text",
      "text": "Could not reach the fee service to resolve trailing-12-month fees for account acme-corp -- the lookup did not run, so the cap basis is UNKNOWN. Do NOT treat this as $0. Return this error upstream with its category intact so the contract coordinator can escalate instead of computing a cap from a missing number."
    }
  ],
  "isError": true,
  "_meta": {
    "error_category": "transient",
    "retryable": true,
    "code": "FEE_SERVICE_UNREACHABLE"
  }
}
```

### Account genuinely has no fees -> valid empty result

```json
{
  "content": [
    {
      "type": "text",
      "text": "No fees recorded for this account. The fee service responded successfully; the trailing-12-month fee total is genuinely $0. A fee-based cap therefore resolves to $0 -- this means a near-zero liability ceiling, so confirm it is intended before relying on it."
    }
  ],
  "isError": false,
  "_meta": {
    "error_category": null,
    "retryable": false,
    "code": "NO_FEES_ON_RECORD",
    "resolved_basis": 0
  }
}
```

**The confident lie to avoid:** collapsing "unreachable" into "fees = $0." That makes
an _unbounded_ formula cap read as **zero exposure** -- the safest-looking possible
number -- and clears the contract reviewer's send gate on a fabricated figure. Note
the asymmetry the prose handles: even the _legitimate_ $0 (valid empty) is dangerous
enough to flag ("confirm it is intended"), but it is still categorically distinct
from the outage -- `isError: false` vs `true`. Absence of fees is not failure to
read fees.

**Categories must survive propagation.** When the Domain 1 risk-checker subagent
calls this tool and the fee service is down, it must hand the coordinator back
`{error_category: "transient", retryable: true, code: "FEE_SERVICE_UNREACHABLE"}`,
**not** a flattened "couldn't resolve the cap." The coordinator's recovery is only
deterministic if the category arrives intact.

**What the coordinator then DOES with an unresolved cap** -- escalate to a human
rather than fabricate a clean "no exposure" verdict that clears the send gate -- is a
**Domain 5** concern (load-bearing failure / reliability). It is flagged there, not
solved here: this exercise's job is to make the tool return a _categorized,
truthful_ unknown; making the coordinator act correctly on that unknown is Domain 5's.

---

## Self-grade against your rubric

- **Do the ambiguous pair's boundaries point at each other, and route the test
  request correctly?** Yes. `lookup_order` -> "do not use to look up the person ...
  that is `get_customer`"; `get_customer` -> "do not use to get the status of a
  specific order ... goes to `lookup_order`." Both name the other tool. "check order
  #12345 status" matches `lookup_order`'s WHEN and trips `get_customer`'s WHEN-NOT;
  "what's this customer's email" does the mirror. Each request has exactly one home.
- **Is each error's `isError`/`retryable` correct for its category -- especially the
  business error as `isError: true`, retryable false (not a valid empty result)?**
  Yes. Transient true/true, validation true/true (fixable-then-retryable, stated in
  prose), business true/**false**, permission true/false. "Already refunded" is a
  failed intent, modeled as an error, not an empty query.
- **Are access-failure and valid-empty-result actually distinguishable?** Yes --
  `isError: false` (order genuinely absent) vs `isError: true` + `transient` (db
  unreachable). The confident-lie failure mode is spelled out in deliverable 4.
- **Does the `.mcp.json` use `${VAR}` and leak zero secrets?** Yes -- three `${VAR}`
  expansions, no credential values, project scope, no default-secret leak.
- **Does every tool description carry all four components?** Yes -- what / when /
  when-not / returns+params on all three, with the mutual boundary on the pair and a
  no-dry-run boundary on the mutation.

The one place I sharpened your spec rather than echoing it -- pinning `retryable` to
mean "can recovery-by-retry succeed?" so validation's `true` is unambiguous to a
coordinator -- is in deliverable 3, with rationale. If you would rather `retryable`
mean strictly "retry the identical call" (which would make validation `false` and add
a separate `fixable` flag), say so and I will re-cut the four objects that way; it is
a real schema fork worth choosing on purpose.

## Next increment

This design doc is deliverable-complete. The runnable, test-driven build-out (a
`domain2-support-agent-mcp/` package mirroring Domain 1: tool registry, the four
categorized errors, the access-vs-empty seam, and the routing test
"check order #12345 status -> lookup_order" as a real passing test with the
mis-routing distractor shown failing) is the next step per CONTRIBUTING. Want me to
build that now?
