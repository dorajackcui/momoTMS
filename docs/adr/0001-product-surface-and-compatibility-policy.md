# ADR 0001: Product Surface And Branch API Policy

## Status

Accepted.

## Decision

- `/app` is the only operator-facing product surface.
- `/workbench` is removed and returns `410 Gone`.
- `/variant-workbench` is removed and returns `410 Gone`.
- Runtime APIs are project-scoped and branch-oriented.
- rel/current direct mutation stays API-only and internal-only; it is intentionally not exposed in `/app`.

## Consequences

- New product UX should use project-scoped APIs only.
- `/app` may use inspection APIs for read-only debugging, but should not depend on compatibility bootstrap or string-shaped routes.
- Branch workflow reads and writes should use `/api/projects/{project_id}/branches/...`.
- Branch writes should converge on generic mutation/sync routes rather than scenario-specific route names.

## Source Of Truth

- Page routing: `app/routers/pages.py`
- Product bootstrap: `app/services/project/state.py`
- Inspection routes: `app/routers/inspection.py`
- Internal branch write workflows: `app/routers/workflows.py`
