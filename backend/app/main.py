"""Argus - FastAPI entrypoint.

Serves the JSON API under /api and the static investigation dashboard
under /. Configuration is environment-driven (see .env.example).
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import health, investigate
from app.config.settings import get_settings

logging.basicConfig(
    level=get_settings().log_level.upper(),
    format="%(asctime)s %(levelname)-8s %(name)s %(message)s",
)
logger = logging.getLogger("argus")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.settings = settings
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Argus - Agentic Blockchain Intelligence",
        version=settings.version,
        description=(
            "Natural-language investigation of Ethereum wallets and contracts "
            "via a LangGraph orchestrated agent pipeline."
        ),
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(investigate.router)

    _mount_frontend(app)

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        frontend_index = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "index.html")
        if not os.path.exists(frontend_index):
            from fastapi.responses import JSONResponse

            return JSONResponse({"detail": "Frontend not built; GET /api/health instead."})
        return FileResponse(frontend_index)

    return app


def _mount_frontend(app: FastAPI) -> None:
    static_dir = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "assets")
    )
    if os.path.isdir(static_dir):
        app.mount("/assets", StaticFiles(directory=static_dir), name="assets")


app = create_app()