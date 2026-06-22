# Domain 2 Build Exercise — MCP Tool & Error Design

You are helping me build a small MCP tool surface that exercises every concept in
Domain 2 (Tool Design & MCP Integration) of the Claude Certified Architect exam.
Build it with me incrementally. Explain each design choice as you go, and push back
hard if my instructions violate the principles below.

## Build target

A support-agent MCP server for an e-commerce backend. It exposes **three tools**, one
**deliberately ambiguous pair**, returns **structured errors across all four categories**,
and is wired up in a committed **`.mcp.json`** that leaks no secrets.

The routing test the design must pass:

> A user asks **"check order #12345 status."** The agent must route to the order tool,
> never to the customer tool.

## Requirements — every one must be satisfied

1. **Three tool definitions** (name + full description). Two must be a plausibly-ambiguous
   pair — e.g. `lookup_order` and `get_customer` — whose naive descriptions ("Retrieves
   [entity] information") would misroute the test request. The third must be a **mutation**
   (e.g. `issue_refund`). Each description must contain all four components: **what it does,
   when to use it, when NOT to use it, what it returns / key params.**

2. **Mutual disambiguation.** The ambiguous pair's "do not use" boundaries must point at
   **each other** by name. A one-sided boundary leaks — the tool without it still reads as a
   generic catch-all the model can grab. Prove the boundaries route "check order #12345
   status" to the order tool and "what's this customer's email" to the customer tool.

3. **Four error responses, one per category.** Each as a full MCP result object with
   `content`, `isError`, and `_meta` (`error_category`, `retryable`, `code`). Write the prose
   **for the model to read and act on**, not for a log file:
   - **Transient** — temporary, retry helps (timeout, rate limit). `isError: true`, retryable true.
   - **Validation** — malformed input (missing/!bad `order_id`). `isError: true`, retryable true (after fixing args).
   - **Business** — valid request, domain rule blocks it (already refunded, insufficient funds).
     `isError: true`, retryable **false**.
   - **Permission** — caller not authorized. `isError: true`, retryable **false**.

4. **Access-failure vs. valid-empty-result.** Show the two responses that look alike but mean
   opposite things, and make them distinguishable:
   - Order genuinely not found → a **valid empty result**: `isError: false`, content "No order
     found with ID 99999."
   - Orders database unreachable → an **access failure**: `isError: true`, transient.
     Explain the confident-lie failure that happens if you make them identical.

5. **`.mcp.json` with env var expansion.** Declare the server at **project scope** (committed),
   using **`${VAR}`** expansion for at least one secret (API key / DB URL). No hardcoded
   credentials anywhere in the file.

## Principles to enforce while building (Domain 2 spine)

- **The description is the primary selection mechanism** — not the name, not the params. Each
  description is prompt engineering aimed at a routing decision. Boundaries ("do not use…")
  are what prevent misrouting.
- **Sharpen vs. split.** Two tools colliding → sharpen descriptions with mutual boundaries.
  One tool overloaded ("does X, Y, or Z depending on a param") → split it so each has a clean
  trigger. Pick the right direction.
- **`tool_choice` is not a routing fix.** Forcing a tool fixes one request and breaks every
  other. `auto` = model chooses whether to call a tool. `any` = must call a tool, model
  chooses which. forced = designer names the exact tool for a known constrained step.
- **Errors are content the model reasons over.** Return `isError`, never throw — a thrown
  error can't be recovered from inside the loop. The category dictates recovery: transient/
  validation are retryable; **business/permission are not.**
- **A failed mutation is `isError: true` even when retrying won't help.** "Already refunded"
  and "insufficient funds" are real failures of intent (business, retryable false) — NOT
  valid empty results. Empty result = a _query_ succeeded with nothing to return.
- **Categories must survive propagation.** A subagent must not flatten a categorized error to
  "it failed" — preserve `error_category` and `retryable` so a coordinator's recovery stays
  deterministic.
- **Committed config carries structure, not secrets.** Project scope `.mcp.json` is shared
  via git; secrets come from each user's environment via `${VAR}`. A hardcoded credential in
  committed config is leaked into git history.
- **~4-5 tools per agent; degradation sets in around ~18.** Crisp read-only lookups are cheap
  against the budget and shareable across agents; ambiguous high-stakes mutations stay tightly
  scoped to one owner.

## Deliverables

Produce, with the design explained:

1. The three tool definitions — name + full four-component description, with the ambiguous
   pair's mutual boundaries explicit.
2. The four categorized error responses (transient / validation / business / permission) as
   JSON result objects with correct `isError` + `_meta`.
3. The access-failure vs. valid-empty-result pair, with the failure-mode explanation.
4. The `.mcp.json` with `${VAR}` env var expansion and no hardcoded secrets.
5. One paragraph: walk the request "check order #12345 status" through your descriptions and
   show why it routes to the order tool and not the customer tool.

## How I want you to grade the result (apply this to your own output)

- Do the ambiguous pair's boundaries point at **each other**, and would they route the test
  request correctly?
- Is each error's `isError` / `retryable` correct for its category — **especially that the
  business error is `isError: true`, retryable false** (not a valid empty result)?
- Are access-failure and valid-empty-result actually distinguishable (`isError` differs)?
- Does the `.mcp.json` use `${VAR}` and leak **zero** secrets?
- Does every tool description carry all four components (what / when / when-not / returns)?

## Cross-domain hook -- formula caps for the Domain 1 contract reviewer

The Domain 1 contract-review coordinator flags liability caps stated as a concrete
number ($5,000,000 > $1M) with deterministic arithmetic. Real caps are often formulas
tied to external data: "liability shall not exceed the fees paid in the trailing 12
months," "2x annual contract value." Resolving one is a Domain 2 tool problem -- the
**same access-failure-vs-valid-empty pattern as requirement 4**, pointed at a fee
service instead of an orders database. Build it here as a cross-domain extension (a
tool for the Domain 1 reviewer, not a fourth tool on the support-agent surface):

- `resolve_cap_basis` fetches the figure a formula cap references (trailing fees,
  contract value). Design its two look-alike responses:
  - Fee service unreachable -> **access failure**: `isError: true`, transient.
  - Account genuinely has no fees on record -> **valid empty result**: `isError: false`,
    content "No fees recorded for this account."
- The confident lie to avoid: collapsing "unreachable" into "fees = $0," which makes an
  unbounded formula cap read as **zero exposure** and clears the contract reviewer's
  send gate on a fabricated number.
- Categories must survive propagation (this exercise's principle): the contract
  coordinator must receive `error_category` and `retryable`, not a flattened "it failed."

What the coordinator then DOES with an unresolved cap -- escalate instead of fabricating
a clean "no exposure" verdict -- is **Domain 5** (load-bearing failure / reliability).
Flag it there; do not solve it here.

Build it step by step. Where my instructions would violate a principle above, stop and tell me.
