"""Orchestrator - the LangGraph state machine that runs an investigation.

Pipeline (each box is a real subsystem with distinct responsibilities):

    plan -> retrieve (blockchain agent) -> analyze (analysis agent)
        -> decide -> (retrieve again if deeper work needed) -> report

The orchestrator owns planning and the loop decision. Loops are strictly
bounded by ``max_iterations`` and ``max_tool_calls`` (configured via the
environment) so runaway behaviour is impossible by construction.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from langgraph.graph import END, StateGraph

from app.agents.analysis_agent import analysis_node
from app.agents.blockchain_agent import retrieve_node
from app.agents.planning import extract_address, plan_investigation
from app.agents.report_agent import report_node
from app.agents.state import AgentState, push_event
from app.models.agent import AgentEvent, EventKind, ToolRequest
from app.services.llm.llm_provider import LLM
from app.tools.specs import ToolExecutor

logger = logging.getLogger("argus.agents.orchestrator")


@dataclass
class GraphContext:
    """Runtime services injected into every node."""

    executor: ToolExecutor
    llm: LLM | None
    settings: Any
    chain: str = "sepolia"


# ----------------------------------------------------------------------
# orchestrator nodes
# ----------------------------------------------------------------------
def plan_node(ctx: GraphContext) -> Callable[[AgentState], dict[str, Any]]:
    def node(state: AgentState) -> dict[str, Any]:
        query = state.get("query", "")
        address = state.get("address") or extract_address(query)
        if not address:
            events = push_event(
                state,
                "orchestrator",
                "Could not determine an address to investigate from the request.",
                EventKind.ERROR,
            )
            return {"error": "no address to investigate", "events": events}

        plan = plan_investigation(query, address)
        events = push_event(
            state,
            "orchestrator",
            f"Planned investigation ({plan.intent}) - {len(plan.requests)} retrieval tool(s)",
            EventKind.PLAN,
        )
        events = push_event(
            {"events": events},
            "orchestrator",
            "Delegating blockchain retrieval to the blockchain agent",
            EventKind.PLAN,
        )
        logger.info("orchestrator plan for %s: %s", address, [r.tool for r in plan.requests])
        return {
            "address": address,
            "plan": plan,
            "pending": plan.requests,
            "iteration": 1,
            "events": events,
        }

    return node


def decide_node(ctx: GraphContext) -> Callable[[AgentState], dict[str, Any]]:
    def node(state: AgentState) -> dict[str, Any]:
        metrics = state.get("metrics", {})
        iteration = int(state.get("iteration", 1))
        max_iterations = int(state.get("max_iterations", 3))
        tool_calls = int(state.get("tool_calls", 0))
        max_tool_calls = int(state.get("max_tool_calls", 30))

        # Which flagged transactions do we still want full receipts for?
        fetched_hashes = set()
        for bucket in state.get("results", {}).get("get_transaction", []):
            if not bucket.ok:
                continue
            items = (
                bucket.data
                if isinstance(bucket.data, list)
                else ([bucket.data] if bucket.data else [])
            )
            for item in items:
                if isinstance(item, dict) and item.get("hash"):
                    fetched_hashes.add(item["hash"])
        candidates = [
            tx for tx in metrics.get("largest_transactions", [])
            if tx.get("hash") not in fetched_hashes
        ][:3]

        if candidates and iteration < max_iterations and tool_calls < max_tool_calls:
            requests = [
                ToolRequest(
                    tool="get_transaction",
                    args={"transaction_hash": tx["hash"]},
                    purpose="deep-dive flagged transaction",
                    iteration=iteration + 1,
                )
                for tx in candidates
            ]
            events = push_event(
                state,
                "orchestrator",
                f"Requesting transaction details for {len(requests)} flagged transaction(s)",
                EventKind.PLAN,
            )
            return {"pending": requests, "iteration": iteration + 1, "events": events}
        return {}

    return node


def router_after_decide(state: AgentState) -> str:
    if state.get("error"):
        return "end"
    if state.get("pending"):
        return "retrieve"
    return "report"


def router_after_work(state: AgentState) -> str:
    if state.get("error"):
        return "end"
    return "continue"


def build_graph(ctx: GraphContext):
    """Compile the LangGraph investigation workflow."""
    workflow = StateGraph(AgentState)

    workflow.add_node("plan", plan_node(ctx))
    workflow.add_node("retrieve", retrieve_node(ctx))
    workflow.add_node("analyze", analysis_node(ctx))
    workflow.add_node("decide", decide_node(ctx))
    workflow.add_node("report", report_node(ctx))

    workflow.set_entry_point("plan")
    workflow.add_edge("plan", "retrieve")
    workflow.add_edge("retrieve", "analyze")
    workflow.add_edge("analyze", "decide")

    workflow.add_conditional_edges(
        "decide",
        router_after_decide,
        {"retrieve": "retrieve", "report": "report", "end": END},
    )
    workflow.add_conditional_edges(
        "retrieve",
        router_after_work,
        {"continue": "analyze", "end": END},
    )
    workflow.add_conditional_edges(
        "plan",
        router_after_work,
        {"continue": "retrieve", "end": END},
    )
    workflow.add_edge("report", END)

    return workflow.compile()


# ----------------------------------------------------------------------
# top-level invocation helper (used by the service layer)
# ----------------------------------------------------------------------
def run_investigation(ctx: GraphContext, investigation_id: str, query: str, address: str) -> dict[str, Any]:
    """Invoke the graph and return the final state (public facts only)."""

    graph = build_graph(ctx)
    initial: AgentState = {
        "investigation_id": investigation_id,
        "query": query,
        "address": address,
        "max_iterations": ctx.settings.max_iterations,
        "max_tool_calls": ctx.settings.max_tool_calls,
        "results": {},
        "tool_calls": 0,
        "iteration": 1,
        "events": [
            AgentEvent.of("orchestrator", "Investigation started", EventKind.PLAN)
        ],
        "chain": ctx.chain,
    }
    final_state = graph.invoke(initial)
    return final_state