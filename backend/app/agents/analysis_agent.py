"""Analysis agent - converts retrieved evidence into cautious findings.

The heavy lifting is deterministic (see :mod:`app.agents.metrics`): real
metrics are computed from what the blockchain agent retrieved, and each
finding is wired to evidence ids so claims stay citable. The LLM is not
needed here - descriptive language is authored in code, keeping the
output conservative by construction.
"""

from __future__ import annotations

import logging
from typing import Any

from app.agents.metrics import build_evidence_map, build_findings, compute_metrics
from app.agents.state import AgentState, push_event
from app.models.agent import EventKind
from app.tools.specs import ToolResult

logger = logging.getLogger("argus.agents.analysis")

TX_TOOLS = ("get_recent_transactions", "get_transaction")


def _data_of(result: ToolResult) -> Any:
    return result.data if result.ok else []


def _merge_transactions(results: dict[str, list[ToolResult]]) -> list[dict]:
    seen: dict[str, dict] = {}
    for tool in TX_TOOLS:
        for result in results.get(tool, []):
            for item in (_data_of(result) or []):
                if isinstance(item, dict) and item.get("hash"):
                    seen[item["hash"]] = item
    return list(seen.values())


def analysis_node(ctx: Any) -> Any:
    """Build the graph node that produces metrics and findings."""

    def node(state: AgentState) -> dict[str, Any]:
        results = state.get("results", {})
        address = state["address"]
        settings = ctx.settings

        txs = _merge_transactions(results)
        transfers = [
            item
            for result in results.get("get_token_transfers", [])
            for item in (_data_of(result) or [])
        ]
        contracts = [
            item
            for result in results.get("get_contract_interactions", [])
            for item in (_data_of(result) or [])
        ]
        balance = next(
            (_data_of(r) for r in results.get("get_wallet_balance", []) if _data_of(r)),
            None,
        )
        tx_count = next(
            (_data_of(r) for r in results.get("get_transaction_count", []) if _data_of(r)),
            None,
        )

        evidence_map = build_evidence_map(results)
        metrics = compute_metrics(
            address,
            txs,
            transfers,
            contracts,
            balance,
            tx_count,
            settings.large_tx_threshold_eth,
            settings.repeated_counterparty_min,
        )
        findings = build_findings(
            address,
            metrics,
            txs,
            transfers,
            contracts,
            evidence_map,
        )

        events = push_event(state, "analysis", "Analyzing transaction patterns", EventKind.ANALYSIS)
        events = push_event(
            {"events": events},
            "analysis",
            f"Computed {len(findings)} evidence-backed finding(s) from {len(txs)} transaction(s)",
            EventKind.ANALYSIS,
        )

        logger.info(
            "analysis agent produced %d finding(s) for %s (tx=%d)",
            len(findings),
            address,
            len(txs),
        )
        return {
            "metrics": metrics,
            "findings": findings,
            "events": events,
        }

    return node