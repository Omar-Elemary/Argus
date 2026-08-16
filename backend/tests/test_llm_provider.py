"""Tests for the Cursor Cloud Agents LLM provider (mocked HTTP)."""

from __future__ import annotations

from unittest import mock

from app.config.settings import build_settings
from app.services.llm.llm_provider import CursorCloudAgentProvider, build_llm


def _cursor_settings(**overrides):
    return build_settings(
        llm_provider="cursor",
        cursor_api_key="crsr_testkey",
        **overrides,
    )


class _FakeRun:
    def __init__(self, responses: list[dict]):
        self._responses = responses
        self._calls = 0

    def json(self):
        resp = self._responses[min(self._calls, len(self._responses) - 1)]
        self._calls += 1
        return resp

    def raise_for_status(self):
        pass


def test_cursor_provider_returns_finished_result():
    settings = _cursor_settings()
    provider = CursorCloudAgentProvider(settings)
    assert provider.name == "cursor-cloud-agent"

    client = mock.Mock()
    client.__enter__ = mock.Mock(return_value=client)
    client.__exit__ = mock.Mock(return_value=False)
    client.post.return_value = _FakeRun(
        [{"agent": {"id": "bc-1"}, "run": {"id": "run-1", "status": "CREATING"}}]
    )
    client.get.return_value = _FakeRun(
        [
            {"id": "run-1", "status": "RUNNING"},
            {"id": "run-1", "status": "FINISHED", "result": "Narrated summary."},
        ]
    )

    with mock.patch("time.sleep"):
        with mock.patch("httpx.Client", return_value=client):
            out = provider.chat(system="sys", user="user")
    assert out == "Narrated summary."

    _, kwargs = client.post.call_args
    body = kwargs["json"]
    assert body["prompt"]["text"].startswith("sys")
    assert "user" in body["prompt"]["text"]
    assert "model" not in body


def test_cursor_provider_passes_model_id_when_configured():
    settings = _cursor_settings(llm_model="composer-2")
    provider = CursorCloudAgentProvider(settings)

    client = mock.Mock()
    client.__enter__ = mock.Mock(return_value=client)
    client.__exit__ = mock.Mock(return_value=False)
    client.post.return_value = _FakeRun([{"agent": {"id": "bc-1"}, "run": {"id": "run-1"}}])
    client.get.return_value = _FakeRun(
        [{"id": "run-1", "status": "FINISHED", "result": "ok"}]
    )

    with mock.patch("time.sleep"):
        with mock.patch("httpx.Client", return_value=client):
            provider.chat(system="s", user="u")
    _, kwargs = client.post.call_args
    assert kwargs["json"]["model"] == {"id": "composer-2"}


def test_cursor_provider_raises_on_agent_error():
    settings = _cursor_settings()
    provider = CursorCloudAgentProvider(settings)

    client = mock.Mock()
    client.__enter__ = mock.Mock(return_value=client)
    client.__exit__ = mock.Mock(return_value=False)
    client.post.return_value = _FakeRun([{"agent": {"id": "bc-1"}, "run": {"id": "run-1"}}])
    client.get.return_value = _FakeRun(
        [{"id": "run-1", "status": "ERROR", "result": "boom"}]
    )

    import pytest

    with mock.patch("time.sleep"):
        with mock.patch("httpx.Client", return_value=client):
            with pytest.raises(RuntimeError, match="ERROR"):
                provider.chat(system="s", user="u")


def test_build_llm_selects_cursor_when_configured():
    llm = build_llm(_cursor_settings())
    assert isinstance(llm, CursorCloudAgentProvider)


def test_build_llm_falls_back_without_cursor_key():
    llm = build_llm(build_settings(llm_provider="cursor", cursor_api_key=""))
    from app.services.llm.llm_provider import DeterministicFallbackProvider

    assert isinstance(llm, DeterministicFallbackProvider)


def test_build_llm_auto_prefers_cursor_when_no_openai_key():
    llm = build_llm(
        build_settings(llm_provider="auto", cursor_api_key="crsr_testkey")
    )
    assert isinstance(llm, CursorCloudAgentProvider)