"""End-to-end tests of the LangGraph investigation pipeline (stubbed RPC)."""

from __future__ import annotations

from app.blockchain.provider import RpcError
from app.models.investigation import InvestigationStatus
from app.services.investigation_service import InvestigationService

from tests.conftest import wait_for
from tests.fakes import EIP55


def _populate_active_wallet(provider, subject=EIP55):
    provider.set_balance(subject, 10 * 10**18)
    provider.set_nonce(subject, 5)
    contract = "0x" + "a" * 40
    provider.set_contract(contract, {"symbol": "VT", "name": "Vault"})
    counterparty = "0x" + "b" * 40
    provider.add_block_range(100)
    # 2 small outbound txs to a contract + counterparty, 1 large inbound transfer
    provider.add_tx(tx_hash="0x" + "1" * 64, from_address=subject, to_address=contract,
                    block_number=100, input_="0x1234")
    provider.add_tx(tx_hash="0x" + "2" * 64, from_address=subject, to_address=counterparty,
                    block_number=99, value_wei=1 * 10**18)
    provider.add_tx(tx_hash="0x" + "3" * 64, from_address=counterparty, to_address=subject,
                    block_number=98, value_wei=5 * 10**18)
    provider.add_tx(tx_hash="0x" + "4" * 64, from_address=subject, to_address="0x" + "c" * 40,
                    block_number=97, value_wei=2 * 10**18, status=0)
    provider.add_token_transfer_log(
        transaction_hash="0x" + "5" * 64, token_address="0x" + "d" * 40,
        from_address=counterparty, to_address=subject, value=3 * 10**18, symbol="TST"
    )


def test_full_investigation_completes_with_adapted_retrieval(runtime, settings, provider):
    _populate_active_wallet(provider)
    service = InvestigationService(runtime, llm=None, settings=settings, chain="sepolia")
    record = service.start("Investigate this wallet and flag unusual activity", EIP55)

    final = wait_for(lambda: record.status if record.status in (InvestigationStatus.COMPLETED, InvestigationStatus.FAILED) else None)
    assert final == InvestigationStatus.COMPLETED, record.error

    assert record.report is not None
    assert record.evidence, "evidence should have been recorded"
    assert record.report.executive_summary, "executive summary must be present"
    section_titles = {s.title for s in record.report.sections}
    for expected in [
        "Wallet / Contract Overview", "Activity Summary", "Important Transactions",
        "Token Activity", "Contract Interactions", "Observed Patterns",
        "Potential Risk Indicators", "Evidence", "Limitations",
    ]:
        assert expected in section_titles

    # findings must reference only evidence that exists
    known_ids = {e["id"] for e in record.evidence}
    for finding in record.findings:
        assert set(finding.evidence_ids) <= known_ids or not finding.evidence_ids

    # adaptive behaviour: large transfer should have triggered a deep dive
    # via get_transaction on a second iteration
    assert record.iterations >= 2
    assert record.tool_calls >= 6  # 5 core tools + >=1 deep-dive get_transaction

    timeline = [e.message for e in record.events]
    assert any("Planned investigation" in m for m in timeline)
    assert any("Retrieved" in m and "get_wallet_balance" in m for m in timeline)
    assert any("Analyzing" in m for m in timeline)
    assert any("evidence-backed report" in m for m in timeline)


def test_empty_wallet_produces_informational_report(runtime, settings, provider):
    provider.set_balance(EIP55, 0)
    service = InvestigationService(runtime, llm=None, settings=settings, chain="sepolia")
    record = service.start("Investigate this wallet", EIP55)

    final = wait_for(lambda: record.status if record.status in (InvestigationStatus.COMPLETED, InvestigationStatus.FAILED) else None)
    assert final == InvestigationStatus.COMPLETED, record.error
    assert record.findings and record.findings[0].severity == "informational"


def test_iteration_budget_limits_deep_dive(provider):
    from app.config.settings import build_settings

    from tests.fakes import make_runtime

    budget_settings = build_settings(
        eth_rpc_url="http://test", llm_provider="none", max_iterations=1,
        max_tool_calls=30, max_transactions=5, large_tx_threshold_eth=0.5,
        repeated_counterparty_min=2,
    )
    _populate_active_wallet(provider)
    rt = make_runtime(provider, budget_settings)
    service = InvestigationService(rt, llm=None, settings=budget_settings, chain="sepolia")
    record = service.start("Investigate", EIP55)
    final = wait_for(lambda: record.status if record.status in (InvestigationStatus.COMPLETED, InvestigationStatus.FAILED) else None)
    assert final == InvestigationStatus.COMPLETED, record.error
    assert record.iterations == 1
    # tool_calls stays at the core 5 (no deep dive allowed)
    assert record.tool_calls <= 5


def test_rpc_failure_is_survived(runtime, settings, provider):
    provider.balances.clear()
    provider.get_balance = lambda address: (_ for _ in ()).throw(RpcError("boom"))
    service = InvestigationService(runtime, llm=None, settings=settings, chain="sepolia")
    record = service.start("Investigate this wallet", EIP55)
    final = wait_for(lambda: record.status if record.status in (InvestigationStatus.COMPLETED, InvestigationStatus.FAILED) else None)
    assert final == InvestigationStatus.COMPLETED, record.error
    assert record.report is not None
    assert any("failed" in e.message.lower() for e in record.events)
