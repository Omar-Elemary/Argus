"""In-memory fakes used across tests - no real RPC for unit tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from app.config.settings import Settings
from app.models.blockchain import (
    BlockInfo,
    RpcTransaction,
    TransactionLog,
    TransactionReceipt,
)
from app.tools.blockchain_tools import ToolRuntime

EIP55 = "0x0f52fD2320D48E4f2cBdF29196BdBAa65e0E1D04"
TOKEN_A = "0x9f8F72aA9304c8B593d555F12eF6589cC3A579A2"


class StubBlockchainProvider:
    """A deterministic stand-in for EthereumNodeProvider."""

    def __init__(self, latest_block: int = 5000) -> None:
        self.latest_block = latest_block
        self.balances: dict[str, int] = {}
        self.transaction_counts: dict[str, int] = {}
        self.transactions: dict[str, RpcTransaction] = {}
        self.receipts: dict[str, TransactionReceipt] = {}
        self.contract_code: dict[str, bytes] = {}
        self.token_metadata: dict[str, dict[str, Any]] = {}
        self.logs: list[TransactionLog] = []
        self.base_timestamp = datetime(2025, 1, 1, tzinfo=UTC)

    # ------------------------------------------------------------------
    # data builders
    # ------------------------------------------------------------------
    def set_balance(self, address: str, wei: int) -> None:
        self.balances[address.lower()] = wei

    def set_nonce(self, address: str, nonce: int) -> None:
        self.transaction_counts[address.lower()] = nonce

    def add_tx(
        self,
        *,
        tx_hash: str,
        from_address: str,
        to_address: str | None,
        value_wei: int = 0,
        block_number: int | None = None,
        status: int = 1,
        input_: str = "0x",
        nonce: int = 0,
        contract_created: str | None = None,
    ) -> RpcTransaction:
        block_number = block_number or self.latest_block
        value_eth = value_wei / 10**18
        tx = RpcTransaction(
            hash=tx_hash,
            from_address=from_address,
            to_address=to_address,
            value_wei=value_wei,
            value_eth=value_eth,
            nonce=nonce,
            block_number=block_number,
            gas=21000,
            gas_price_gwei=20.0,
            input=input_,
            status=status,
            timestamp=self._block_ts(block_number),
            is_contract_creation=contract_created is not None,
        )
        self.transactions[tx_hash.lower()] = tx
        if contract_created:
            self.contract_code[contract_created.lower()] = b"\x60\x00\x60\x00"
        self.receipts[tx_hash.lower()] = TransactionReceipt(
            hash=tx_hash, status=status, block_number=block_number, gas_used=50000, log_count=0
        )
        if self.latest_block < block_number:
            self.latest_block = block_number
        return tx

    def add_token_transfer_log(
        self,
        *,
        transaction_hash: str,
        token_address: str,
        from_address: str,
        to_address: str,
        value: int,
        block_number: int | None = None,
        symbol: str = "TEST",
        decimals: int = 18,
    ) -> None:
        block_number = block_number or self.latest_block
        topic0 = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
        def pad(a: str) -> str:
            return "0x" + a[2:].lower().zfill(64)
        self.logs.append(
            TransactionLog(
                address=token_address,
                topics=[topic0, pad(from_address), pad(to_address)],
                data=hex(value),
                block_number=block_number,
                transaction_hash=transaction_hash,
                log_index=len(self.logs),
            )
        )
        self.token_metadata.setdefault(
            token_address.lower(), {}
        ).update({"symbol": _padded_string(symbol), "decimals": decimals})

    def set_contract(self, address: str, metadata: dict[str, Any] | None = None) -> None:
        self.contract_code[address.lower()] = b"\x60\x00"
        if metadata:
            self.token_metadata.setdefault(address.lower(), {}).update(metadata)

    def add_block_range(self, height: int) -> None:
        self.latest_block = height

    # ------------------------------------------------------------------
    # provider protocol implementation
    # ------------------------------------------------------------------
    def _block_ts(self, block_number: int) -> datetime:
        return self.base_timestamp + timedelta(seconds=12 * (block_number - self.latest_block))

    def get_balance(self, address: str) -> int:
        return self.balances.get(address.lower(), 0)

    def get_transaction_count(self, address: str) -> int:
        return self.transaction_counts.get(address.lower(), 0)

    def get_transaction(self, tx_hash: str) -> RpcTransaction | None:
        return self.transactions.get(tx_hash.lower())

    def get_receipt(self, tx_hash: str) -> TransactionReceipt | None:
        return self.receipts.get(tx_hash.lower())

    def get_latest_block_number(self) -> int:
        return self.latest_block

    def get_block_info(self, block_number: int) -> BlockInfo:
        txs = [t for t in self.transactions.values() if t.block_number == block_number]
        return BlockInfo(
            number=block_number,
            hash=f"0x{block_number:064x}",
            timestamp=self._block_ts(block_number),
            transaction_count=len(txs),
        )

    def get_block_full(self, block_number: int) -> tuple[BlockInfo, list[RpcTransaction]]:
        info = self.get_block_info(block_number)
        return info, [t for t in self.transactions.values() if t.block_number == block_number]

    def get_logs(
        self,
        from_block: int,
        to_block: int,
        address: str | None = None,
        topics: list[str] | None = None,
    ) -> list[TransactionLog]:
        result: list[TransactionLog] = []
        for log in self.logs:
            if log.block_number is None or not (from_block <= log.block_number <= to_block):
                continue
            if address and log.address.lower() != address.lower():
                continue
            if topics:
                if len(topics) > 0 and topics[0] and log.topics[0] != topics[0]:
                    continue
                if len(topics) > 1 and topics[1] and len(log.topics) > 1 and log.topics[1] != topics[1]:
                    continue
                if len(topics) > 2 and topics[2] and len(log.topics) > 2 and log.topics[2] != topics[2]:
                    continue
            result.append(log)
        return result

    def get_code(self, address: str) -> bytes:
        return self.contract_code.get(address.lower(), b"")

    def is_contract(self, address: str) -> bool:
        return address.lower() in self.contract_code

    def erc20_metadata(self, address: str, fields: list[str]) -> dict[str, Any]:
        meta = self.token_metadata.get(address.lower(), {})
        return {f: meta.get(f) for f in fields}


def _padded_string(value: str) -> str:
    """Encode a string as an ABI dynamic string (offset << len << data)."""
    encoded = value.encode("utf-8").hex()
    data = encoded + "0" * max(0, 64 - len(encoded)) if len(encoded) < 64 else encoded
    return ("0" * 62 + "40") + f"{len(value):064x}" + data


def make_runtime(provider: StubBlockchainProvider, settings: Settings) -> ToolRuntime:
    from app.blockchain.indexer import BlockScanIndexer

    return ToolRuntime(provider=provider, indexer=BlockScanIndexer(provider, max_blocks=100), settings=settings)