"""Company API and tenant isolation."""

from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

from tests.conftest import auth_header, register


def _create_company(client: TestClient, token: str, name: str = "Acme AI") -> dict:
    response = client.post(
        "/api/v1/companies",
        headers=auth_header(token),
        json={
            "name": name,
            "description": "AI productivity software",
            "mission": "Build useful AI tools for small businesses.",
            "industry": "Technology",
            "settings": {"timezone": "Africa/Cairo"},
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_create_list_and_overview(client: TestClient) -> None:
    token = register(client)["access_token"]
    company = _create_company(client, token)
    assert company["name"] == "Acme AI"
    assert company["mission"].startswith("Build useful")
    assert company["role"] == "owner"
    assert company["settings"]["timezone"] == "Africa/Cairo"

    listed = client.get("/api/v1/companies", headers=auth_header(token))
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    overview = client.get(
        f"/api/v1/companies/{company['id']}/overview", headers=auth_header(token)
    )
    assert overview.status_code == 200
    body = overview.json()
    assert body["company"]["id"] == company["id"]
    assert len(body["members"]) == 1
    assert body["members"][0]["role"] == "owner"
    assert body["recent_events"][0]["event_type"] == "COMPANY_CREATED"


def test_update_company(client: TestClient) -> None:
    token = register(client)["access_token"]
    company = _create_company(client, token)
    patched = client.patch(
        f"/api/v1/companies/{company['id']}",
        headers=auth_header(token),
        json={"industry": "SaaS"},
    )
    assert patched.status_code == 200
    assert patched.json()["industry"] == "SaaS"


def test_cannot_read_another_users_company(client: TestClient) -> None:
    owner = register(client, email="owner@example.com")
    company = _create_company(client, owner["access_token"], name="Owner Co")
    other = register(client, email="intruder@example.com", full_name="Intruder")
    hidden = client.get(
        f"/api/v1/companies/{company['id']}",
        headers=auth_header(other["access_token"]),
    )
    assert hidden.status_code == 404
    listed = client.get("/api/v1/companies", headers=auth_header(other["access_token"]))
    assert listed.json() == []
    overview = client.get(
        f"/api/v1/companies/{company['id']}/overview",
        headers=auth_header(other["access_token"]),
    )
    assert overview.status_code == 404
    patched = client.patch(
        f"/api/v1/companies/{company['id']}",
        headers=auth_header(other["access_token"]),
        json={"name": "Hijacked"},
    )
    assert patched.status_code == 404


def test_unknown_company_is_404(client: TestClient) -> None:
    token = register(client)["access_token"]
    response = client.get(f"/api/v1/companies/{uuid4()}", headers=auth_header(token))
    assert response.status_code == 404


def test_health(client: TestClient) -> None:
    health = client.get("/api/v1/health")
    assert health.status_code == 200
    assert health.json()["app"] == "fellows"
    ready = client.get("/api/v1/health/ready")
    assert ready.status_code == 200
    assert ready.json()["status"] == "ready"
