"""Blockchain agent - the subsystem that executes retrieval tools.

It owns the :class:`ToolExecutor` and is the *only* component that talks
to the blockchain. It drains the orchestrator's queue of tool requests,
applies the hard tool-call ceiling, records an event per retrieval, and
stores structured results (with evidence ids) back into graph state.
"""

from __future__ import annotations

import logging
from typing import Any

from app.agents.state import AgentState, push_event
from app.models.agent import AgentEvent, EventKind, ToolResult
from app.tools.specs import ToolExecutor

logger = logging.getLogger("argus.agents.blockchain")


def retrieve_node(ctx: Any) -> Any:
    """Build the graph node that executes pending tool requests."""

    def node(state: AgentState) -> dict[str, Any]:
        pending = list(state.get("pending", []))
        if not pending:
            return {"events": push_event(state, "blockchain", "No tool requests pending")}

        max_calls = state.get("max_tool_calls", 30)
        used = int(state.get("tool_calls", 0))
        executor: ToolExecutor = ctx.executor

        events = list(state.get("events", []))
        results: dict[str, list[ToolResult]] = {
            tool: list(bucket) for tool, bucket in (state.get("results") or {}).items()
        }
        executed = 0

        for request in pending:
            if used >= max_calls:
                events.append(
                    AgentEvent.of(
                        "blockchain",
                        f"Tool-call budget reached ({max_calls}); skipping remaining work",
                        EventKind.ERROR,
                    )
                )
                break
            result = executor.execute(request)
            used += 1
            executed += 1
            results.setdefault(request.tool, []).append(result)
            if result.ok:
                events.append(
                    AgentEvent.of(
                        "blockchain",
                        f"Retrieved {request.tool} ({_brief(args=request.args)}) - {_body(result)}",
                        EventKind.TOOL,
                    )
                )
            else:
                events.append(
                    AgentEvent.of(
                        "blockchain",
                        f"Tool {request.tool} failed: {result.error}",
                        EventKind.ERROR,
                    )
                )

        logger.debug(
            "blockchain agent executed %d tool call(s), budget %d/%d",
            executed,
            used,
            max_calls,
        )
        return {
            "results": results,
            "tool_calls": used,
            "pending": [],
            "events": events,
        }

    return node


def _brief(args: dict[str, Any]) -> str:
    joined = ", ".join(f"{k}={v}" for k, v in args.items())
    if len(joined) > 48:
        joined = joined[:45] + "..."
    return joined or "(no args)"


def _body(result: ToolResult) -> str:
    data = result.data
    if isinstance(data, list):
        return f"{len(data)} item(s)"
    if isinstance(data, dict) and data:
        keys = list(data.keys())[:3]
        return "{" + ", ".join(keys) + "}"
    return "ok"