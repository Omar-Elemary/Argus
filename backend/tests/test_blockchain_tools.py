"""Tests for the blockchain tools via the ToolExecutor (stubbed RPC)."""

import pytest
from app.models.agent import ToolRequest

from tests.fakes import EIP55, TOKEN_A


def run(executor, tool: str, **kwargs):
    return executor.execute(ToolRequest(tool=tool, args=kwargs))


def test_wallet_balance(executor, provider):
    provider.set_balance(EIP55, 2 * 10**18)
    result = run(executor, "get_wallet_balance", address=EIP55)
    assert result.ok
    assert result.data["eth"] == pytest.approx(2.0)
    assert result.data["wei"] == 2 * 10**18
    assert len(result.evidence_ids) == 1


def test_transaction_count(executor, provider):
    provider.set_nonce(EIP55, 12)
    provider.add_tx(tx_hash="0x" + "1" * 64, from_address=EIP55, to_address="0x" + "2" * 40)
    result = run(executor, "get_transaction_count", address=EIP55)
    assert result.ok
    assert result.data["outgoing_nonce"] == 12
    assert result.data["observed_transactions"] == 1


def test_recent_transactions(executor, provider):
    provider.add_block_range(100)
    provider.add_tx(
        tx_hash="0x" + "3" * 64, from_address=EIP55, to_address="0x" + "4" * 40,
        value_wei=5 * 10**17, block_number=99, status=1,
    )
    provider.add_tx(
        tx_hash="0x" + "5" * 64, from_address="0x" + "6" * 40, to_address=EIP55,
        value_wei=7 * 10**17, block_number=98, status=0,
    )
    result = run(executor, "get_recent_transactions", address=EIP55)
    assert result.ok
    txs = result.data
    assert len(txs) == 2
    hashes = {t["hash"] for t in txs}
    assert hashes == {"0x" + "3" * 64, "0x" + "5" * 64}
    # newest first (block 99 > 98)
    assert txs[0]["block_number"] == 99
    assert txs[0]["status"] == 1
    assert txs[1]["status"] == 0
    assert len(result.evidence_ids) == 2


def test_get_transaction_single(executor, provider):
    tx = provider.add_tx(
        tx_hash="0x" + "7" * 64, from_address=EIP55,
        to_address="0x" + "8" * 40, value_wei=10**18, status=1,
    )
    result = run(executor, "get_transaction", transaction_hash=tx.hash.upper())
    assert result.ok
    assert result.data["hash"] == tx.hash.lower()
    assert result.data["status"] == 1
    assert len(result.evidence_ids) == 1


def test_get_transaction_not_found(executor):
    result = run(executor, "get_transaction", transaction_hash="0x" + "9" * 64)
    assert not result.ok
    assert "not found" in result.error.lower()


def test_contract_interactions(executor, provider):
    contract = "0x" + "a" * 40
    provider.set_contract(contract, {"symbol": "VT", "name": "Vault"})
    provider.add_block_range(100)
    for i in range(3):
        provider.add_tx(
            tx_hash=f"0x{i + 1:064x}", from_address=EIP55, to_address=contract,
            block_number=100 - i, input_="0x1234",
        )
    result = run(executor, "get_contract_interactions", address=EIP55)
    assert result.ok
    assert any(c["address"] == contract for c in result.data)
    target = next(c for c in result.data if c["address"] == contract)
    assert target["interaction_count"] == 3
    assert target["is_contract"] is True
    assert target["symbol"].lower() == "vt"
    assert len(result.evidence_ids) == 1


def test_token_transfers(executor, provider):
    provider.add_token_transfer_log(
        transaction_hash="0x" + "b" * 64, token_address=TOKEN_A,
        from_address="0x" + "c" * 40, to_address=EIP55, value=2 * 10**18,
        symbol="TST",
    )
    result = run(executor, "get_token_transfers", address=EIP55)
    assert result.ok
    assert len(result.data) == 1
    transfer = result.data[0]
    assert transfer["token_address"] == TOKEN_A
    assert transfer["to_address"] == EIP55
    assert transfer["value"] == 2 * 10**18
    assert transfer["token_symbol"] == "TST"
    assert result.evidence_ids


def test_get_block(executor, provider):
    provider.add_tx(tx_hash="0x" + "d" * 64, from_address=EIP55, to_address="0x" + "e" * 40, block_number=77)
    result = run(executor, "get_block", block_number=77)
    assert result.ok
    assert result.data["number"] == 77
    assert result.data["transaction_count"] == 1


def test_unknown_tool(executor):
    result = run(executor, "no_such_tool", address=EIP55)
    assert not result.ok
    assert "Unknown tool" in result.error


def test_invalid_address_input_fails_cleanly(executor):
    result = run(executor, "get_wallet_balance", address="not-an-address")
    assert not result.ok
    assert "Invalid input" in result.error


def test_missing_required_argument(executor):
    result = executor.execute(ToolRequest(tool="get_wallet_balance", args={}))
    assert not result.ok
    assert "Missing required arguments" in result.error


def test_unexpected_argument(executor):
    result = run(executor, "get_block", block_number=5, nope=True)
    assert not result.ok
    assert "Unexpected arguments" in result.error