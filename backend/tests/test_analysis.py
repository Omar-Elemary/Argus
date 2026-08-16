"""Tests for the deterministic analysis engine (metrics + findings)."""

import pytest
from app.agents.metrics import build_evidence_map, build_findings, compute_metrics
from app.models.agent import ToolResult

from tests.fakes import EIP55, TOKEN_A


def tx(hash_, from_, to, value_eth, block=100, status=1, ts=None):
    return {
        "hash": hash_,
        "from_address": from_,
        "to_address": to,
        "value_eth": value_eth,
        "block_number": block,
        "status": status,
        "timestamp": ts,
    }


def findings_from(settings, txs, transfers=None, contracts=None, balance=None, tx_count=None, results=None):
    metrics = compute_metrics(
        EIP55, txs, transfers or [], contracts or [],
        balance, tx_count, settings.large_tx_threshold_eth, settings.repeated_counterparty_min,
    )
    if results is None:
        ids = [f"EVID-{i + 1:04d}" for i in range(len(txs))]
        results = {
            "get_recent_transactions": [
                ToolResult(tool="get_recent_transactions", ok=True, data=txs, evidence_ids=ids)
            ]
        }
    e_map = build_evidence_map(results)
    return metrics, build_findings(EIP55, metrics, txs, transfers or [], contracts or [], e_map)


def test_evidence_map_links_hashes():
    t1 = tx("0x" + "1" * 64, EIP55, "0x" + "a" * 40, 0.1)
    results = {
        "get_recent_transactions": [
            ToolResult(tool="get_recent_transactions", ok=True, data=[t1], evidence_ids=["EVID-0001"])
        ]
    }
    mapping = build_evidence_map(results)
    assert mapping["hash"]["0x" + "1" * 64] == ["EVID-0001"]


def test_large_incoming_transfer_flagged(settings):
    big = tx("0x" + "2" * 64, "0x" + "a" * 40, EIP55, value_eth=50.0, block=101)
    small = tx("0x" + "3" * 64, "0x" + "b" * 40, EIP55, value_eth=0.001, block=102)
    metrics, findings = findings_from(settings, [big, small])
    assert metrics["eth_in"] == pytest.approx(50.001)

    large_findings = [f for f in findings if "large ETH transfer" in f.title]
    assert large_findings
    assert large_findings[0].evidence_ids  # references evidence
    assert large_findings[0].severity == "medium"


def test_failed_transactions_ratio(settings):
    t1 = tx("0x" + "4" * 64, EIP55, "0x" + "c" * 40, 0.1, status=1)
    t2 = tx("0x" + "5" * 64, EIP55, "0x" + "d" * 40, 0.2, status=0)
    metrics, findings = findings_from(settings, [t1, t2])
    assert metrics["failed_transactions"] == 1
    failed = [f for f in findings if "reverted" in f.title.lower()]
    assert failed and failed[0].evidence_ids


def test_repeated_counterparty(settings):
    other = "0x" + "e" * 40
    txs = [
        tx(f"0x{i + 10:064x}", EIP55, other, 0.1)
        for i in range(settings.repeated_counterparty_min)
    ]
    metrics, findings = findings_from(settings, txs)
    assert other in [c[0] for c in metrics["repeated_counterparties"]]
    assert any("Repeated counterparty" in f.title for f in findings)


def test_no_activity_is_informational(settings):
    metrics, findings = findings_from(settings, [])
    assert metrics["tx_total"] == 0
    assert len(findings) == 1
    assert findings[0].severity == "informational"


def test_token_activity_finding(settings):
    transfer = {
        "token_address": TOKEN_A,
        "from_address": "0x" + "f" * 40,
        "to_address": EIP55,
        "value": 2 * 10**18,
        "block_number": 100,
        "transaction_hash": "0x" + "6" * 64,
        "token_symbol": "TST",
        "token_decimals": 18,
    }
    results = {
        "get_token_transfers": [
            ToolResult(tool="get_token_transfers", ok=True, data=[transfer], evidence_ids=["EVID-0001"])
        ]
    }
    metrics, findings = findings_from(settings, [], transfers=[transfer], results=results)
    assert metrics["token_activity"][0]["token"] == "TST"
    assert metrics["token_activity"][0]["volume"] == pytest.approx(2.0)
    assert any("Token activity" in f.title for f in findings)


def test_language_is_cautious(settings):
    big = tx("0x" + "7" * 64, "0x" + "9" * 40, EIP55, value_eth=99.0)
    _, findings = findings_from(settings, [big])
    joined = " ".join(f.title + " " + f.description for f in findings).lower()
    assert "malicious" not in joined
    assert "potentially" in joined or "requires further investigation" in joined