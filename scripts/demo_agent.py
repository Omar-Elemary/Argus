"""Demo - run the full agentic pipeline against a deterministic stub.

Lets you observe the agent behaviour (plan -> retrieve -> analyze ->
decide -> report) end to end without an RPC endpoint or API keys.

Usage:
    python scripts/demo_agent.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.config.settings import build_settings
from app.models.evidence import EvidenceStore
from app.tools.specs import ToolExecutor
from app.agents.orchestrator import GraphContext, run_investigation

# import the test stub (safe - no network)
from tests.fakes import StubBlockchainProvider, make_runtime

SUBJECT = "0x0f52fD2320D48E4f2cBdF29196BdBAa65e0E1D04"


def main() -> None:
    settings = build_settings(
        eth_rpc_url="http://demo.invalid",
        llm_provider="none",
        max_iterations=3,
        max_tool_calls=30,
        max_transactions=50,
        large_tx_threshold_eth=1.0,
        repeated_counterparty_min=2,
    )

    provider = StubBlockchainProvider(latest_block=120)
    provider.set_balance(SUBJECT, 12 * 10**18)
    provider.set_nonce(SUBJECT, 6)
    contract = "0x" + "a" * 40
    provider.set_contract(contract, {"symbol": "VT", "name": "Vault"})
    counterparty = "0x" + "b" * 40
    for i in range(4):
        provider.add_tx(
            tx_hash=f"0x{i + 1:064x}",
            from_address=SUBJECT,
            to_address=contract if i % 2 else counterparty,
            block_number=120 - i,
            value_wei=(2 if i == 3 else 1) * 10**17,
            status=0 if i == 3 else 1,
            input_="0x1234" if i % 2 == 0 else "0x",
        )
    provider.add_tx(
        tx_hash="0x" + "f" * 64,
        from_address=counterparty,
        to_address=SUBJECT,
        block_number=115,
        value_wei=50 * 10**18,  # a potentially large transfer
    )
    provider.add_token_transfer_log(
        transaction_hash="0x" + "9" * 64,
        token_address="0x" + "d" * 40,
        from_address=counterparty,
        to_address=SUBJECT,
        value=3 * 10**18,
        symbol="TST",
    )

    evidence = EvidenceStore()
    executor = ToolExecutor(make_runtime(provider, settings), evidence)
    ctx = GraphContext(executor=executor, llm=None, settings=settings, chain="sepolia")

    state = run_investigation(
        ctx,
        investigation_id="demo-0001",
        query="Investigate this wallet and flag unusual activity",
        address=SUBJECT,
    )

    print("=" * 78)
    print("EXECUTION LOG")
    print("=" * 78)
    for event in state["events"]:
        print(f"  [{event.actor:>12}] {event.message}")

    print()
    print("=" * 78)
    print("FINDINGS")
    print("=" * 78)
    for finding in state.get("findings", []):
        print(f"  {finding.id} [{finding.severity:>14}] {finding.title}")
        print(f"        {finding.description}")
        print(f"        evidence: {', '.join(finding.evidence_ids)}")

    report = state.get("report")
    if report:
        print()
        print("=" * 78)
        print("EXECUTIVE SUMMARY")
        print("=" * 78)
        print("  " + report.executive_summary.replace("\n", "\n  "))

    print()
    print(f"tool_calls={state['tool_calls']}  iterations={state['iteration']}  "
          f"evidence={evidence.count()}")


if __name__ == "__main__":
    main()