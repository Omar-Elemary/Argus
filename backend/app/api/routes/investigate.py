"""API route schemas and handlers."""

from __future__ import annotations

import re
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.dependencies import DependencyBag
from app.blockchain.validators import ValidationError, validate_eth_address

router = APIRouter(prefix="/api", tags=["investigation"])


def _bag() -> DependencyBag:
    from app.api.dependencies import build_bag

    return build_bag()


BagDep = Annotated[DependencyBag, Depends(_bag)]

_ADDRESS_IN_QUERY = re.compile(r"\b0x[a-fA-F0-9]{40}\b")


class InvestigateRequest(BaseModel):
    query: str = Field(..., min_length=3, description="Natural-language investigation request")
    address: str | None = Field(
        None, description="Ethereum address to investigate (optional if embedded in query)"
    )


class InvestigateStart(BaseModel):
    investigation_id: str
    status: str


@router.post("/investigate", summary="Start an investigation")
def investigate(
    request: InvestigateRequest,
    bag: BagDep,
) -> dict[str, Any]:
    address = request.address or _extract_address(request.query)
    if not address:
        raise HTTPException(
            status_code=422,
            detail="No address found; provide 'address' in the body or include 0x... in the query.",
        )
    try:
        address = validate_eth_address(address)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None

    try:
        service = bag.get_service()
    except Exception as exc:  # noqa: BLE001
        detail = bag.runtime_last_error() or str(exc)
        raise HTTPException(
            status_code=503,
            detail=f"Blockchain runtime unavailable: {detail}",
        ) from exc

    record = service.start(request.query, address)
    # Make this new investigation discoverable across requests by placing
    # it in a small module-scoped registry. This avoids race conditions
    # when the dependency bag is recreated per-request in some dev setups.
    try:
        _GLOBAL_INVESTIGATIONS[record.id] = record
    except NameError:
        _GLOBAL_INVESTIGATIONS: dict[str, "InvestigationRecord"] = {record.id: record}  # type: ignore[name-defined]
    # Return the public record so callers don't have to poll immediately.
    return record.public()


@router.get("/investigation/{investigation_id}", summary="Poll an investigation's current state")
def get_investigation(
    investigation_id: str,
    bag: BagDep,
) -> dict[str, Any]:
    # Prefer the module-scoped registry if present (ensures visibility
    # when services are created per-request). Fall back to the bag-local
    # service storage when necessary.
    record = None
    try:
        record = _GLOBAL_INVESTIGATIONS.get(investigation_id)  # type: ignore[name-defined]
    except NameError:
        pass
    if record is None:
        record = bag.get_service().get(investigation_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Investigation not found")
    return record.public()


def _extract_address(query: str) -> str | None:
    match = _ADDRESS_IN_QUERY.search(query or "")
    return match.group(0) if match else None