"""Pluggable LLM provider.

The agent pipeline is fully functional without an LLM: every factual
claim is computed deterministically from on-chain evidence. The LLM is
used *only* to narrate investigation results into readable prose.

Provide ``LLM_PROVIDER`` (openai/auto -> any OpenAI-compatible
endpoint, cursor -> Cursor Cloud Agents, none -> deterministic
fallback) plus the matching keys via the environment. No keys are ever
hard-coded.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Protocol

from app.config.settings import Settings

logger = logging.getLogger("argus.llm")


class LLM(Protocol):
    """Minimal interface the report/analysis agents depend on."""

    name: str

    def chat(self, *, system: str, user: str) -> str:
        ...


class OpenAICompatibleProvider:
    """Production provider - works with OpenAI, OpenRouter, vLLM, ..."""

    name = "openai-compatible"

    def __init__(self, settings: Settings) -> None:
        from openai import OpenAI  # imported lazily to keep tests light

        self.settings = settings
        self.model = settings.llm_model or "gpt-4o-mini"
        self.client: Any = OpenAI(
            api_key=settings.llm_api_key or "sk-unused",
            base_url=settings.llm_base_url or None,
            timeout=60,
        )

    def chat(self, *, system: str, user: str) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            temperature=self.settings.llm_temperature,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        content = response.choices[0].message.content
        return content or ""


class CursorCloudAgentProvider:
    """Runs the narration through Cursor's Cloud Agents API.

    Cursor exposes a Cloud Agents API (``api.cursor.com``) rather than a
    plain chat-completions endpoint. We drive it in "no-repo agent"
    mode: create an agent with the narration prompt, poll its first run
    until it finishes, and return the resulting reply. This is a real
    LLM-backed narrative produced by a real cloud agent.

    Configure with ``LLM_PROVIDER=cursor`` plus ``CURSOR_API_KEY``.
    """

    name = "cursor-cloud-agent"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.base_url = (settings.cursor_base_url or "https://api.cursor.com/v1").rstrip("/")
        self.api_key = settings.cursor_api_key
        self.model = settings.llm_model or None

    def chat(self, *, system: str, user: str) -> str:
        import time

        import httpx

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        body: dict[str, Any] = {"prompt": {"text": f"{system}\n\n{user}"}}
        if self.model:
            body["model"] = {"id": self.model}

        with httpx.Client(timeout=90) as client:
            create = client.post(f"{self.base_url}/agents", json=body, headers=headers)
            create.raise_for_status()
            payload = create.json()
            agent_id = payload["agent"]["id"]
            run_id = payload["run"]["id"]

            deadline = time.monotonic() + 240
            while time.monotonic() < deadline:
                time.sleep(3)
                run = client.get(
                    f"{self.base_url}/agents/{agent_id}/runs/{run_id}",
                    headers=headers,
                )
                run.raise_for_status()
                status = run.json().get("status")
                if status == "FINISHED":
                    return run.json().get("result") or ""
                if status in ("ERROR", "CANCELLED", "EXPIRED"):
                    raise RuntimeError(f"Cursor agent run ended with status {status}")
            raise TimeoutError("Cursor cloud agent run did not finish in time")


class DeterministicFallbackProvider:
    """No-LLM fallback used for tests and demos without an API key.

    It reads the structured ``DATA:`` JSON that the agents pass in and
    emits a concise, factual summary - deterministic and repeatable.
    This is a graceful degradation, not a "fake model".
    """

    name = "deterministic-fallback"

    def chat(self, *, system: str, user: str) -> str:
        data = _extract_json(user)
        if data is None:
            return "No structured context was supplied."
        return _summarise(data)


def _extract_json(user: str) -> Any:
    marker = "DATA:"
    start = user.find(marker)
    if start < 0:
        return None
    payload = user[start + len(marker) :].strip()
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        return None


def _summarise(data: Any) -> str:
    if not isinstance(data, dict):
        return "Investigation completed with structured evidence."
    parts: list[str] = []
    if data.get("subject"):
        parts.append(f"Investigation subject: {data['subject']}")
    if data.get("tx_count") is not None:
        parts.append(
            f"Observed {data['tx_count']} transactions across a {data.get('window_blocks', 'bounded')}-block window."
        )
    if data.get("balance_eth") is not None:
        parts.append(f"Current ETH balance is {data['balance_eth']:.4f}.")
    if data.get("total_in_eth") is not None:
        parts.append(f"Approx. ETH inflow {data['total_in_eth']:.4f} and outflow {data.get('total_out_eth', 0.0):.4f}.")
    findings = data.get("findings", [])
    if findings:
        parts.append(f"{len(findings)} evidence-linked finding(s) were recorded.")
        for finding in findings[:3]:
            refs = finding.get("evidence_count", len(finding.get("evidence_ids", [])))
            parts.append(
                f"- [{finding.get('severity', 'informational')}] {finding.get('title', '')} ({refs} evidence references)."
            )
    return "\n".join(parts)


def build_llm(settings: Settings) -> LLM | None:
    """Resolve the configured LLM backend. Returns None if none matched."""
    provider = settings.llm_provider.lower()
    if provider == "none":
        logger.info("Using deterministic fallback LLM (LLM_PROVIDER=none).")
        return DeterministicFallbackProvider()
    if provider in ("auto", "openai"):
        if settings.llm_api_key:
            logger.info("Using OpenAI-compatible LLM (model=%s).", settings.llm_model)
            return OpenAICompatibleProvider(settings)
        if settings.cursor_api_key:
            logger.info("Using Cursor Cloud Agents LLM (model=%s).", settings.llm_model)
            return CursorCloudAgentProvider(settings)
        if provider == "openai":
            logger.warning("LLM_PROVIDER=openai but LLM_API_KEY is empty.")
        logger.info("LLM not configured; falling back to deterministic narratives.")
        return DeterministicFallbackProvider()
    if provider == "cursor":
        if settings.cursor_api_key:
            logger.info("Using Cursor Cloud Agents LLM (model=%s).", settings.llm_model)
            return CursorCloudAgentProvider(settings)
        logger.warning("LLM_PROVIDER=cursor but CURSOR_API_KEY is empty.")
        return DeterministicFallbackProvider()
    logger.warning("Unknown LLM_PROVIDER=%r; using deterministic fallback.", provider)
    return DeterministicFallbackProvider()


__all__ = [
    "LLM",
    "OpenAICompatibleProvider",
    "CursorCloudAgentProvider",
    "DeterministicFallbackProvider",
    "build_llm",
]