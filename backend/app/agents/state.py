"""Graph state for the investigation workflow."""

from __future__ import annotations

from typing import Any, TypedDict

from app.models.agent import AgentEvent, InvestigationPlan, ToolRequest, ToolResult
from app.models.investigation import Finding, InvestigationReport


class AgentState(TypedDict, total=False):
    investigation_id: str
    query: str
    address: str
    plan: InvestigationPlan
    pending: list[ToolRequest]
    results: dict[str, list[ToolResult]]
    tool_calls: int
    iteration: int
    max_iterations: int
    max_tool_calls: int
    chain: str
    events: list[AgentEvent]
    findings: list[Finding]
    metrics: dict[str, Any]
    report: InvestigationReport
    error: str


# ----------------------------------------------------------------------
# small state helpers used by the nodes
# ----------------------------------------------------------------------
def push_event(state: AgentState, actor: str, message: str, kind: Any = None) -> list[AgentEvent]:
    """Return new events list with one more entry (pure helper)."""
    events = list(state.get("events", []))
    events.append(AgentEvent.of(actor, message, kind))
    return events


def all_results(state: AgentState) -> list[ToolResult]:
    results = state.get("results", {})
    return [result for bucket in results.values() for result in bucket]


def result_for_tool(state: AgentState, tool: str) -> list[ToolResult]:
    return state.get("results", {}).get(tool, [])


def budget_remaining(state: AgentState) -> bool:
    return state.get("tool_calls", 0) < state.get("max_tool_calls", 30) and state.get(
        "iteration", 1
    ) < state.get("max_iterations", 3)