"""Evidence builders - convert tool output into citable evidence records.

Each tool registered in the registry is paired with a builder here, so
the link between "what was retrieved" and "what appears in the report"
is always explicit.
"""

from __future__ import annotations

from typing import Any

from app.models.blockchain import (
    BlockInfo,
    ContractInfo,
    RpcTransaction,
    TokenTransfer,
    TransactionCount,
    WalletBalance,
)
from app.models.evidence import Evidence


def evidence_balance(runtime: Any, kwargs: dict, data: WalletBalance) -> list[Evidence]:
    subject = kwargs["address"]
    description = (
        f"Address {subject} holds {data.eth:.4f} ETH "
        f"({data.wei} wei) as of block {data.block_number}."
    )
    return [
        Evidence.new(
            "balance",
            description=description,
            address=data.address,
            value_wei=data.wei,
            value_eth=data.eth,
            block_number=data.block_number,
            metadata={"chain_id": data.chain_id},
        )
    ]


def evidence_transaction_count(runtime: Any, kwargs: dict, data: TransactionCount) -> list[Evidence]:
    description = (
        f"Address {data.address} has an outgoing nonce of {data.outgoing_nonce} and "
        f"{data.observed_transactions} transactions observed in a "
        f"{data.window_blocks}-block scan window."
    )
    return [
        Evidence.new(
            "observation",
            description=description,
            address=data.address,
            metadata={
                "outgoing_nonce": data.outgoing_nonce,
                "observed_transactions": data.observed_transactions,
                "window_blocks": data.window_blocks,
            },
        )
    ]


def evidence_recent_transactions(runtime: Any, kwargs: dict, data: list[RpcTransaction]) -> list[Evidence]:
    subject = kwargs["address"]
    result: list[Evidence] = []
    for tx in data:
        result.append(
            Evidence.new(
                "transaction",
                description=(
                    f"Transaction {tx.hash} from {tx.from_address} to "
                    f"{tx.to_address or 'contract-creation'} of {tx.value_eth:.6f} ETH "
                    f"(block {tx.block_number})."
                ),
                transaction_hash=tx.hash,
                block_number=tx.block_number,
                timestamp=tx.timestamp,
                value_wei=tx.value_wei,
                value_eth=tx.value_eth,
                metadata={
                    "from": tx.from_address,
                    "to": tx.to_address,
                    "status": tx.status,
                    "subject": subject,
                    "input": tx.input,
                },
            )
        )
    return result


def evidence_token_transfers(runtime: Any, kwargs: dict, data: list[TokenTransfer]) -> list[Evidence]:
    result: list[Evidence] = []
    for transfer in data:
        result.append(
            Evidence.new(
                "token_transfer",
                description=(
                    f"Token transfer of {transfer.value_fmt} "
                    f"{transfer.token_symbol or transfer.token_address} from "
                    f"{transfer.from_address} to {transfer.to_address} in tx "
                    f"{transfer.transaction_hash} (block {transfer.block_number})."
                ),
                token_address=transfer.token_address,
                transaction_hash=transfer.transaction_hash,
                block_number=transfer.block_number,
                value_wei=transfer.value,
                metadata={
                    "from": transfer.from_address,
                    "to": transfer.to_address,
                    "token_symbol": transfer.token_symbol,
                    "token_decimals": transfer.token_decimals,
                },
            )
        )
    return result


def evidence_transaction(runtime: Any, kwargs: dict, data: RpcTransaction) -> list[Evidence]:
    return evidence_recent_transactions(runtime, {"address": data.from_address}, [data])


def evidence_contract_interaction(runtime: Any, kwargs: dict, data: list[ContractInfo]) -> list[Evidence]:
    subject = kwargs["address"]
    result: list[Evidence] = []
    for contract in data:
        label = f"{contract.name or ''} ({contract.symbol or ''})".strip() or "contract"
        result.append(
            Evidence.new(
                "contract",
                description=(
                    f"Subject {subject} called contract {contract.address} "
                    f"({label}) {contract.interaction_count} times between blocks "
                    f"{contract.first_seen_block} and {contract.last_seen_block}."
                ),
                contract_address=contract.address,
                address=subject,
                block_number=contract.last_seen_block,
                metadata={
                    "name": contract.name,
                    "symbol": contract.symbol,
                    "is_contract": contract.is_contract,
                    "interaction_count": contract.interaction_count,
                    "first_seen_block": contract.first_seen_block,
                },
            )
        )
    return result


def evidence_block(runtime: Any, kwargs: dict, data: BlockInfo) -> list[Evidence]:
    description = (
        f"Block {data.number} ({data.hash}) contains {data.transaction_count} "
        f"transactions and has timestamp {data.timestamp.isoformat() if data.timestamp else 'unknown'}."
    )
    return [
        Evidence.new(
            "block",
            description=description,
            block_number=data.number,
            timestamp=data.timestamp,
            metadata={"hash": data.hash, "transaction_count": data.transaction_count},
        )
    ]