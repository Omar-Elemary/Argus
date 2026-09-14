"""Auth API tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.conftest import auth_header, register


def test_register_and_me(client: TestClient) -> None:
    body = register(client)
    assert body["token_type"] == "bearer"
    assert body["user"]["email"] == "founder@example.com"
    me = client.get("/api/v1/auth/me", headers=auth_header(body["access_token"]))
    assert me.status_code == 200
    assert me.json()["full_name"] == "Ada Founder"


def test_duplicate_email(client: TestClient) -> None:
    register(client)
    again = client.post(
        "/api/v1/auth/register",
        json={"email": "founder@example.com", "password": "password12", "full_name": "Other"},
    )
    assert again.status_code == 409


def test_login_success_and_failure(client: TestClient) -> None:
    register(client, email="ada@fellows.dev")
    ok = client.post(
        "/api/v1/auth/login",
        json={"email": "ADA@fellows.dev", "password": "password12"},
    )
    assert ok.status_code == 200
    bad = client.post(
        "/api/v1/auth/login",
        json={"email": "ada@fellows.dev", "password": "wrong-password"},
    )
    assert bad.status_code == 401


def test_me_requires_auth(client: TestClient) -> None:
    assert client.get("/api/v1/auth/me").status_code == 401
