"""Shared pytest fixtures - hermetic, no live RPC required."""

from __future__ import annotations

import pytest
from app.config.settings import build_settings
from app.models.evidence import EvidenceStore
from app.tools.specs import ToolExecutor

from tests.fakes import StubBlockchainProvider, make_runtime


@pytest.fixture
def settings() -> object:
    return build_settings(
        eth_rpc_url="http://test-node.invalid/",
        eth_network="sepolia",
        eth_chain_id=11155111,
        llm_provider="none",
        max_transactions=5,
        max_blocks_scan=100,
        max_iterations=3,
        max_tool_calls=30,
        large_tx_threshold_eth=1.0,
        repeated_counterparty_min=2,
    )


@pytest.fixture
def provider() -> StubBlockchainProvider:
    return StubBlockchainProvider(latest_block=5000)


@pytest.fixture
def runtime(provider, settings):
    return make_runtime(provider, settings)


@pytest.fixture
def evidence_store() -> EvidenceStore:
    return EvidenceStore()


@pytest.fixture
def executor(runtime, evidence_store) -> ToolExecutor:
    return ToolExecutor(runtime, evidence_store)


def wait_for(topredicate, timeout_s: float = 10.0):
    """Poll until predicate(item) is truthy or timeout."""
    import time

    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        value = topredicate()
        if value:
            return value
        time.sleep(0.05)
    raise TimeoutError("condition not met before timeout")