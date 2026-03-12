# Delivery Status

This file no longer tracks an active backlog. The previous phased cleanup plan is complete.

Use this page as a short status snapshot of the runtime that remains after the refactor and product convergence work.

## Current State

- `/app` is the only operator-facing product surface.
- `/variant-workbench` and `/workbench` both return `410 Gone`.
- Product bootstrap is `GET /api/projects/{project_id}/state`.
- Runtime APIs are project-scoped only.
- Branch writes are unified as scope mutation plus scope sync.
- rel/current direct mutation stays API-only and internal-only.
- Trash and restore are project-scoped and variant-aware.
- `/app/imports` is the operator cockpit for imports, jobs, reports, and artifacts.
- Canonical-source variant semantics are live for scope mutation, scope sync, fill, and inspection.
- `/app/inspection` is the read-only inspection surface for canonical/orphan variants and business-key lookups.
- Retained lifecycle semantics and storage have been removed.

## Stable Outcomes

- Test isolation no longer depends on the shared `data/tms.db`.
- Project ownership and negative-path API behavior are covered by backend tests.
- Compare, queue, and master search no longer rely on full-scope in-memory hydration for normal pagination.
- Long-running jobs record stage timing in `job.summary.stages`.
- Project switching, no-project empty state, and imports/job inspection are handled in `/app`.

## Runtime Surface

- `/api/projects/{project_id}/branches`
- `/api/projects/{project_id}/branches/compare`
- `/api/projects/{project_id}/branches/mutations`
- `/api/projects/{project_id}/branches/sync/execute`
- `/api/projects/{project_id}/imports/...`
- `/api/projects/{project_id}/jobs/...`

## Source Docs

- Runtime overview: [../context/overview.md](../context/overview.md)
- API surface: [../runtime/api-surface.md](../runtime/api-surface.md)
- Frontend surface: [../runtime/frontend.md](../runtime/frontend.md)
- Product bootstrap contract: [../runtime/product-bootstrap.md](../runtime/product-bootstrap.md)
- Compatibility policy ADR: [../adr/0001-product-surface-and-compatibility-policy.md](../adr/0001-product-surface-and-compatibility-policy.md)
