"""Health and readiness."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from sqlalchemy import text

router = APIRouter(prefix="/api/v1", tags=["health"])


@router.get("/health", summary="Service health")
def health(request: Request) -> dict[str, Any]:
    settings = request.app.state.settings
    bag = request.app.state.bag
    return {
        "status": "ok",
        "version": settings.version,
        "app": settings.app_name,
        "env": settings.env,
        "llm_provider": getattr(bag.llm, "name", "none"),
        "phase": 1,
    }


@router.get("/health/ready", summary="Readiness (database)")
async def ready(request: Request) -> dict[str, Any]:
    factory = request.app.state.session_factory
    async with factory() as session:
        await session.execute(text("SELECT 1"))
    return {"status": "ready"}
