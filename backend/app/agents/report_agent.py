"""Report agent - assembles the final evidence-linked investigation report.

The report is assembled deterministically from metrics and findings so
its structure can never drift. The LLM is used *only* to write the
executive summary prose, and it is given the structured facts (plus
instructions to never invent values). Every factual bullet carries the
evidence ids that support it.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.agents.metrics import build_evidence_map
from app.agents.state import push_event
from app.models.agent import EventKind
from app.models.evidence import EvidenceStore
from app.models.investigation import (
    Finding,
    FindingsSummary,
    InvestigationReport,
    ReportSection,
)
from app.services.llm.llm_provider import LLM, DeterministicFallbackProvider

logger = logging.getLogger("argus.agents.report")

RISK_SEVERITIES = {"low", "medium", "high"}


def _ids_by_type(store: EvidenceStore, etype: str, address: str) -> list[str]:
    return [
        e.id
        for e in store.all()
        if e.type == etype and (e.address or "").lower() == address.lower()
    ]


def _format_evidence_refs(ids: list[str]) -> str:
    if not ids:
        return ""
    return " (evidence: " + ", ".join(ids) + ")"


def build_report(
    investigation_id: str,
    address: str,
    chain: str,
    window_blocks: int,
    results: dict[str, list[Any]],
    metrics: dict[str, Any],
    findings: list[Finding],
    evidence_store: EvidenceStore,
    llm: LLM | None = None,
) -> InvestigationReport:
    """Construct the full structured report."""
    evidence_map = build_evidence_map(results)
    hashes = evidence_map["hash"]
    tokens = evidence_map["token"]
    contracts_evidence = evidence_map["contract"]

    # ---- sections -----------------------------------------------------
    overview_bullets: list[str] = []
    balance = metrics.get("balance_eth")
    if balance is not None:
        balance_ids = _ids_by_type(evidence_store, "balance", address)
        overview_bullets.append(
            f"Current ETH balance: {balance:.4f} ETH{_format_evidence_refs(balance_ids)}"
        )
    nonce = metrics.get("outgoing_nonce")
    if nonce is not None:
        overview_bullets.append(f"Outgoing transaction nonce: {nonce} (transactions ever sent).")
    overview_bullets.append(f"Chain: {chain}; RPC-scan window: last {window_blocks} blocks.")
    overview_bullets.append(f"Subject address: {address}")

    activity_bullets: list[str] = []
    activity_bullets.append(
        f"{metrics['tx_total']} transaction(s) observed (in: {metrics['in_count']}, "
        f"out: {metrics['out_count']})."
    )
    activity_bullets.append(
        f"Approx. ETH inflow {metrics['eth_in']:.4f}, outflow {metrics['eth_out']:.4f}, "
        f"net {metrics['net_eth']:.4f}."
    )
    activity_bullets.append(f"{metrics['unique_counterparties']} unique counterparty address(es).")
    if metrics.get("span_hours") is not None:
        activity_bullets.append(
            f"Activity spans ~{metrics['span_hours']}h at ~{metrics['txs_per_hour']} tx/h."
        )

    important_bullets: list[str] = []
    for tx in metrics.get("largest_transactions", []):
        ids = hashes.get(tx.get("hash"), [])
        important_bullets.append(
            f"Transfer of {tx.get('value_eth', 0.0):.4f} ETH via tx {tx.get('hash')} "
            f"(block {tx.get('block_number')}){_format_evidence_refs(ids)}"
        )
    failed_ids = [
        eid
        for key, ids in hashes.items()
        for eid in ids
        if _tx_status_for(key, results, 0)
    ]
    if metrics.get("failed_transactions"):
        important_bullets.append(
            f"{metrics['failed_transactions']} reverted transaction(s) observed"
            f"{_format_evidence_refs(failed_ids[:5])}"
        )

    token_bullets: list[str] = []
    for token in metrics.get("token_activity", []):
        ids = tokens.get(token.get("address") or token["token"], [])
        token_bullets.append(
            f"{token['token']}: {token['transfers']} transfer(s), approx "
            f"volume {token['volume']}{_format_evidence_refs(ids)}"
        )

    contract_bullets: list[str] = []
    for interaction in metrics.get("contract_activity", []):
        ids = contracts_evidence.get(interaction["address"], [])
        label = interaction["label"].lower()
        contract_bullets.append(
            f"{label}: {interaction['calls']} call(s) in window"
            f"{_format_evidence_refs(ids)}"
        )

    pattern_bullets = [
        f"[{f.severity}] {f.title}: {f.description}{_format_evidence_refs(f.evidence_ids)}"
        for f in findings
        if f.category in {"pattern", "counterparty"} or f.severity == "informational"
    ]

    risk_bullets = [
        f"[{f.severity}] {f.title}: {f.description}{_format_evidence_refs(f.evidence_ids)}"
        for f in findings
        if f.severity in RISK_SEVERITIES
    ]
    if not risk_bullets:
        risk_bullets.append(
            "No potentially unusual patterns exceeded the configured thresholds. "
            "This is not a statement of safety - just that nothing flagged in this window."
        )

    evidence_bullets = [
        f"**{e.id}** - {e.description} (source: {e.source})"
        for e in evidence_store.all()
    ]

    limitations = [
        f"Analysis is limited to the last {window_blocks} blocks of the {chain} chain "
        "as served by the configured RPC endpoint; older history was not assessed.",
        "Transaction discovery uses a bounded block-scan indexer on the public RPC; "
        "it is not a complete archive search.",
        "Token activity covers ERC-20 Transfer events only (no NFT / ERC-1155 or "
        "internal-call tracing).",
        "Findings describe observed patterns and risk indicators; they are not "
        "judgements of intent or legality.",
        "Automated smart-contract security analysis (static analysis + Slither) is "
        "planned (Phase 3) and not part of this report.",
    ]

    sections = [
        ReportSection(title="Wallet / Contract Overview", bullets=overview_bullets),
        ReportSection(title="Activity Summary", bullets=activity_bullets),
        ReportSection(title="Important Transactions", bullets=important_bullets),
        ReportSection(title="Token Activity", bullets=token_bullets),
        ReportSection(title="Contract Interactions", bullets=contract_bullets),
        ReportSection(title="Observed Patterns", bullets=pattern_bullets),
        ReportSection(title="Potential Risk Indicators", bullets=risk_bullets),
        ReportSection(title="Evidence", bullets=evidence_bullets),
        ReportSection(title="Limitations", bullets=limitations),
    ]

    # ---- executive summary --------------------------------------------
    by_severity: dict[str, int] = {}
    for f in findings:
        by_severity[f.severity] = by_severity.get(f.severity, 0) + 1
    summary_obj = FindingsSummary(
        total=len(findings),
        by_severity=by_severity,
        highlights=[f.title for f in findings[:5]],
    )

    executive = _narrate_executive_summary(
        llm, address, metrics, findings, window_blocks, chain
    )

    return InvestigationReport(
        investigation_id=investigation_id,
        subject=address,
        chain=chain,
        executive_summary=executive,
        sections=sections,
        summary=summary_obj,
        limitations=limitations,
    )


def _tx_status_for(tx_hash: Any, results: dict, target: int) -> bool:
    """Check whether any retrieved record for the hash has given status."""
    from app.agents.analysis_agent import TX_TOOLS

    for tool in TX_TOOLS:
        for bucket in results.get(tool, []):
            items = bucket.data if getattr(bucket, "ok", False) else []
            if not isinstance(items, list):
                items = [items]
            for item in items:
                if isinstance(item, dict) and item.get("hash") == tx_hash:
                    if item.get("status") == target:
                        return True
    return False


def _narrate_executive_summary(
    llm: LLM | None,
    address: str,
    metrics: dict[str, Any],
    findings: list[Finding],
    window_blocks: int,
    chain: str,
) -> str:
    data = {
        "subject": address,
        "chain": chain,
        "window_blocks": window_blocks,
        "tx_count": metrics.get("tx_total"),
        "balance_eth": metrics.get("balance_eth"),
        "total_in_eth": metrics.get("eth_in"),
        "total_out_eth": metrics.get("eth_out"),
        "failed_transactions": metrics.get("failed_transactions"),
        "findings": [
            {
                "id": f.id,
                "severity": f.severity,
                "title": f.title,
                "evidence_count": len(f.evidence_ids),
            }
            for f in findings
        ],
    }
    if llm is not None and not isinstance(llm, DeterministicFallbackProvider):
        system = (
            "You are the report writer for a blockchain intelligence system. "
            "Write a short, conservative executive summary (3-5 sentences). "
            "Only state facts that are present in the structured DATA provided. "
            "Never invent balances, hash values, block numbers or counts. "
            "Use cautious language such as 'potentially', 'observed', "
            "'requires further investigation'. Reference evidence ids like [EVID-0001] "
            "where relevant."
        )
        user = f"DATA: {json.dumps(data, default=str)}"
        try:
            narrated = llm.chat(system=system, user=user).strip()
            if narrated:
                return narrated
        except Exception as exc:  # noqa: BLE001 - never break reporting
            logger.warning("LLM narration failed; using deterministic summary: %s", exc)
    fallback = DeterministicFallbackProvider()
    return fallback.chat(
        system="Summarize the structured investigation data.", user=f"DATA: {json.dumps(data)}"
    )


def report_node(ctx: Any) -> Any:
    """Build the graph node that generates the final report."""

    def node(state: Any) -> dict[str, Any]:
        findings = state.get("findings", [])
        metrics = state.get("metrics", {})
        store: EvidenceStore = ctx.executor.evidence

        invalid = store.validate_references(
            [eid for f in findings for eid in f.evidence_ids]
        )
        if invalid:
            raise RuntimeError(
                f"Findings reference missing evidence: {invalid[:5]} - refusing to report unsupported claims"
            )

        report = build_report(
            investigation_id=state["investigation_id"],
            address=state["address"],
            chain=state.get("chain", "sepolia"),
            window_blocks=ctx.settings.max_blocks_scan,
            results=state.get("results", {}),
            metrics=metrics,
            findings=findings,
            evidence_store=store,
            llm=ctx.llm,
        )
        events = push_event(
            state,
            "report",
            f"Generating evidence-backed report ({len(findings)} finding(s), "
            f"{store.count()} evidence record(s))",
            EventKind.REPORT,
        )
        events = push_event(
            {"events": events},
            "report",
            "Report complete",
            EventKind.REPORT,
        )
        return {"report": report, "events": events}

    return node