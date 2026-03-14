# Delivery Status (Archived)

Archived on March 14, 2026 during the documentation system refactor. Keep this file as a historical status snapshot, not as active runtime guidance.

## Current State

- `/app` is the only operator-facing product surface.
- `/variant-workbench` and `/workbench` both return `410 Gone`.
- Product bootstrap is `GET /api/projects/{project_id}/state`.
- Runtime APIs are project-scoped only.
- Branch writes are unified as scope mutation plus scope sync.
- `rel/current` direct mutation stays API-only and internal-only.
- Trash and restore are project-scoped and variant-aware.
- `/app/imports` is the operator cockpit for imports, jobs, reports, and artifacts.
- Canonical-source variant semantics are live for scope mutation, scope sync, fill, and inspection.
- `/app/inspection` is the read-only inspection surface for canonical and orphan variants plus business-key lookups.
- Retained lifecycle semantics and storage have been removed.

## Stable Outcomes

- Test isolation no longer depends on the shared `data/tms.db`.
- Project ownership and negative-path API behavior are covered by backend tests.
- Compare, queue, and master search no longer rely on full-scope in-memory hydration for normal pagination.
- Long-running jobs record stage timing in `job.summary.stages`.
- Project switching, no-project empty state, and imports/job inspection are handled in `/app`.

## Verification

- Route inventory and request/response contracts now live in [../../docs/reference/api.md](../../docs/reference/api.md).
- Local run commands, environment overrides, and validation commands now live in [../../docs/development/local-setup.md](../../docs/development/local-setup.md) and [../../docs/development/testing-and-validation.md](../../docs/development/testing-and-validation.md).
- Backend route regression is primarily covered by `tests/test_variant_api.py` and `tests/test_service_package_smoke.py`.
- Branch workflow behavior is primarily covered by `tests/test_branch_service.py` and `tests/test_io_flows.py`.
- Product flow coverage is primarily in `tests/e2e/product-app.spec.js` and `tests/e2e/product-app-empty.spec.js`.
