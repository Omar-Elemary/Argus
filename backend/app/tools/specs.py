"""Tool registry and executor.

Tools are declared as :class:`ToolSpec` entries combining a callable,
a human description, an argument schema, and an evidence builder. The
executor validates arguments, runs the tool, converts results to
JSON-safe structured data, and registers every retrieved fact as
:class:`Evidence` so that nothing can be reported without a citable
source.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.blockchain.provider import RpcError
from app.blockchain.validators import (
    ValidationError,
    validate_block_number,
    validate_eth_address,
    validate_tx_hash,
)
from app.models.agent import ToolRequest, ToolResult
from app.models.evidence import Evidence, EvidenceStore
from app.tools.blockchain_tools import (
    ToolRuntime,
    get_block,
    get_contract_interactions,
    get_recent_transactions,
    get_token_transfers,
    get_transaction,
    get_transaction_count,
    get_wallet_balance,
)
from app.tools.evidence import (
    evidence_balance,
    evidence_block,
    evidence_contract_interaction,
    evidence_recent_transactions,
    evidence_token_transfers,
    evidence_transaction,
    evidence_transaction_count,
)

logger = logging.getLogger("argus.tools")

ARG_VALIDATORS: dict[str, Callable[[Any], Any]] = {
    "address": validate_eth_address,
    "transaction_hash": validate_tx_hash,
    "block_number": validate_block_number,
}


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    purpose: str
    parameters: dict[str, dict[str, Any]]  # JSON-schema style field defs
    func: Callable[[ToolRuntime, dict[str, Any]], Any]
    evidence_builder: Callable[[ToolRuntime, dict[str, Any], Any], list[Evidence]]


# ----------------------------------------------------------------------
def build_tool_registry() -> dict[str, ToolSpec]:
    return {
        "get_wallet_balance": ToolSpec(
            name="get_wallet_balance",
            description="Current native (ETH) balance of an address.",
            purpose="Determine wallet funds.",
            parameters={"address": {"type": "string", "required": True}},
            func=get_wallet_balance,
            evidence_builder=evidence_balance,
        ),
        "get_transaction_count": ToolSpec(
            name="get_transaction_count",
            description="How many transactions the address has sent (nonce) and how many are observed in the scan window.",
            purpose="Measure overall activity level.",
            parameters={"address": {"type": "string", "required": True}},
            func=get_transaction_count,
            evidence_builder=evidence_transaction_count,
        ),
        "get_recent_transactions": ToolSpec(
            name="get_recent_transactions",
            description="Recent transactions involving the address from the scan window.",
            purpose="Inspect the address's transaction history.",
            parameters={"address": {"type": "string", "required": True}},
            func=get_recent_transactions,
            evidence_builder=evidence_recent_transactions,
        ),
        "get_token_transfers": ToolSpec(
            name="get_token_transfers",
            description="ERC-20 token transfers in/out of the address within the scan window.",
            purpose="Inspect ERC-20 token activity.",
            parameters={"address": {"type": "string", "required": True}},
            func=get_token_transfers,
            evidence_builder=evidence_token_transfers,
        ),
        "get_transaction": ToolSpec(
            name="get_transaction",
            description="Full details of one transaction by hash, including receipt status.",
            purpose="Deep-dive a specific transaction.",
            parameters={"transaction_hash": {"type": "string", "required": True}},
            func=get_transaction,
            evidence_builder=evidence_transaction,
        ),
        "get_contract_interactions": ToolSpec(
            name="get_contract_interactions",
            description="Contracts the address has interacted with in the scan window.",
            purpose="Identify contract relationships.",
            parameters={"address": {"type": "string", "required": True}},
            func=get_contract_interactions,
            evidence_builder=evidence_contract_interaction,
        ),
        "get_block": ToolSpec(
            name="get_block",
            description="Info about a specific block (hash, timestamp, tx count).",
            purpose="Establish temporal context.",
            parameters={"block_number": {"type": "integer", "required": True}},
            func=get_block,
            evidence_builder=evidence_block,
        ),
    }


class ToolExecutor:
    """Validates, runs and evidence-links tool calls."""

    def __init__(self, runtime: ToolRuntime, evidence_store: EvidenceStore) -> None:
        self.runtime = runtime
        self.evidence = evidence_store
        self._registry = build_tool_registry()

    def has_tool(self, name: str) -> bool:
        return name in self._registry

    def describe(self) -> list[dict[str, Any]]:
        return [
            {
                "name": spec.name,
                "description": spec.description,
                "purpose": spec.purpose,
                "parameters": spec.parameters,
            }
            for spec in self._registry.values()
        ]

    def execute(self, req: ToolRequest) -> ToolResult:
        spec = self._registry.get(req.tool)
        if spec is None:
            return ToolResult(
                tool=req.tool,
                ok=False,
                error=f"Unknown tool: {req.tool!r}. Available: {sorted(self._registry)}",
            )
        try:
            kwargs = self._validate_args(spec, req.args)
            data = spec.func(self.runtime, **kwargs)  # type: ignore[arg-type]
            evidence_list = spec.evidence_builder(self.runtime, kwargs, data)
            registered = [self.evidence.add(ev) for ev in evidence_list]
            return ToolResult(
                tool=req.tool,
                ok=True,
                data=to_json_safe(data),
                evidence_ids=[ev.id for ev in registered],
            )
        except (ValidationError, ValueError) as exc:
            logger.warning("Tool %s rejected input: %s", req.tool, exc)
            return ToolResult(tool=req.tool, ok=False, error=f"Invalid input: {exc}")
        except RpcError as exc:
            logger.warning("Tool %s failed on the chain: %s", req.tool, exc)
            return ToolResult(tool=req.tool, ok=False, error=f"RPC error: {exc}")
        except Exception as exc:  # noqa: BLE001 - defensive tool boundary
            logger.exception("Tool %s crashed", req.tool)
            return ToolResult(tool=req.tool, ok=False, error=f"Internal error: {exc}")

    def _validate_args(self, spec: ToolSpec, args: dict[str, Any]) -> dict[str, Any]:
        unknown = set(args) - set(spec.parameters)
        if unknown:
            raise ValidationError(f"Unexpected arguments for {spec.name}: {sorted(unknown)}")
        missing = [
            name for name, definition in spec.parameters.items() if definition.get("required") and name not in args
        ]
        if missing:
            raise ValidationError(f"Missing required arguments for {spec.name}: {missing}")
        cleaned: dict[str, Any] = {}
        for name, definition in spec.parameters.items():
            if name not in args:
                continue
            value = args[name]
            if name in ARG_VALIDATORS:
                value = ARG_VALIDATORS[name](value)
            elif definition.get("type") == "integer":
                value = int(value)
            cleaned[name] = value
        return cleaned


def to_json_safe(obj: Any) -> Any:
    """Deep convert pydantic models / datetimes to JSON-safe primitives."""
    if hasattr(obj, "model_dump"):
        return to_json_safe(obj.model_dump(mode="json"))  # type: ignore[attr-defined]
    if isinstance(obj, dict):
        return {str(k): to_json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [to_json_safe(v) for v in obj]
    return obj


__all__ = ["ToolExecutor", "ToolSpec", "build_tool_registry", "to_json_safe"]