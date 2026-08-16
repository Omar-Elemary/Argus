"""Transaction indexers.

Public JSON-RPC nodes do *not* expose "give me all transactions for
address X". Real deployments solve this with an indexer (Etherscan,
BlockScout, a dedicated archive). Argus therefore depends only on a
small :class:`TransactionIndexer` protocol so that any backend can be
plugged in.

MVP backends:
  * :class:`BlockScanIndexer`   - works on plain RPC by scanning a
    bounded window of recent blocks and gathering transactions that
    involve the address. Entirely real data, capped to control cost.
  * :class:`EtherscanIndexer`   - optional; enabled when an
    ETHERSCAN_API_KEY is configured and returns complete history.

Both return typed pydantic models. No data is ever synthesized.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx

from app.blockchain.provider import (
    ERC20_TRANSFER_TOPIC,
    BlockchainProvider,
)
from app.config.settings import Settings
from app.models.blockchain import RpcTransaction, TokenTransfer

logger = logging.getLogger("argus.blockchain.indexer")


@dataclass
class TransactionIndexer:
    """Protocol for address-scoped transaction discovery."""

    provider: BlockchainProvider

    def name(self) -> str:
        raise NotImplementedError

    def list_transactions(self, address: str, limit: int) -> list[RpcTransaction]:
        raise NotImplementedError

    def list_token_transfers(self, address: str, limit: int) -> list[TokenTransfer]:
        raise NotImplementedError


def _topic_param(address: str) -> str:
    return ("0x" + address[2:].lower().zfill(64))


class BlockScanIndexer(TransactionIndexer):
    """Scans a bounded window of recent blocks to find address activity."""

    def __init__(self, provider: BlockchainProvider, max_blocks: int = 200) -> None:
        super().__init__(provider)
        self.max_blocks = max_blocks

    def name(self) -> str:
        return "block-scan (RPC)"

    def list_transactions(self, address: str, limit: int) -> list[RpcTransaction]:
        from app.blockchain.provider import _normalise_address

        addr = _normalise_address(address)
        latest = self.provider.get_latest_block_number()
        start = max(0, latest - self.max_blocks + 1)
        found: list[RpcTransaction] = []
        for block_number in range(latest, start - 1, -1):
            if len(found) >= limit:
                break
            _, txs = self.provider.get_block_full(block_number)
            for tx in txs:
                if tx.from_address == addr or tx.to_address == addr:
                    found.append(tx)
                    if len(found) >= limit:
                        break
        return found

    def list_token_transfers(self, address: str, limit: int) -> list[TokenTransfer]:
        from app.blockchain.provider import _normalise_address

        addr = _normalise_address(address)
        latest = self.provider.get_latest_block_number()
        start = max(0, latest - self.max_blocks + 1)
        outgoing = self.provider.get_logs(
            start, latest, topics=[ERC20_TRANSFER_TOPIC, _topic_param(addr)]
        )
        incoming = self.provider.get_logs(
            start, latest, topics=[ERC20_TRANSFER_TOPIC, None, _topic_param(addr)]
        )
        merged: dict[tuple[str, int], TokenTransfer] = {}
        symbol_cache: dict[str, str | None] = {}
        decimals_cache: dict[str, int | None] = {}
        for log in (incoming + outgoing):
            if len(log.topics) < 3:
                continue
            to = "0x" + log.topics[2][-40:]
            fro = "0x" + log.topics[1][-40:]
            value = int(log.data, 16) if len(log.data) >= 2 else 0
            token = log.address
            key = (log.transaction_hash or "", log.log_index or 0)
            if key in merged:
                continue
            if token not in symbol_cache:
                meta = self.provider.erc20_metadata(token, ["symbol"])
                symbol_cache[token] = meta.get("symbol")
            if token not in decimals_cache:
                meta = self.provider.erc20_metadata(token, ["decimals"])
                decimals_cache[token] = meta.get("decimals")
            merged[key] = TokenTransfer(
                token_address=token,
                from_address=from_block_checksum(fro),
                to_address=from_block_checksum(to),
                value=value,
                block_number=log.block_number,
                transaction_hash=log.transaction_hash or "",
                token_symbol=decode_abi_string(symbol_cache.get(token)),
                token_decimals=decimals_cache.get(token),
            )
        ordered = sorted(merged.values(), key=lambda t: (t.block_number or 0, -1), reverse=True)
        return ordered[:limit]


def decode_abi_string(raw: str | None) -> str | None:
    """Decode a single dynamic ABI string encoded as length-prefixed data.

    Encoding is: 32-byte offset word, 32-byte length word, then the string
    data padded to a 32-byte boundary.
    """
    if not raw or raw in ("0x", "") or len(raw) < 192:
        return None
    try:
        offset = int(raw[:64], 16)  # byte offset to the data payload
        length = int(raw[64:128], 16)  # length word sits right after the offset word
    except ValueError:
        return None
    start = offset * 2
    end = start + length * 2
    if end > len(raw):
        return None
    try:
        return bytes.fromhex(raw[start:end]).decode("utf-8", errors="replace")
    except (ValueError, TypeError):
        return None


def from_block_checksum(addr: str) -> str:
    from app.blockchain.provider import _normalise_address

    return _normalise_address(addr)


class EtherscanIndexer(TransactionIndexer):
    """Optional backend using Etherscan - enabled only with an API key."""

    def __init__(
        self, provider: BlockchainProvider, api_key: str, base_url: str = "https://api.etherscan.io/api"
    ) -> None:
        super().__init__(provider)
        self.api_key = api_key
        self.base_url = base_url

    def name(self) -> str:
        return "etherscan"

    def _get(self, params: dict) -> dict:
        resp = httpx.get(
            self.base_url,
            params={**params, "apikey": self.api_key, "tag": "latest"},
            timeout=15,
        )
        resp.raise_for_status()
        payload = resp.json()
        if payload.get("status") not in ("0", "1"):
            raise RuntimeError(f"Etherscan error: {payload.get('result')}")
        return payload

    def list_transactions(self, address: str, limit: int) -> list[RpcTransaction]:
        data = self._get(
            {"module": "account", "action": "txlist", "address": address, "page": 1, "offset": limit}
        )
        out: list[RpcTransaction] = []
        for row in data.get("result") or []:
            ts = row.get("timeStamp")
            out.append(
                RpcTransaction(
                    hash=row["hash"],
                    from_address=Web3_checksum(row["from"]),
                    to_address=Web3_checksum(row["to"]) if row.get("to") else None,
                    value_wei=int(row.get("value", 0)),
                    value_eth=int(row.get("value", 0)) / 10**18,
                    nonce=int(row.get("nonce", 0)),
                    block_number=int(row.get("blockNumber") or 0),
                    gas=int(row.get("gas", 0)),
                    gas_price_gwei=int(row.get("gasPrice", 0)) / 1e9,
                    input=row.get("input", "0x"),
                    status=int(row.get("txreceipt_status") or 0),
                    timestamp=_epoch_to_dt(ts),
                    is_contract_creation=bool(row.get("contractAddress"))
                    and not row.get("to"),
                )
            )
        return out

    def list_token_transfers(self, address: str, limit: int) -> list[TokenTransfer]:
        data = self._get(
            {"module": "account", "action": "tokentx", "contractaddress": "", "address": address, "page": 1, "offset": limit}
        )
        out: list[TokenTransfer] = []
        for row in data.get("result") or []:
            decimals = int(row["tokenDecimal"]) if row.get("tokenDecimal") else None
            out.append(
                TokenTransfer(
                    token_address=Web3_checksum(row["contractAddress"])
                    if row.get("contractAddress")
                    else "",
                    from_address=Web3_checksum(row["from"]),
                    to_address=Web3_checksum(row["to"]),
                    value=int(row.get("value", 0)),
                    block_number=int(row.get("blockNumber") or 0),
                    transaction_hash=row["hash"],
                    token_symbol=row.get("tokenSymbol"),
                    token_decimals=decimals,
                )
            )
        return out


def Web3_checksum(address: str) -> str:
    from app.blockchain.provider import _normalise_address

    return _normalise_address(address)


def _epoch_to_dt(epoch: str | None) -> datetime | None:
    if not epoch:
        return None
    try:
        return datetime.fromtimestamp(int(epoch), tz=UTC)
    except (ValueError, OSError, OverflowError):
        return None


def build_indexer(settings: Settings, provider: BlockchainProvider) -> TransactionIndexer:
    """Return the best available indexer for the current configuration."""
    if settings.etherscan_api_key:
        return EtherscanIndexer(provider, settings.etherscan_api_key)
    return BlockScanIndexer(provider, max_blocks=settings.max_blocks_scan)


__all__ = [
    "TransactionIndexer",
    "BlockScanIndexer",
    "EtherscanIndexer",
    "build_indexer",
]