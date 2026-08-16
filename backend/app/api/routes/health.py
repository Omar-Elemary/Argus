"""Health endpoint - reports API status and RPC connectivity."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from app.api.dependencies import DependencyBag

router = APIRouter(prefix="/api", tags=["health"])


def _bag() -> DependencyBag:
    from app.api.dependencies import build_bag

    return build_bag()


BagDep = Annotated[DependencyBag, Depends(_bag)]


@router.get("/health", summary="Service health")
def health(bag: BagDep) -> dict[str, Any]:
    rpc_connected = False
    chain = bag.settings.eth_network
    provider = "n/a"
    error = bag.runtime_last_error()
    try:
        runtime = bag.get_runtime()
        rpc_connected = True
        provider = runtime.indexer.name()
    except Exception:  # noqa: BLE001
        pass
    return {
        "status": "ok",
        "version": bag.settings.version,
        "app": bag.settings.app_name,
        "env": bag.settings.env,
        "llm_provider": getattr(bag.llm, "name", "none"),
        "rpc": {
            "connected": rpc_connected,
            "chain": chain,
            "indexer": provider,
            "error": error,
        },
    }