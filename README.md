# Domain 2 -- Support-Agent MCP Tool & Error Design

A runnable, test-driven implementation of the CCA Domain 2 build exercise. A
support-agent MCP surface exposes three tools -- an ambiguous read pair
(`lookup_order` / `get_customer`) and a mutation (`issue_refund`) -- whose
**descriptions** route requests, returns **categorized errors** the model can act
on, and keeps an **access failure** distinct from a **valid empty result** so the
agent never lies about what it could not read.

- The design doc this implements: [`./deliverables/domain2-build-exercise.md`](./deliverables/domain2-build-exercise.md)
- The exercise prompt: [`./.prompts/domain2-build-exercise.prompt.md`](./.prompts/domain2-build-exercise.prompt.md)

## Quick start

```bash
make install            # poetry install --with dev (no API key needed)
make test               # full test suite, no key
make demo               # offline routing + error demo
```

`make help` lists every target. No Make? The commands are `poetry install --with dev`,
`poetry run pytest`, and `poetry run python -m support_agent.demo`.

The demo runs four sections against the real code:

```
=== routing: "check order #12345 status" ===
  with mutual boundaries -> lookup_order
  with naive getters     -> AMBIGUOUS (ambiguous between get_customer, lookup_order)

=== four error categories ===
  transient   isError=True   category=transient    retryable=True   code=ORDERS_UPSTREAM_TIMEOUT
  validation  isError=True   category=validation   retryable=True   code=INVALID_ORDER_ID
  business    isError=True   category=business     retryable=False  code=ALREADY_REFUNDED
  permission  isError=True   category=permission   retryable=False  code=REFUND_FORBIDDEN

=== access failure vs. valid empty (same request, opposite meaning) ===
  order absent    isError=False  category=None         retryable=False  code=ORDER_NOT_FOUND
  db unreachable  isError=True   category=transient    retryable=True   code=ORDERS_DB_UNREACHABLE

=== cross-domain resolve_cap_basis ===
  no fees (valid) isError=False  category=None         retryable=False  code=NO_FEES_ON_RECORD  resolved_basis=0
  fee svc down    isError=True   category=transient    retryable=True   code=FEE_SERVICE_UNREACHABLE  resolved_basis=NONE
```

## Optional -- live model + MCP protocol client

The demo above is deterministic and needs no key. Two optional paths exercise the
real model and the real MCP protocol -- install the live extras first:

```bash
make install-live       # adds anthropic, mcp, python-dotenv
cp .env.example .env    # set ANTHROPIC_API_KEY (only the live router needs it)

make live               # live routing: the real model picks the tool via
                        #   tool_choice="auto"  (support_agent.live_demo)
make mcp-demo           # a plain MCP client over the protocol -- no model, no key
                        #   (support_agent.mcp_client_demo)
```

`make mcp-demo` needs the `mcp` SDK but no key: it lists and calls the tools over
the protocol, showing that the same descriptions the router scores are the contract
every client sees. The server it talks to (`python -m support_agent.server`,
declared in `.mcp.json`) is what a real MCP client such as Claude Code launches.

## The headline

"check order #12345 status" **must** route to `lookup_order`, never to
`get_customer`. The routing is done by the **description** -- specifically the
mutual `WHEN NOT TO USE` boundary, where each of the ambiguous pair names the other
as the place to send colliding requests. With the real boundaried descriptions the
request routes to `lookup_order`; swap in naive "Retrieves [entity] information"
getters and the same request goes **ambiguous**. That delta is the proof the
boundary is load-bearing, not decorative.

`route` (`router.py`) is the deterministic stand-in for the model's tool selection
-- the offline seam, exactly like Domain 1's `ScriptedClient`. The thing under test
is the descriptions, not the router: the scorer is uniform and tool-agnostic, so
changing the outcome means changing the descriptions. The live analog
(`ModelRouter` in `live.py`) sends the same descriptions to the real model with
`tool_choice="auto"`. See `tests/test_routing.py` and `tests/test_tool_descriptions.py`.

## How the deliverables map to code

| Deliverable                       | Where                      | Correct pattern (demonstrated)                                     | Distractor (shown failing)                                   |
| --------------------------------- | -------------------------- | ------------------------------------------------------------------ | ------------------------------------------------------------ |
| 1. Three tool definitions         | `tools.py`                 | Four-component descriptions; mutation not overloaded               | "Retrieves X information" generic getters                    |
| 2. Mutual disambiguation          | `tools.py`, `router.py`    | Each boundary names the **other** tool; sibling is disqualified    | One-sided boundary -> the other reads as a catch-all         |
| 3. Four categorized errors        | `errors.py`, `handlers.py` | `isError`+`_meta`; business is `isError:true`/retryable **false**  | Model `business` failure as a valid empty result             |
| 4. Access-failure vs. valid-empty | `handlers.py`, `errors.py` | `isError:false` (absent) vs `isError:true`+transient (unreachable) | Same shape for both -> "no such order" on an outage          |
| 5. `.mcp.json` with `${VAR}`      | `.mcp.json`, `config.py`   | Project scope, `${VAR}` on every secret, scanner proves zero leaks | Hardcoded credential in committed config                     |
| Cross-domain `resolve_cap_basis`  | `cap_basis.py`             | Unreachable -> no number; no-fees -> valid `$0`                    | Collapse "unreachable" into "fees = $0" (fake zero exposure) |
| Categories survive propagation    | `propagation.py`           | Coordinator reads `error_category`/`retryable` off `_meta`         | Subagent flattens the error to "it failed"                   |

## The one decision the field name encodes -- `retryable`

`retryable` answers **"can recovery-by-retry succeed?"**, not "retry the identical
call." Transient -> yes, same call. Validation -> yes, **but only after the agent
fixes the arguments** (a verbatim retry fails the same way -- the prose says so).
Business / permission -> no; change strategy or escalate. This keeps a coordinator's
recovery deterministic: a `retryable: true` validation error never means "replay the
same bytes." See the design doc's note on why this is pinned.

## Access failure vs. valid empty -- the confident lie

The dangerous failure is making the two identical. If a database outage returned the
same shape as a genuine miss (`isError: false`, "no order found"), the model cannot
tell "we looked and it isn't there" from "we couldn't look" -- and it will fluently
tell the customer the order does not exist. The `isError` split forces the loop to
branch: `false` -> answer the user; `true` + `transient` -> retry, never assert
non-existence. `tests/test_access_vs_empty.py` asserts the outage never renders as
"no order found" and always reads "UNKNOWN".

## Cross-domain hook -- `resolve_cap_basis` (for the Domain 1 reviewer)

The Domain 1 reviewer handles numeric caps with deterministic arithmetic. A
**formula** cap ("fees paid in the trailing 12 months") needs an external figure,
and resolving it is the _same_ access-vs-empty pattern pointed at a fee service:

- fee service unreachable -> **access failure** (`isError: true`, transient), and it
  carries **no** `resolved_basis` -- collapsing it into `$0` would make an unbounded
  cap read as zero exposure and clear the reviewer's send gate on a fabricated number.
- account genuinely has no fees -> **valid empty** (`isError: false`,
  `resolved_basis: 0`).

`propagation.py` shows the category surviving from an isolated subagent up to a
coordinator (the distractor `flatten_to_failed` throws it away). **What the
coordinator then DOES with an unresolved cap** -- escalate rather than fabricate a
clean "no exposure" verdict -- is **Domain 5** (load-bearing failure), flagged
there, not solved here.

## `tool_choice` is not a routing fix

Routing is a description problem. The live path uses `tool_choice="auto"` (model
decides whether and which tool to call). Forcing a tool would fix one request and
misroute every other; `any` would force a call on turns that should just talk to the
user. Forced choice is for a known constrained sub-step, never a substitute for
descriptions that route on their own.

## Module guide

| Module           | Responsibility                                                                          |
| ---------------- | --------------------------------------------------------------------------------------- |
| `tools.py`       | The three tool definitions + `render_description`; the naive distractor surface         |
| `router.py`      | `route` -- the deterministic tool-selection seam (offline analog of the model)          |
| `errors.py`      | `mcp_error` / `mcp_ok` builders + the named scenario objects (the exact prose)          |
| `handlers.py`    | `lookup_order` / `get_customer` / `issue_refund` -- map backend outcomes to results     |
| `backend.py`     | `OrdersBackend` / `CustomersBackend` seam + `StubBackend` (stages each condition)       |
| `cap_basis.py`   | `resolve_cap_basis` + `StubFeeService` -- the cross-domain access-vs-empty tool         |
| `propagation.py` | Category survival from subagent to coordinator (and the flattening distractor)          |
| `config.py`      | Load `.mcp.json`, expand `${VAR}`, scan for hardcoded secrets (rejects default secrets) |
| `server.py`      | The MCP server in `.mcp.json` -- testable `dispatch` core + optional `mcp`-SDK glue     |
| `live.py`        | Optional `ModelRouter` -- real-model routing via `tool_choice="auto"`                   |
| `demo.py`        | The four-section offline demonstration                                                  |

## The live path (optional)

```bash
poetry install --with dev --with live
export ANTHROPIC_API_KEY=...           # or cp .env.example .env
```

`ModelRouter` (`live.py`) sends the real descriptions to `claude-opus-4-8` with
`tool_choice="auto"` and reports which tool the model selected. The deterministic
`route` powers every test, so the suite never needs a key.

The `live` group also installs the `mcp` SDK, so the server in `.mcp.json` runs:

```bash
python -m support_agent.server        # stdio MCP server over in-memory sample data
```

`server.py`'s `dispatch` core is covered by the offline suite; only the stdio glue
needs the SDK (same opt-in pattern as the model path).
