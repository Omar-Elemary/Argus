"""Auth service: register, authenticate, issue tokens."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import Settings
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserPublic
from app.security.passwords import hash_password, verify_password
from app.security.tokens import create_access_token


class AuthError(Exception):
    def __init__(self, detail: str, status_code: int = 400) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _token_response(user: User, settings: Settings) -> TokenResponse:
    return TokenResponse(
        access_token=create_access_token(user.id, settings),
        user=UserPublic.model_validate(user),
    )


async def register_user(
    session: AsyncSession, payload: RegisterRequest, settings: Settings
) -> TokenResponse:
    user = User(
        email=_normalize_email(str(payload.email)),
        password_hash=hash_password(payload.password),
        full_name=payload.full_name.strip(),
    )
    session.add(user)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise AuthError("An account with this email already exists.", 409) from exc
    await session.refresh(user)
    return _token_response(user, settings)


async def login_user(
    session: AsyncSession, payload: LoginRequest, settings: Settings
) -> TokenResponse:
    email = _normalize_email(str(payload.email))
    result = await session.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise AuthError("Invalid email or password.", 401)
    return _token_response(user, settings)


async def get_user_by_id(session: AsyncSession, user_id) -> User | None:
    result = await session.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()
