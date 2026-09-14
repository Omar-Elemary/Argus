# ADR 004 — Office is a projection

## Status

Accepted

## Decision

`OfficeState` is computed from activity events and agent/task rows (`project_office_state`). Character animation maps from backend status. The office never writes business records.

## Consequences

- Phase 1 ships the Pydantic model and a pure projector with tests.
- React Three Fiber is added in Phase 6 as a renderer of that model.
