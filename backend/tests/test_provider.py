"""Tests for the RPC reliability machinery (retries, timeouts, rate limit)."""

from threading import Lock

import pytest
from app.blockchain.provider import EthereumNodeProvider, RpcError
from web3.exceptions import Web3Exception


def _build_provider(settings):
    provider = EthereumNodeProvider.__new__(EthereumNodeProvider)
    provider.settings = settings
    provider._min_interval = settings.rpc_min_interval_ms / 1000.0
    provider._last_call = 0.0
    provider._rate_lock = Lock()
    return provider


def test_retries_then_raises(settings):
    s = settings.model_copy(update={"rpc_retries": 2, "rpc_retry_backoff": 0.01, "rpc_min_interval_ms": 0})
    provider = _build_provider(s)
    attempts = []

    def flaky():
        attempts.append(1)
        raise Web3Exception("node exploded")

    with pytest.raises(RpcError, match="after 3 attempts"):
        provider._call(flaky)
    assert len(attempts) == 3


def test_success_does_not_retry(settings):
    s = settings.model_copy(update={"rpc_retries": 3, "rpc_retry_backoff": 0.01, "rpc_min_interval_ms": 0})
    provider = _build_provider(s)
    attempts = []

    def works():
        attempts.append(1)
        return 42

    assert provider._call(works) == 42
    assert len(attempts) == 1


def test_rate_limit_enforces_min_interval(settings):
    s = settings.model_copy(update={"rpc_retries": 0, "rpc_min_interval_ms": 200})
    provider = _build_provider(s)
    import time

    def echo():
        return time.monotonic()

    first = provider._call(echo)
    second = provider._call(echo)
    assert (second - first) >= 0.18  # a little slack for scheduling


def test_unknown_rpc_values_convert_to_typed_tx(settings):
    # exercises _call path conversions without touching a real node
    s = settings.model_copy(update={"rpc_retries": 0, "rpc_min_interval_ms": 0})
    provider = _build_provider(s)
    provider._convert_tx(_FakeTx())


class _FakeTx:
    hash = bytes.fromhex("aa" * 32)
    nonce = 3
    blockNumber = 1234
    gas = 21000
    value = 2 * 10**18
    input = b"\x12\x34"
    gasPrice = 20 * 10**9

    def __getitem__(self, item):
        if item == "from":
            return "0x0000000000000000000000000000000000000001"
        raise KeyError(item)

    to = None  # contract creation


def test_contract_creation_flag(settings):
    s = settings.model_copy(update={"rpc_retries": 0, "rpc_min_interval_ms": 0})
    provider = _build_provider(s)
    tx = provider._convert_tx(_FakeTx())
    assert tx.is_contract_creation is True
    assert tx.value_eth == 2.0
    assert tx.to_address is None