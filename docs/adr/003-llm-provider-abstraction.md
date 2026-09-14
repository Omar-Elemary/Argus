# ADR 003 — LLM provider abstraction

## Status

Accepted

## Decision

Domain and orchestration code depend on an `LLM` protocol. Vendor SDKs stay behind `OpenAICompatibleProvider`, `CursorCloudAgentProvider`, and future Anthropic/Gemini/local adapters. Configuration is environment-driven. A deterministic fallback exists for tests; it must not be presented as an AI employee doing work.

## Consequences

- Phase 4 agent execution fails closed if no real provider is configured.
- Per-agent `provider` / `model` fields can route without rewriting graphs.
