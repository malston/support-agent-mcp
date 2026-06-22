"""Category survival across propagation.

An isolated subagent calls a tool and hands the result up to a coordinator. The
correct subagent returns the MCP result UNCHANGED; the coordinator reads the
category off `_meta` and keeps its recovery deterministic. The distractor
(`flatten_to_failed`) collapses everything to a bare string and throws the
recovery contract away.
"""

from dataclasses import dataclass

from support_agent.cap_basis import FeeService, resolve_cap_basis
from support_agent.errors import ErrorCategory


@dataclass
class CapResolution:
    resolved: bool
    error_category: ErrorCategory | None
    retryable: bool
    code: str
    basis: float | None


def subagent_resolve_cap(account_id: str, fee_service: FeeService) -> dict:
    """Isolated subagent: call the tool, return its result object verbatim."""
    return resolve_cap_basis({"account_id": account_id}, fee_service)


def coordinator_receive(result: dict) -> CapResolution:
    """Preserve error_category + retryable so recovery stays deterministic."""
    meta = result["_meta"]
    return CapResolution(
        resolved=not result["isError"],
        error_category=meta["error_category"],
        retryable=meta["retryable"],
        code=meta["code"],
        basis=meta.get("resolved_basis"),
    )


def flatten_to_failed(result: dict) -> str:
    """Distractor: a subagent that flattens the categorized error to a string.

    This is what NOT to do -- the coordinator can no longer distinguish a
    retryable transient outage from a final business block.
    """
    return "ok" if not result["isError"] else "it failed"
