"""API-level tests using FastAPI TestClient with a stubbed runtime."""

from __future__ import annotations

import pytest
from app.api.dependencies import DependencyBag
from app.api.routes import health, investigate
from app.main import app
from starlette.testclient import TestClient

from tests.conftest import wait_for
from tests.fakes import EIP55


@pytest.fixture
def client(provider, settings):
    bag = DependencyBag(settings=settings, llm=None, chain="sepolia")
    from tests.fakes import make_runtime

    bag._runtime = make_runtime(provider, settings)
    app.dependency_overrides[investigate._bag] = lambda: bag
    app.dependency_overrides[health._bag] = lambda: bag
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_health_ok(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["rpc"]["connected"] is True
    assert body["rpc"]["chain"] == "sepolia"


def test_investigate_with_explicit_address(client, provider):
    provider.set_balance(EIP55, 10**18)
    resp = client.post("/api/investigate", json={"query": "Investigate this wallet", "address": EIP55})
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["status"] in ("queued", "running")  # async start can race ahead
    assert payload["investigation_id"]

    rec = wait_for(
        lambda: (lambda r: r if r["status"] in ("completed", "failed") else None)(
            client.get(f"/api/investigation/{payload['investigation_id']}").json()
        ),
        timeout_s=10.0,
    )
    assert rec["status"] == "completed", rec.get("error")
    assert rec["evidence"]
    assert rec["report"]["executive_summary"]


def test_investigate_with_address_in_query(client, provider):
    provider.set_nonce(EIP55, 3)
    resp = client.post(
        "/api/investigate",
        json={"query": f"Investigate 0x{EIP55[2:].lower()} and its contracts"},
    )
    assert resp.status_code == 200


def test_investigate_missing_address(client):
    resp = client.post("/api/investigate", json={"query": "tell me about the weather"})
    assert resp.status_code == 422


def test_investigate_invalid_address(client):
    resp = client.post("/api/investigate", json={"query": "check", "address": "0xnotvalid"})
    assert resp.status_code == 422


def test_investigation_not_found(client):
    resp = client.get("/api/investigation/nope-not-an-id")
    assert resp.status_code == 404