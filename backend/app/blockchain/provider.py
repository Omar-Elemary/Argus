"""Ethereum RPC provider.

Wraps Web3.py behind a small, testable interface. It adds:
  * request timeouts
  * retries with exponential backoff
  * a minimum interval between calls (rate-limit protection)
  * chain-id validation (Sepolia vs Mainnet)
  * conversion of raw RPC payloads into typed pydantic models

The provider knows nothing about agents or tools - it is pure data
access and can be swapped for another implementation (e.g. an archive
node, a different JSON-RPC gateway, or a custom light-client).
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Iterable
from datetime import UTC
from threading import Lock
from typing import Any

from web3 import Web3
from web3.exceptions import Web3Exception

from app.config.settings import Settings
from app.models.blockchain import (
    BlockInfo,
    RpcTransaction,
    TransactionLog,
    TransactionReceipt,
)

logger = logging.getLogger("argus.blockchain.provider")

ZERO_HASH = "0x0000000000000000000000000000000000000000"

# SIGNAATURE of the canonical ERC20 Transfer event.
ERC20_TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"


class RpcError(Exception):
    """Raised when an RPC call ultimately fails after retries."""


class NodeMisconfigured(RpcError):
    """Raised when the node/network does not match expectations."""


class BlockchainProvider:
    """Protocol implemented by any on-chain data provider.

    New providers (Etherscan-scoped, archive nodes, light clients) can be
    plugged in by implementing this interface; the tools and agents only
    depend on it.
    """

    def get_balance(self, address: str) -> int:
        ...

    def get_transaction_count(self, address: str) -> int:
        """Number of transactions *sent* by the address (nonce)."""

    def get_transaction(self, tx_hash: str) -> RpcTransaction | None:
        ...

    def get_receipt(self, tx_hash: str) -> TransactionReceipt | None:
        ...

    def get_latest_block_number(self) -> int:
        ...

    def get_block_info(self, block_number: int) -> BlockInfo:
        ...

    def get_block_full(self, block_number: int) -> tuple[BlockInfo, list[RpcTransaction]]:
        ...

    def get_logs(
        self,
        from_block: int,
        to_block: int,
        address: str | None = None,
        topics: list[str] | None = None,
    ) -> list[TransactionLog]:
        ...

    def get_code(self, address: str) -> bytes:
        ...

    def erc20_metadata(self, address: str, fields: Iterable[str]) -> dict[str, Any]:
        """Return name/symbol/decimals for an ERC20 token (best effort)."""

    def is_contract(self, address: str) -> bool:
        ...


def _normalise_address(value: Any) -> str:
    return Web3.to_checksum_address(value.lower())


class EthereumNodeProvider:
    """An implementation of :class:`BlockchainProvider` over Web3.py."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.w3: Web3 = Web3(
            Web3.HTTPProvider(
                settings.eth_rpc_url,
                request_kwargs={"timeout": settings.rpc_timeout_seconds},
            )
        )
        self._min_interval = settings.rpc_min_interval_ms / 1000.0
        self._last_call = 0.0
        self._rate_lock = Lock()
        if not self.w3.is_connected():
            raise NodeMisconfigured(
                f"Cannot connect to Ethereum RPC at {settings.eth_rpc_url!r}"
            )
        self._validate_chain()

    # ------------------------------------------------------------------
    # reliability machinery
    # ------------------------------------------------------------------
    def _validate_chain(self) -> None:
        chain_id = self.w3.eth.chain_id
        expected = self.settings.chain_id
        if expected and chain_id != expected:
            raise NodeMisconfigured(
                f"RPC chain id {chain_id} does not match configured network "
                f"{self.settings.network!r} (expected {expected}). "
                "Check ETH_RPC_URL / ETH_NETWORK / ETH_CHAIN_ID."
            )
        logger.info("Connected to %s (chain id %d)", self.settings.network, chain_id)

    def _call(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        with self._rate_lock:
            wait = self._last_call + self._min_interval - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            tries = self.settings.rpc_retries + 1
            delay = self.settings.rpc_retry_backoff
            last_exc: Exception | None = None
            for attempt in range(tries):
                try:
                    result = fn(*args, **kwargs)
                    self._last_call = time.monotonic()
                    return result
                except Web3Exception as exc:
                    last_exc = exc
                    if attempt < tries - 1:
                        backoff = delay * (2**attempt)
                        logger.debug(
                            "RPC call %r failed (attempt %d/%d): %s; retrying in %.2fs",
                            getattr(fn, "__name__", fn),
                            attempt + 1,
                            tries,
                            exc,
                            backoff,
                        )
                        time.sleep(backoff)
            self._last_call = time.monotonic()
            raise RpcError(
                f"RPC call failed after {tries} attempts: {last_exc}"
            ) from last_exc

    # ------------------------------------------------------------------
    # typed data access
    # ------------------------------------------------------------------
    def get_balance(self, address: str) -> int:
        addr = _normalise_address(address)
        return int(self._call(self.w3.eth.get_balance, addr))

    def get_transaction_count(self, address: str) -> int:
        addr = _normalise_address(address)
        return int(self._call(self.w3.eth.get_transaction_count, addr))

    def get_transaction(self, tx_hash: str) -> RpcTransaction | None:
        tx = self._call(self.w3.eth.get_transaction, tx_hash)
        if tx is None:
            return None
        return self._convert_tx(tx)

    def get_receipt(self, tx_hash: str) -> TransactionReceipt | None:
        rcpt = self._call(self.w3.eth.get_transaction_receipt, tx_hash)
        if rcpt is None:
            return None
        gas_price = getattr(rcpt, "effectiveGasPrice", None)
        return TransactionReceipt(
            hash=Web3.to_hex(rcpt.transactionHash),
            status=int(rcpt.status),
            block_number=int(rcpt.blockNumber) if rcpt.blockNumber is not None else None,
            gas_used=int(rcpt.gasUsed) if rcpt.gasUsed is not None else None,
            effective_gas_price_gwei=(
                gas_price / 1e9 if gas_price is not None else None
            ),
            log_count=len(rcpt.logs),
        )

    def get_latest_block_number(self) -> int:
        return int(self._call(self.w3.eth.block_number))

    def get_block_info(self, block_number: int) -> BlockInfo:
        block = self._call(self.w3.eth.get_block, block_number)
        return self._convert_block(block)

    def get_block_full(self, block_number: int) -> tuple[BlockInfo, list[RpcTransaction]]:
        block = self._call(self.w3.eth.get_block, block_number, True)
        info = self._convert_block(block)
        block_ts = info.timestamp
        txs: list[RpcTransaction] = []
        for tx in block.transactions:
            converted = self._convert_tx(tx)
            if converted.timestamp is None:
                converted.timestamp = block_ts
            txs.append(converted)
        return info, txs

    def get_logs(
        self,
        from_block: int,
        to_block: int,
        address: str | None = None,
        topics: list[str] | None = None,
    ) -> list[TransactionLog]:
        filter_params: dict[str, Any] = {
            "fromBlock": from_block,
            "toBlock": to_block,
        }
        if address:
            filter_params["address"] = _normalise_address(address)
        if topics:
            filter_params["topics"] = topics
        raw = self._call(self.w3.eth.get_logs, filter_params)
        logs: list[TransactionLog] = []
        for log in raw:
            logs.append(
                TransactionLog(
                    address=_normalise_address(log.address),
                    topics=[Web3.to_hex(t) for t in (log.topics or [])],
                    data=Web3.to_hex(log.data),
                    block_number=int(log.blockNumber) if log.blockNumber is not None else None,
                    transaction_hash=Web3.to_hex(log.transactionHash)
                    if log.transactionHash is not None
                    else None,
                    log_index=int(log.logIndex) if log.logIndex is not None else None,
                )
            )
        return logs

    def get_code(self, address: str) -> bytes:
        addr = _normalise_address(address)
        return bytes(self._call(self.w3.eth.get_code, addr))  # type: ignore[arg-type]

    def is_contract(self, address: str) -> bool:
        return bool(self.get_code(address))

    def erc20_metadata(self, address: str, fields: Iterable[str]) -> dict[str, Any]:
        """Best-effort ERC20 name/symbol/decimals lookup via eth_call.

        Non-standard tokens simply omit the field - we never fabricate.
        """
        addr = _normalise_address(address)
        result: dict[str, Any] = {}
        field_map: dict[str, Any] = {
            "name": ("name()", []),
            "symbol": ("symbol()", []),
            "decimals": ("decimals()", []),
        }
        for field in fields:
            spec = field_map.get(field)
            if spec is None:
                continue
            signature, _ = spec
            try:
                value = self._call(
                    self.w3.eth.call, {"to": addr, "data": Web3.keccak(text=signature)[:4].hex()}
                )
                if field == "decimals":
                    result[field] = int(self.w3.to_int(hexstr=value))
                else:
                    result[field] = value.hex()
            except (Web3Exception, ValueError, TypeError):
                logger.debug("ERC20 %s lookup failed for %s", field, addr)
        return result

    # ------------------------------------------------------------------
    # conversion helpers
    # ------------------------------------------------------------------
    def _convert_block(self, block: Any) -> BlockInfo:
        from datetime import datetime

        ts = block.timestamp
        return BlockInfo(
            number=int(block.number) if block.number is not None else None,
            hash=Web3.to_hex(block.hash) if block.hash is not None else None,
            timestamp=datetime.fromtimestamp(ts, tz=UTC) if ts is not None else None,
            transaction_count=len(block.transactions),
        )

    def _convert_tx(self, tx: Any) -> RpcTransaction:
        to_addr = None
        if tx.to is not None:
            to_addr = _normalise_address(tx.to)
        value = int(tx.value) if tx.value is not None else 0
        gas_price = getattr(tx, "gasPrice", None)
        return RpcTransaction(
            hash=Web3.to_hex(tx.hash),
            from_address=_normalise_address(tx["from"]),
            to_address=to_addr,
            value_wei=value,
            value_eth=value / 10**18,
            nonce=int(tx.nonce) if tx.nonce is not None else None,
            block_number=int(tx.blockNumber) if tx.blockNumber is not None else None,
            gas=int(tx.gas) if tx.gas is not None else None,
            gas_price_gwei=(gas_price / 1e9) if gas_price is not None else None,
            input=Web3.to_hex(tx.input),
            is_contract_creation=to_addr is None or to_addr == ZERO_HASH,
        )


class NoopProvider:
    """A minimal provider that returns empty or zeroed values.

    Useful for running the API without an RPC endpoint configured.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def get_balance(self, address: str) -> int:
        return 0

    def get_transaction_count(self, address: str) -> int:
        return 0

    def get_transaction(self, tx_hash: str) -> RpcTransaction | None:
        return None

    def get_receipt(self, tx_hash: str) -> TransactionReceipt | None:
        return None

    def get_latest_block_number(self) -> int:
        return 0

    def get_block_info(self, block_number: int) -> BlockInfo:
        return BlockInfo(number=0, hash=None, timestamp=None, transaction_count=0)

    def get_block_full(self, block_number: int) -> tuple[BlockInfo, list[RpcTransaction]]:
        return (self.get_block_info(block_number), [])

    def get_logs(self, from_block: int, to_block: int, address: str | None = None, topics: list[str] | None = None) -> list[TransactionLog]:
        return []

    def get_code(self, address: str) -> bytes:
        return b""

    def erc20_metadata(self, address: str, fields: Iterable[str]) -> dict[str, Any]:
        return {}

    def is_contract(self, address: str) -> bool:
        return False


__all__ = [
    "BlockchainProvider",
    "EthereumNodeProvider",
    "RpcError",
    "NodeMisconfigured",
    "ERC20_TRANSFER_TOPIC",
    "NoopProvider",
]