"""Live routing demo: `python -m support_agent.live_demo` (needs an API key).

The live counterpart to the routing section of `demo.py`. Where `demo.py` scores
the descriptions with the deterministic `router.route`, this sends the SAME
descriptions to the real model via `ModelRouter` (`tool_choice="auto"`) and prints
which tool the model reached for. It is the proof that the routing is a property
of the descriptions, not of the offline scorer.

Requires the live extras and a key (the deterministic demo and the whole test
suite run without either):

    poetry install --with live
    cp .env.example .env          # set ANTHROPIC_API_KEY
    poetry run python -m support_agent.live_demo

One short model call per request (a few tenths of a cent each); not offline.
The naive-getter contrast stays in `demo.py` -- it is deterministic and instant,
and running the live model twice to show ambiguity adds latency, not insight.
"""

import os

# Each request names one tool unambiguously; `expect` is what the descriptions
# should route it to, printed alongside the model's actual choice so a mismatch
# is visible rather than asserted (the model is not deterministic).
REQUESTS: list[tuple[str, str]] = [
    ("check order #12345 status", "lookup_order"),
    ("what's the email on file for customer cust-1?", "get_customer"),
    ("refund order #12345 for the customer", "issue_refund"),
]


def main() -> None:
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ModuleNotFoundError:
        pass  # dotenv ships with the live extras; env vars still work without it

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print(
            "ANTHROPIC_API_KEY is not set. The live router needs a key; set it in "
            ".env (see .env.example) or the environment. The deterministic demo "
            "(`python -m support_agent.demo`) needs no key."
        )
        return

    try:
        from support_agent.live import ModelRouter

        router = ModelRouter()  # builds the client + tool list once
    except ModuleNotFoundError:
        print(
            "The live router needs the `anthropic` package. Install the live "
            "extras:\n    poetry install --with live"
        )
        return

    print('=== live routing (real model, tool_choice="auto") ===')
    for request, expect in REQUESTS:
        chosen = router.route(request)
        mark = "ok" if chosen == expect else "DIFF"
        print(f"  [{mark:4}] {request!r:50} -> {chosen}  (expected {expect})")


if __name__ == "__main__":
    main()
