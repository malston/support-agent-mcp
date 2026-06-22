"""A deterministic stand-in for the model's tool selection.

This is the offline seam, exactly analogous to `ScriptedClient` in the Domain 1
example: it lets the routing behavior be exercised without an API key. The live
analog (`ModelRouter` in live.py) sends the same descriptions to the real model
with tool_choice="auto".

The scorer is intentionally simple and tool-agnostic. For each candidate it:
  1. DISQUALIFIES the tool if any of its own WHEN-NOT triggers appear in the
     request (the boundary firing -- "this belongs to the sibling").
  2. otherwise scores it by how many WHEN triggers appear.
The highest unique score wins; a tie is reported as ambiguous (no confident
route). Because the logic is uniform, the *descriptions* -- not the router --
decide the outcome: swap in naive boundary-less descriptions and the same request
goes ambiguous.
"""

from dataclasses import dataclass, field

from support_agent.tools import Tool


@dataclass
class RouteResult:
    tool: str | None
    ambiguous: bool = False
    reason: str = ""
    disqualified: list[str] = field(default_factory=list)


def _count(triggers: list[str], request: str) -> int:
    return sum(1 for t in triggers if t in request)


def route(request: str, tools: list[Tool]) -> RouteResult:
    req = request.lower()
    scored: list[tuple[int, str]] = []
    disqualified: list[str] = []

    for tool in tools:
        if _count(tool.when_not_triggers, req) > 0:
            disqualified.append(tool.name)
            continue
        score = _count(tool.when_triggers, req)
        if score > 0:
            scored.append((score, tool.name))

    if not scored:
        return RouteResult(tool=None, reason="no tool matched", disqualified=disqualified)

    scored.sort(reverse=True)
    top_score, top_name = scored[0]
    tied = [name for s, name in scored if s == top_score]
    if len(tied) > 1:
        return RouteResult(
            tool=None,
            ambiguous=True,
            reason=f"ambiguous between {', '.join(sorted(tied))}",
            disqualified=disqualified,
        )
    return RouteResult(tool=top_name, reason=f"matched {top_name}", disqualified=disqualified)
