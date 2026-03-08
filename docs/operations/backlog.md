# Delivery Status

This file no longer tracks an active backlog. The previous phased cleanup plan is complete.

Use this page as a short status snapshot of the runtime that remains after the refactor and product convergence work.

## Current State

- `/app` is the only operator-facing product surface.
- `/variant-workbench` remains available only as a deprecated internal regression page.
- `GET /workbench` returns `410 Gone`.
- Product bootstrap is `GET /api/projects/{project_id}/state`.
- `GET /api/state` and other default-project routes remain frozen as compatibility-only surfaces for project `1`.
- Hotfix stays API-only and internal-only.
- Trash and restore are project-scoped and variant-aware.
- `/app/imports` is the operator cockpit for imports, jobs, reports, and artifacts.
- Canonical-source variant semantics are live for dev import, rel hotfix, promote, fill, and inspection.
- `/app/inspection` is the read-only inspection surface for canonical/orphan variants and business-key lookups.
- Retained lifecycle semantics and storage have been removed.

## Stable Outcomes

- Test isolation no longer depends on the shared `data/tms.db`.
- Project ownership and negative-path API behavior are covered by backend tests.
- Compare, queue, and master search no longer rely on full-scope in-memory hydration for normal pagination.
- Long-running jobs record stage timing in `job.summary.stages`.
- Project switching, no-project empty state, and imports/job inspection are handled in `/app`.

## Compatibility Route Policy

Compatibility routes are frozen, not expanded.

Kept temporarily:

- `/api/state`
- `/api/demo/reset`
- `/api/strings`
- `/api/strings/{business_key}`
- `/api/imports/...`
- `/api/jobs/...`
- `/api/dev-versions...`
- `/api/scopes/...`
- `/api/translation-queue`
- `/api/master/...`
- `/api/promote/...`
- `/api/fill...`
- `/api/qa...`

Removed from the live API:

- `/api/rel/hotfix/active`
- `/api/rel/hotfix/passive`
- `/api/trash/delete`
- `/api/trash/restore`

## Source Docs

- Runtime overview: [../context/overview.md](../context/overview.md)
- API surface: [../runtime/api-surface.md](../runtime/api-surface.md)
- Frontend surface: [../runtime/frontend.md](../runtime/frontend.md)
- Product bootstrap contract: [../runtime/product-bootstrap.md](../runtime/product-bootstrap.md)
- Compatibility policy ADR: [../adr/0001-product-surface-and-compatibility-policy.md](../adr/0001-product-surface-and-compatibility-policy.md)
