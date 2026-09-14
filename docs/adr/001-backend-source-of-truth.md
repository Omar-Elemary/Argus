# ADR 001 — Backend is the source of truth

## Status

Accepted

## Decision

Company, agent, task, memory, approval, and activity state are owned by the FastAPI backend and PostgreSQL. The Next.js UI and the 3D office are projections of that state.

## Consequences

- 3D components must not create or infer work.
- Real-time UI reduces typed `ActivityEvent` records.
- Tests assert API/DB facts, not canvas animations.
