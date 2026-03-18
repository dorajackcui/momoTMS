# ADR 0001: Product Surface And Compatibility Policy

## Status

Accepted.

## Decision

- `/app` is the only operator-facing product surface
- `/workbench` is removed and returns `410 Gone`
- `/variant-workbench` is removed and returns `410 Gone`
- runtime APIs are project-scoped and branch-oriented
- `rel/current` direct mutation stays API-only and internal-only; it is intentionally not exposed in `/app`

## Consequences

- new product UX should use project-scoped APIs only
- `/app` may use inspection APIs for read-only debugging, but should not depend on compatibility bootstrap or string-shaped routes
- branch workflow reads and writes should use `/api/projects/{project_id}/branches/...`
- branch writes should converge on generic mutation and sync routes rather than scenario-specific route names

## Historical Source Of Truth

- page routing: `app/routers/pages.py`
- product bootstrap: `app/services/project/state.py`
- inspection routes: `app/routers/inspection.py`
- internal branch write workflows: `app/routers/workflows.py`
