"""Blockchain tools - the typed capability surface the agents can call.

Each tool performs a single real data-retrieval job and returns a
structured pydantic object (or list thereof). Tools do no analysis;
they only retrieve. Results are cached so a re-plan never repeats RPC
work.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.blockchain.indexer import TransactionIndexer
from app.blockchain.provider import BlockchainProvider
from app.blockchain.validators import (
    validate_block_number,
    validate_eth_address,
    validate_tx_hash,
)
from app.config.settings import Settings
from app.models.blockchain import (
    BlockInfo,
    ContractInfo,
    RpcTransaction,
    TokenTransfer,
    TransactionCount,
    WalletBalance,
)
from app.tools.cache import ToolCache

MAX_CONTRACT_METADATA = 20


@dataclass
class ToolRuntime:
    """Everything a tool needs to talk to the chain."""

    provider: BlockchainProvider
    indexer: TransactionIndexer
    settings: Settings
    cache: ToolCache = field(default_factory=ToolCache)

    def recent_transactions(self, address: str) -> list[RpcTransaction]:
        key = self.cache.key("recent_transactions", address=address.lower())
        return self.cache.memoize(
            key, lambda: self.indexer.list_transactions(address, self.settings.max_transactions)
        )


# ----------------------------------------------------------------------
# tools
# ----------------------------------------------------------------------
def get_wallet_balance(runtime: ToolRuntime, address: str) -> WalletBalance:
    addr = validate_eth_address(address)
    wei = runtime.provider.get_balance(addr)
    key = runtime.cache.key("latest_block")
    latest = runtime.cache.memoize(key, lambda: runtime.provider.get_latest_block_number())
    return WalletBalance(
        address=addr,
        wei=wei,
        eth=wei / 10**18,
        block_number=latest,
        chain_id=runtime.settings.chain_id,
    )


def get_transaction_count(runtime: ToolRuntime, address: str) -> TransactionCount:
    addr = validate_eth_address(address)
    nonce = runtime.provider.get_transaction_count(addr)
    observed = runtime.recent_transactions(addr)
    return TransactionCount(
        address=addr,
        outgoing_nonce=nonce,
        observed_transactions=len(observed),
        window_blocks=runtime.settings.max_blocks_scan,
    )


def get_recent_transactions(runtime: ToolRuntime, address: str) -> list[RpcTransaction]:
    addr = validate_eth_address(address)
    txs = runtime.recent_transactions(addr)
    enriched: list[RpcTransaction] = []
    for tx in txs:
        if tx.status is None:
            tx.status = _tx_status(runtime, tx.hash)
        if tx.timestamp is None:
            tx.timestamp = _tx_timestamp(runtime, tx.block_number)
        enriched.append(tx)
    return enriched


def get_token_transfers(runtime: ToolRuntime, address: str) -> list[TokenTransfer]:
    addr = validate_eth_address(address)
    key = runtime.cache.key("token_transfers", address=addr.lower())
    return runtime.cache.memoize(
        key,
        lambda: runtime.indexer.list_token_transfers(
            addr, runtime.settings.max_transactions
        ),
    )


def get_transaction(runtime: ToolRuntime, transaction_hash: str) -> RpcTransaction:
    tx_hash = validate_tx_hash(transaction_hash)
    key = runtime.cache.key("transaction", hash=tx_hash)
    tx = runtime.cache.memoize(
        key, lambda: runtime.provider.get_transaction(tx_hash) or raise_for_missing_tx(tx_hash)
    )
    if tx.status is None:
        tx.status = _tx_status(runtime, tx.hash)
    if tx.timestamp is None:
        tx.timestamp = _tx_timestamp(runtime, tx.block_number)
    return tx


def get_contract_interactions(runtime: ToolRuntime, address: str) -> list[ContractInfo]:
    addr = validate_eth_address(address)
    txs = runtime.recent_transactions(addr)

    counters: dict[str, dict[str, Any]] = {}
    for tx in txs:
        if tx.from_address != addr or not tx.to_address or tx.to_address == addr:
            continue
        target = tx.to_address
        entry = counters.setdefault(
            target,
            {"interaction_count": 0, "first_seen_block": tx.block_number, "last_seen_block": tx.block_number},
        )
        entry["interaction_count"] += 1
        entry["first_seen_block"] = min(
            entry["first_seen_block"] or tx.block_number, tx.block_number
        )
        entry["last_seen_block"] = max(
            entry["last_seen_block"] or tx.block_number, tx.block_number
        )

    ordered = sorted(counters.items(), key=lambda kv: kv[1]["interaction_count"], reverse=True)
    contracts: list[ContractInfo] = []
    for target, stats in ordered[:MAX_CONTRACT_METADATA]:
        is_contract = runtime.cache.memoize(
            runtime.cache.key("is_contract", address=target),
            lambda t=target: runtime.provider.is_contract(t),
        )
        meta: dict[str, Any] = {}
        if is_contract:
            meta = runtime.cache.memoize(
                runtime.cache.key("token_meta", address=target),
                lambda t=target: runtime.provider.erc20_metadata(t, ["symbol", "name"]),
            )
        symbol = _decode_meta_string(meta.get("symbol"))
        name = _decode_meta_string(meta.get("name"))
        contracts.append(
            ContractInfo(
                address=target,
                is_contract=bool(is_contract),
                name=name,
                symbol=symbol,
                interaction_count=int(stats["interaction_count"]),
                first_seen_block=stats["first_seen_block"],
                last_seen_block=stats["last_seen_block"],
            )
        )
    return contracts


def get_block(runtime: ToolRuntime, block_number: int) -> BlockInfo:
    block_number = validate_block_number(block_number)
    key = runtime.cache.key("block", number=block_number)
    return runtime.cache.memoize(key, lambda: runtime.provider.get_block_info(block_number))


# ----------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------
def _tx_status(runtime: ToolRuntime, tx_hash: str) -> Any:
    key = runtime.cache.key("receipt", hash=tx_hash)
    receipt = runtime.cache.memoize(
        key, lambda: runtime.provider.get_receipt(tx_hash)
    )
    return receipt.status if receipt else None


def _tx_timestamp(runtime: ToolRuntime, block_number: Any) -> Any:
    if block_number is None:
        return None
    key = runtime.cache.key("block_ts", number=block_number)
    return runtime.cache.memoize(
        key, lambda: runtime.provider.get_block_info(block_number).timestamp
    )


def raise_for_missing_tx(tx_hash: str) -> None:
    raise ValueError(f"Transaction {tx_hash} was not found on the chain")


def _decode_meta_string(value: Any) -> Any:
    if not isinstance(value, str) or len(value) < 130:
        return value
    try:
        offset = int(value[:64], 16)
        length = int(value[offset * 2 : offset * 2 + 64], 16)
        raw = value[offset * 2 + 64 : offset * 2 + 64 + length * 2]
        return bytes.fromhex(raw).decode("utf-8", errors="replace")
    except (ValueError, IndexError):
        return None


ALL_TOOLS = {
    "get_wallet_balance": get_wallet_balance,
    "get_transaction_count": get_transaction_count,
    "get_recent_transactions": get_recent_transactions,
    "get_token_transfers": get_token_transfers,
    "get_transaction": get_transaction,
    "get_contract_interactions": get_contract_interactions,
    "get_block": get_block,
}