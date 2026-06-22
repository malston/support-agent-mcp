"""Optional live path: route with the REAL model via tool_choice="auto".

Opt-in via `poetry install --with live` and an `ANTHROPIC_API_KEY`. The entire
test suite and the offline demo run without any of this -- `route` in router.py is
the deterministic stand-in. This module is the real selector: it sends the same
descriptions the router scores, lets the model choose, and reports which tool it
picked. It is how you confirm the descriptions route correctly against the actual
model, not just the offline scorer.

`tool_choice="auto"` is deliberate: the model decides whether and which tool to
call. Forcing a tool would fix one request and misroute every other -- routing is
a description problem, not a tool_choice problem.

Model and request shape follow the current API: `claude-opus-4-8` with adaptive
thinking.
"""

from support_agent.tools import SUPPORT_TOOLS, TOOL_INPUT_SCHEMA, Tool

MODEL = "claude-opus-4-8"


def to_anthropic_tool(tool: Tool) -> dict:
    """Render a Tool into the Messages API tools[] shape (description does the work)."""
    return {
        "name": tool.name,
        "description": tool.render_description(),
        "input_schema": TOOL_INPUT_SCHEMA,
    }


def build_anthropic_tools() -> list[dict]:
    return [to_anthropic_tool(t) for t in SUPPORT_TOOLS]


class ModelRouter:
    """Selects a tool for a request using the real model with tool_choice=auto."""

    def __init__(self, *, model: str = MODEL, max_tokens: int = 1024):
        import anthropic

        self._client = anthropic.Anthropic()
        self._model = model
        self._max_tokens = max_tokens
        self._tools = build_anthropic_tools()

    def route(self, request: str) -> str | None:
        message = self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            thinking={"type": "adaptive"},
            tools=self._tools,
            tool_choice={"type": "auto"},
            messages=[{"role": "user", "content": request}],
        )
        for block in message.content:
            if block.type == "tool_use":
                return block.name
        return None
