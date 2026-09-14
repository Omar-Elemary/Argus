# ADR 002 — Multi-tenant isolation

## Status

Accepted

## Decision

Authorization is enforced in backend services. A user may access a company only with a `company_memberships` row. Cross-tenant access returns 404. Future agent/task/memory/file/key tables include `company_id` and the same predicate.

## Consequences

- Frontend hiding is not a security control.
- Every new resource type must be company-scoped in the same way.
