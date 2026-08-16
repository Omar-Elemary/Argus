"""Blockchain data models.

Typed representations of on-chain data returned by the blockchain tools.
Values are normalised (value kept both in Wei and formatted ETH) so that
downstream agents never need to reason about raw hex.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field

# --- primitives --------------------------------------------------------

WEI_PER_ETH = 10**18


def wei_to_eth(wei: int) -> float:
    return wei / WEI_PER_ETH


def format_eth(wei: int, ndigits: int = 4) -> str:
    return f"{wei / WEI_PER_ETH:.{ndigits}f}"


def utcnow() -> datetime:
    return datetime.now(UTC)


class RpcTransaction(BaseModel):
    """A single on-chain transaction."""

    hash: str
    from_address: str
    to_address: str | None = None
    value_wei: int = Field(default=0, ge=0)
    value_eth: float = 0.0
    nonce: int | None = None
    block_number: int | None = None
    gas: int | None = None
    gas_price_gwei: float | None = None
    input: str = "0x"
    status: int | None = None
    timestamp: datetime | None = None
    is_contract_creation: bool = False

    @property
    def is_contract_interaction(self) -> bool:
        return self.to_address is not None and self.input not in ("0x", "")


class TransactionReceipt(BaseModel):
    hash: str
    status: int
    block_number: int | None = None
    gas_used: int | None = None
    effective_gas_price_gwei: float | None = None
    log_count: int = 0


class BlockInfo(BaseModel):
    number: int | None = None
    hash: str | None = None
    timestamp: datetime | None = None
    transaction_count: int = 0


class TransactionLog(BaseModel):
    address: str
    topics: list[str] = Field(default_factory=list)
    data: str = "0x"
    block_number: int | None = None
    transaction_hash: str | None = None
    log_index: int | None = None


class TokenTransfer(BaseModel):
    """A decoded ERC-20 Transfer event."""

    token_address: str
    from_address: str
    to_address: str
    value: int
    block_number: int | None = None
    transaction_hash: str
    token_symbol: str | None = None
    token_decimals: int | None = None

    @property
    def value_fmt(self) -> str:
        decimals = self.token_decimals or 0
        num = self.value / (10**decimals) if decimals else float(self.value)
        return f"{num:.4f}"


class ContractInfo(BaseModel):
    address: str
    is_contract: bool
    name: str | None = None
    symbol: str | None = None
    interaction_count: int = 0
    first_seen_block: int | None = None
    last_seen_block: int | None = None


class WalletBalance(BaseModel):
    address: str
    wei: int
    eth: float
    block_number: int | None = None
    chain_id: int | None = None


class EthTransfer(BaseModel):
    """An ETH value transfer between two addresses (may live inside a tx)."""

    transaction_hash: str
    from_address: str
    to_address: str
    value_wei: int = 0
    value_eth: float = 0.0
    block_number: int | None = None
    timestamp: datetime | None = None


class TransactionCount(BaseModel):
    address: str
    outgoing_nonce: int
    observed_transactions: int
    window_blocks: int