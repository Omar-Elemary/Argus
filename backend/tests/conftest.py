"""pytest fixtures for Fellows Phase 1."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from app.config.settings import build_settings
from app.main import create_app
from fastapi.testclient import TestClient


@pytest.fixture
def client() -> Iterator[TestClient]:
    settings = build_settings(
        database_url="sqlite+aiosqlite:///:memory:",
        secret_key="test-secret-key-for-jwt-please-change",
        cors_origins="http://localhost:3000",
        llm_provider="none",
        env="test",
    )
    app = create_app(settings)
    with TestClient(app) as test_client:
        yield test_client


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def register(
    client: TestClient,
    email: str = "founder@example.com",
    password: str = "password12",
    full_name: str = "Ada Founder",
) -> dict:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": full_name},
    )
    assert response.status_code == 200, response.text
    return response.json()
