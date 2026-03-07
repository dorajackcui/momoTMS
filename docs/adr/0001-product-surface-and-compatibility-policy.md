# ADR 0001: Product Surface And Compatibility Policy

## Status

Accepted.

## Decision

- `/app` is the only operator-facing product surface.
- `/workbench` is removed and returns `410 Gone`.
- `/variant-workbench` remains a deprecated internal regression page.
- Default-project compatibility routes remain frozen for validation and regression only.
- Release hotfix stays API-only and internal-only; it is intentionally not exposed in `/app`.

## Consequences

- New product UX should use project-scoped APIs only.
- `/app` may use inspection APIs for read-only debugging, but should not depend on compatibility bootstrap or compatibility string routes.
- Compatibility route removal is deferred to a later phase; this ADR only fixes the runtime policy and product boundary.

## Source Of Truth

- Page routing: `app/routers/pages.py`
- Product bootstrap: `app/services/project/state.py`
- Inspection routes: `app/routers/inspection.py`
- Internal hotfix workflow: `app/routers/workflows.py`
