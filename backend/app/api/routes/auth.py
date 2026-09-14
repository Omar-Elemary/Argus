"""Auth routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_settings_dep
from app.config.settings import Settings
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserPublic
from app.services.auth_service import AuthError, login_user, register_user

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def _raise(exc: AuthError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.post("/register", response_model=TokenResponse)
async def register(
    payload: RegisterRequest,
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
) -> TokenResponse:
    try:
        return await register_user(session, payload, settings)
    except AuthError as exc:
        _raise(exc)
        raise  # pragma: no cover


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
) -> TokenResponse:
    try:
        return await login_user(session, payload, settings)
    except AuthError as exc:
        _raise(exc)
        raise  # pragma: no cover


@router.post("/logout")
async def logout() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/me", response_model=UserPublic)
async def me(user: User = Depends(get_current_user)) -> UserPublic:
    return UserPublic.model_validate(user)
