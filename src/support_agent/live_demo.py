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
#
# Expect the refund request to often print [DIFF] -> lookup_order: that is correct,
# not a misroute. issue_refund's description explicitly says to confirm the order exists
# with lookup_order before an irreversible refund (the "WHEN NOT TO USE" boundary names
# lookup_order as a prerequisite), so the model's first move is to verify. This driver
# captures only the first tool_use; a full loop would then refund.
REQUESTS: list[tuple[str, str]] = [
    ("check order #12345 status", "lookup_order"),
    ("what's the email on file for customer cust-1?", "get_customer"),
    ("refund order #12345 for the customer", "issue_refund"),
]


def main() -> None:
    dotenv_loaded = False
    try:
        from dotenv import load_dotenv

        load_dotenv()
        dotenv_loaded = True
    except ModuleNotFoundError:
        pass  # dotenv ships with the live extras; env vars still work without it
    except Exception as e:
        print(f"Warning: Failed to load .env file: {e}")

    if not os.environ.get("ANTHROPIC_API_KEY"):
        status = " (but .env had an error)" if not dotenv_loaded else ""
        print(
            f"ANTHROPIC_API_KEY is not set{status}. The live router needs a key; set it in "
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
    except Exception as e:
        print(f"Failed to initialize the live router: {type(e).__name__}: {e}")
        return

    print('=== live routing (real model, tool_choice="auto") ===')
    for request, expect in REQUESTS:
        try:
            chosen = router.route(request)
        except Exception as e:
            print(
                f"  [ERROR] {request!r:50} -> Failed: {type(e).__name__}: {e}"
            )
            continue
        mark = "ok" if chosen == expect else "DIFF"
        print(f"  [{mark:4}] {request!r:50} -> {chosen}  (expected {expect})")


if __name__ == "__main__":
    main()
