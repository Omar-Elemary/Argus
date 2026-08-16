"""Evidence model and store.

Every factual claim produced by the system must be backed by an
`:class:`Evidence` record that describes *where* the fact came from
(transaction hash, block number, contract address, source, timestamp).

Findings in the report reference evidence by stable id (EVID-001, ...).
The report agent is constrained to only reference evidence that exists
in the store - it is never allowed to invent support.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

EVIDENCE_TYPES = {
    "transaction",
    "block",
    "transfer",
    "token_transfer",
    "contract",
    "balance",
    "eth_transfer",
    "observation",
}


class Evidence(BaseModel):
    """A single citable piece of evidence."""

    id: str = ""  # assigned by the store: EVID-001 ...
    type: str
    source: str = "Ethereum RPC"
    description: str = ""
    transaction_hash: str | None = None
    block_number: int | None = None
    address: str | None = None
    contract_address: str | None = None
    token_address: str | None = None
    value_wei: int | None = None
    value_eth: float | None = None
    timestamp: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def new(cls, etype: str, **kwargs: Any) -> Evidence:
        if etype not in EVIDENCE_TYPES:
            raise ValueError(f"Unknown evidence type: {etype!r}")
        return cls(type=etype, **kwargs)


class EvidenceStore:
    """Ordered, thread-safe collection of evidence records."""

    def __init__(self) -> None:
        self._items: list[Evidence] = []
        self._lock: Any = None
        try:
            import threading

            self._lock = threading.RLock()
        except Exception:  # pragma: no cover - trivial fallback
            pass

    # -- mutation ----------------------------------------------------
    def add(self, evidence: Evidence) -> Evidence:
        if not evidence.id:
            evidence.id = f"EVID-{len(self._items) + 1:04d}"
        with self._lock:
            self._items.append(evidence)
        return evidence

    def add_many(self, evidence_list: list[Evidence]) -> list[Evidence]:
        return [self.add(ev) for ev in evidence_list]

    # -- queries -----------------------------------------------------
    def get(self, evidence_id: str) -> Evidence | None:
        for item in self._items:
            if item.id == evidence_id:
                return item
        return None

    def all(self) -> list[Evidence]:
        return list(self._items)

    def count(self) -> int:
        return len(self._items)

    def resolve(self, ids: list[str]) -> list[Evidence]:
        resolved: list[Evidence] = []
        for eid in ids:
            ev = self.get(eid)
            if ev is None:
                raise ValueError(f"Evidence {eid} does not exist")
            resolved.append(ev)
        return resolved

    def validate_references(self, referenced: list[str]) -> list[str]:
        """Return any referenced ids that do not exist (for validation)."""
        return [eid for eid in referenced if self.get(eid) is None]

    def to_records(self) -> list[dict[str, Any]]:
        return [ev.model_dump(mode="json") for ev in self._items]