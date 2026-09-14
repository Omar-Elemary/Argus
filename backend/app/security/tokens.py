"""JWT access tokens."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt

from app.config.settings import Settings


class TokenError(Exception):
    pass


def create_access_token(user_id: UUID, settings: Settings) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str, settings: Settings) -> UUID:
    try:
        payload = jwt.decode(
            token, settings.secret_key, algorithms=[settings.jwt_algorithm]
        )
        sub = payload.get("sub")
        if not sub:
            raise TokenError("Token is missing subject.")
        return UUID(str(sub))
    except (jwt.PyJWTError, ValueError) as exc:
        raise TokenError("Invalid or expired token.") from exc
