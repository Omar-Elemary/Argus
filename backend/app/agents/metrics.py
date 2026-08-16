"""Deterministic analysis of retrieved on-chain evidence.

Everything here is computed from real retrieved data - the analysis
agent has no model to confabulate from. Metric code uses conservative
language ("potentially", "observed pattern", "requires further
investigation") and every finding is paired with evidence references.
"""

from __future__ import annotations

import statistics
from collections import Counter, defaultdict
from typing import Any

from app.models.investigation import Finding

LARGE_TX_MIN_SAMPLE = 8


def build_evidence_map(results: dict[str, list[Any]]) -> dict[str, dict[str, list[str]]]:
    """Map concrete on-chain objects to evidence ids.

    Returns {"hash": {hash: [ids]}, "token": {...}, "contract": {...}}.
    Relies on the registry building one evidence record per item, in
    list order - which the evidence builders guarantee.
    """
    mapping: dict[str, dict[str, list[str]]] = {"hash": {}, "token": {}, "contract": {}}
    for bucket in results.values():
        for result in bucket:
            ids = result.evidence_ids
            data = result.data if isinstance(result.data, list) else []
            for idx, item in enumerate(data):
                if idx >= len(ids):
                    break
                item = item if isinstance(item, dict) else {}
                if item.get("block_number") is not None and len(ids) > idx:
                    tx_hash = item.get("hash") or item.get("transaction_hash")
                    if tx_hash:
                        mapping["hash"].setdefault(tx_hash, []).append(ids[idx])
                token = item.get("token_address")
                if token:
                    mapping["token"].setdefault(token, []).append(ids[idx])
                contract = item.get("address")
                if contract:
                    mapping["contract"].setdefault(contract, []).append(ids[idx])
    return mapping


def compute_metrics(
    address: str,
    txs: list[dict],
    transfers: list[dict],
    contracts: list[dict],
    balance: dict | None,
    tx_count: dict | None,
    threshold_eth: float,
    repeated_min: int = 3,
) -> dict[str, Any]:
    """Produce a numeric activity profile (pure computation, no LLM)."""
    total = len(txs)
    eth_in = sum(t.get("value_eth", 0.0) for t in txs if t.get("to_address") == address)
    eth_out = sum(t.get("value_eth", 0.0) for t in txs if t.get("from_address") == address)
    in_count = sum(1 for t in txs if t.get("to_address") == address)
    out_count = sum(1 for t in txs if t.get("from_address") == address)

    counterparties: Counter[str] = Counter()
    for t in txs:
        if t.get("to_address") and t["to_address"] != address:
            counterparties[t["to_address"]] += 1
        elif t.get("from_address") and t["from_address"] != address:
            counterparties[t["from_address"]] += 1

    repeated = [
        (addr, count)
        for addr, count in counterparties.items()
        if addr and count >= repeated_min
    ]
    repeated.sort(key=lambda pair: pair[1], reverse=True)

    failed = [t for t in txs if t.get("status") == 0]
    failed_ratio = len(failed) / total if total else 0.0

    values = [t.get("value_eth", 0.0) for t in txs if t.get("to_address") == address]
    large_in = [t for t in txs if t.get("to_address") == address]
    outlier_hashes: dict[str, float] = {}
    if len(values) >= LARGE_TX_MIN_SAMPLE:
        mean = statistics.mean(values)
        stdev = statistics.stdev(values) or 0.0
        cutoff = mean + 3 * stdev
        outlier_hashes = {
            t["hash"]: t.get("value_eth", 0.0)
            for t in large_in
            if t.get("value_eth", 0.0) >= cutoff
        }
    large = [
        t
        for t in large_in
        if t.get("hash") in outlier_hashes or t.get("value_eth", 0.0) >= threshold_eth
    ]

    # bursts: most transactions inside any single block / calendar hour
    block_counter: Counter[int] = Counter(
        t.get("block_number") for t in txs if t.get("block_number") is not None
    )
    burst_block, burst_count = (block_counter.most_common(1)[0] if block_counter else (None, 0))

    timestamps = [t.get("timestamp") for t in txs if t.get("timestamp")]
    span_hours = None
    txs_per_hour = None
    if len(timestamps) >= 2:
        from datetime import datetime

        parsed: list[datetime] = []
        for raw in timestamps:
            try:
                parsed.append(datetime.fromisoformat(str(raw)))
            except (ValueError, TypeError):
                continue
        if len(parsed) >= 2:
            first = min(parsed)
            last = max(parsed)
            span_seconds = (last - first).total_seconds()
            span_hours = round(span_seconds / 3600, 1)
            txs_per_hour = round(len(parsed) / max(span_hours, 0.0001), 2)

    tokens: Counter[str] = Counter()
    token_volume: dict[str, float] = defaultdict(float)
    token_address: dict[str, str] = {}
    for tr in transfers:
        symbol = tr.get("token_symbol") or tr.get("token_address")
        tokens[symbol] += 1
        token_address.setdefault(symbol, tr.get("token_address") or symbol)
        decimals = tr.get("token_decimals") or 0
        raw = tr.get("value", 0)
        token_volume[symbol] += raw / (10**decimals) if decimals else float(raw)

    contract_counts: Counter[str] = Counter()
    contract_address: dict[str, str] = {}
    for c in contracts:
        label = c.get("symbol") or c.get("name") or c.get("address")
        contract_counts[label] += c.get("interaction_count", 1)
        contract_address.setdefault(label, c.get("address") or label)

    return {
        "address": address,
        "tx_total": total,
        "eth_in": round(eth_in, 6),
        "eth_out": round(eth_out, 6),
        "net_eth": round(eth_in - eth_out, 6),
        "in_count": in_count,
        "out_count": out_count,
        "unique_counterparties": len(counterparties),
        "repeated_counterparties": repeated[:10],
        "failed_transactions": len(failed),
        "failed_ratio": round(failed_ratio, 4),
        "largest_transactions": large[:5],
        "burst_block": burst_block,
        "burst_count": burst_count,
        "span_hours": span_hours,
        "txs_per_hour": txs_per_hour,
        "token_activity": [
            {"token": k, "address": token_address.get(k, k), "transfers": v, "volume": round(token_volume[k], 4)}
            for k, v in tokens.most_common(10)
        ],
        "contract_activity": [
            {"label": k, "address": contract_address.get(k, k), "calls": v}
            for k, v in contract_counts.most_common(5)
        ],
        "balance_eth": balance.get("eth") if balance else None,
        "outgoing_nonce": tx_count.get("outgoing_nonce") if tx_count else None,
    }


# ----------------------------------------------------------------------
# findings (evidence-linked, cautious language)
# ----------------------------------------------------------------------
def build_findings(
    address: str,
    metrics: dict[str, Any],
    txs: list[dict],
    transfers: list[dict],
    contracts: list[dict],
    evidence_map: dict[str, dict[str, list[str]]],
    max_evidence: int = 3,
) -> list[Finding]:
    findings: list[Finding] = []
    hashes = evidence_map["hash"]
    index = 1

    def add(severity: str, category: str, title: str, description: str, ids: list[str]) -> None:
        nonlocal index
        findings.append(
            Finding(
                id=f"FIND-{index:03d}",
                severity=severity,
                category=category,
                title=title,
                description=description,
                evidence_ids=ids[:max_evidence],
            )
        )
        index += 1

    if metrics["tx_total"] == 0 and not transfers and not contracts:
        add(
            "informational",
            "activity",
            "No transaction activity observed",
            "No transactions involving this address were found within the scan window.",
            _ids_for(hashes, []),
        )
        return findings

    # -- large transfers ------------------------------------------------
    large = metrics["largest_transactions"]
    if large:
        top = large[0]
        ids = _ids_for(hashes, [top.get("hash")])
        add(
            "medium",
            "transaction",
            "Potentially unusually large ETH transfer",
            (
                f"Incoming transfer of {top.get('value_eth', 0.0):.4f} ETH in "
                f"transaction {top.get('hash')} (block {top.get('block_number')}) is "
                f"potentially unusually large for this wallet's typical activity "
                "and requires further investigation."
            ),
            ids,
        )
        if len(large) > 1:
            add(
                "low",
                "transaction",
                "Large transfer cluster",
                f"{len(large)} incoming transfers exceeded the activity baseline.",
                _ids_for(hashes, [t.get('hash') for t in large]),
            )

    # -- repeated counterparties ----------------------------------------
    repeated = metrics["repeated_counterparties"]
    if repeated:
        top_cp = repeated[0][0]
        ids: list[str] = []
        for t in txs:
            if any(t.get(k) == top_cp for k in ("from_address", "to_address")):
                ids.extend(hashes.get(t.get("hash"), []))
            if len(ids) >= max_evidence:
                break
        add(
            "low",
            "counterparty",
            "Repeated counterparty observed",
            (
                f"Address repeatedly transacts with {top_cp} "
                f"({repeated[0][1]} occurrences in the window). This is an "
                "observed pattern, not itself an indicator of wrongdoing."
            ),
            ids,
        )

    # -- failed transactions ---------------------------------------------
    failed_ids: list[str] = []
    for t in txs:
        if t.get("status") == 0:
            failed_ids.extend(hashes.get(t.get("hash"), []))
    if metrics["failed_transactions"] > 0:
        ratio = metrics["failed_ratio"]
        severity = "medium" if ratio >= 0.3 else "low"
        note = (
            "An elevated failure ratio can indicate contract interaction "
            "miscounts and requires further investigation."
            if ratio >= 0.3
            else "A small number of reverts is normal."
        )
        description = (
            f"{metrics['failed_transactions']} of {metrics['tx_total']} observed "
            "transactions reverted (failed). " + note
        )
        add(
            severity,
            "transaction",
            "Transactions reverted / failed",
            description,
            failed_ids[:max_evidence],
        )

    # -- burst detection ---------------------------------------------------
    burst = metrics.get("burst_count") or 0
    if metrics["tx_total"] and burst >= 3 and burst > max(2, int(metrics["tx_total"] / 2)):
        burst_hashes = [
            t.get("hash") for t in txs if t.get("block_number") == metrics.get("burst_block")
        ]
        add(
            "low",
            "pattern",
            "Potential burst of activity",
            (
                f"{burst} transactions appear in block {metrics.get('burst_block')}, "
                "which is a potential burst of activity relative to the observed "
                "distribution. Requires further investigation to contextualise."
            ),
            _ids_for(hashes, burst_hashes),
        )

    # -- token activity ------------------------------------------------------
    token_activity = metrics["token_activity"]
    if token_activity:
        top_token = token_activity[0]
        token_ids = evidence_map["token"]
        top_ids = _ids_for(token_ids, [top_token["address"]])
        add(
            "informational",
            "token",
            "Token activity observed",
            (
                f"Active in {len(token_activity)} distinct token(s); heaviest is "
                f"{top_token['token']} with {top_token['transfers']} transfers."
            ),
            top_ids,
        )
        if top_token["token"].lower() not in ("", "eth"):
            if top_token["transfers"] >= 20:
                add(
                    "low",
                    "token",
                    "High token transfer volume",
                    (
                        f"{top_token['token']} shows {top_token['transfers']} transfers "
                        "in the window - a high observed volume for the scan range."
                    ),
                    top_ids,
                )

    # -- contract interactions ------------------------------------------------
    contract_activity = metrics["contract_activity"]
    if contract_activity:
        top_contract = contract_activity[0]
        contract_ids = evidence_map["contract"]
        target_address = top_contract["address"]
        ids = _ids_for(contract_ids, [target_address])
        add(
            "low",
            "contract",
            "Contract interaction focus",
            (
                f"The wallet most frequently calls contract {target_address} "
                f"({top_contract['calls']} calls in the window)."
            ),
            ids,
        )

    return findings


def _ids_for(mapping: dict[str, list[str]], keys: list[Any]) -> list[str]:
    ids: list[str] = []
    for key in keys:
        if not key:
            continue
        ids.extend(mapping.get(key, []))
    return ids