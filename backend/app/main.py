"""Fellows — FastAPI entrypoint.

Serves the JSON API under /api/v1. Configuration is environment-driven.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.dependencies import DependencyBag
from app.api.routes import auth, companies, health
from app.config.settings import Settings, get_settings
from app.db.base import Base
from app.db.session import create_engine_from_url, session_factory

# Import models so metadata is complete before create_all.
from app.models import company as _company  # noqa: F401
from app.models import event as _event  # noqa: F401
from app.models import user as _user  # noqa: F401

logger = logging.getLogger("fellows")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings: Settings = app.state.settings
    engine = create_engine_from_url(settings.database_url)
    app.state.engine = engine
    app.state.session_factory = session_factory(engine)
    app.state.bag = DependencyBag.build(settings)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Fellows API ready (env=%s)", settings.env)
    yield
    await engine.dispose()


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    logging.basicConfig(
        level=settings.log_level.upper(),
        format="%(asctime)s %(levelname)-8s %(name)s %(message)s",
    )
    app = FastAPI(
        title="Fellows",
        version=settings.version,
        description="AI company operating system — Phase 1 foundation.",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(companies.router)
    return app


app = create_app()
