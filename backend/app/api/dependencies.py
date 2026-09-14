"""FastAPI dependencies: settings, current user, LLM (reused protocol)."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import Settings
from app.db.session import get_db
from app.models.user import User
from app.security.tokens import TokenError, decode_access_token
from app.services import auth_service
from app.services.llm.llm_provider import LLM, build_llm

bearer_scheme = HTTPBearer(auto_error=False)


def get_settings_dep(request: Request) -> Settings:
    return request.app.state.settings


@dataclass
class DependencyBag:
    """Kept from Argus: a small bag of process-wide services (LLM, settings)."""

    settings: Settings
    llm: LLM | None = None

    @classmethod
    def build(cls, settings: Settings) -> DependencyBag:
        return cls(settings=settings, llm=build_llm(settings))


def get_bag(request: Request) -> DependencyBag:
    return request.app.state.bag


async def get_current_user(
    request: Request,
    session: AsyncSession = Depends(get_db),
    creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> User:
    if creds is None or creds.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated.")
    settings: Settings = request.app.state.settings
    try:
        user_id = decode_access_token(creds.credentials, settings)
    except TokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token."
        ) from exc
    user = await auth_service.get_user_by_id(session, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found.")
    return user
