# 2026-03 Maintainability Repair Plan

## Purpose

- track the multi-phase maintainability repair work without turning archive notes into runtime source of truth

## Problem Areas

- request-scoped write flows were split across multiple independent SQLite commits
- `branches/mutations` could leave partially created entries, variants, bindings, or dev branch metadata after an exception
- `variants/trash/*` could leave partially removed bindings or partially restored variants after an exception
- `frontend/src/App.tsx` had become a catch-all product shell, state container, API client, and page renderer
- read-model and repository boundaries still mixed query hydration with command-oriented persistence concerns
- bootstrap and branch summary were paying avoidable query cost for release summary and candidate dev branch detail

## Phase Status


| phase | focus                                                        | owner doc                                    | validation                                                                                                                                    | status   |
| ----- | ------------------------------------------------------------ | -------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- | -------- |
| 0     | repair tracking note                                         | none; archive only                           | `.venv/bin/python scripts/validate_docs.py`                                                                                                   | complete |
| 1     | backend transaction consistency for mutation, trash, restore | [../docs/workflows.md](../docs/workflows.md) | `tests/test_branch_service.py`, `tests/test_variant_api.py`, `tests/test_variant_refactor_services.py`, `tests/test_service_package_smoke.py` | complete |
| 2     | frontend `/app` decomposition without contract changes       | [../docs/contracts.md](../docs/contracts.md) | frontend build plus `tests/e2e/product-app.spec.js`                                                                                           | complete |
| 3     | phase 3A read-model and repository boundary core slimming   | [../docs/system.md](../docs/system.md)       | `tests/test_branch_service.py`, `tests/test_variant_api.py`, `tests/test_variant_refactor_services.py`, `tests/test_service_package_smoke.py`, `.venv/bin/python scripts/validate_docs.py` | complete |


## Phase 1 Acceptance

- `BranchMutationService.apply()` runs in one DB transaction per request
- `VariantWorkflowService.delete()` runs in one DB transaction per request
- `VariantWorkflowService.restore()` runs in one DB transaction per request
- unhandled exceptions roll back the whole request, including dev branch creation, entry creation, variant writes, and binding updates
- business-result rows such as `MISSING`, `NOT_TRASHED`, or `SOURCE_CONFLICT` still return as normal report rows and do not trigger rollback by themselves

## Phase 2 Acceptance

- `frontend/src/App.tsx` is reduced to route, shared state, effects, and workflow orchestration
- product app types, route helpers, API helpers, shared widgets, and page renderers live under `frontend/src/product-app/`
- `/app` routes, project-scoped API usage, payload shapes, and existing `data-testid` hooks remain unchanged
- frontend verification includes `npm run build:app` and `tests/e2e/product-app.spec.js`

## Phase 3A Acceptance

- `app/services/variant/` exposes explicit entry, variant, and binding command or query repositories through responsibility modules and package exports, and read-side hydration no longer crosses repo private helpers
- `BranchService` is reduced to branch metadata, candidate-branch detail, and rich branch entry views instead of acting as the `/branches*` route facade
- `/api/projects/{project_id}/branches`, `/branches/compare`, `/branches/queue`, and `/branches/master/*` read directly through `ReadModelService`
- `ProjectStateService.get_state()` uses lightweight release summary plus reused active dev branch metadata instead of hydrating release entries to build bootstrap
- targeted regression keeps the demo plus one active dev branch scenario within the phase 3A query budgets: `get_state()` at or below 12 SQL statements and `branch_summary()` at or below 3

## Risks And Follow-Up

- phases 1, 2, and 3A intentionally do not change HTTP routes, payload shapes, or user-facing flow names
- phase 2 intentionally does not introduce a new frontend state library
- compare and queue still use the existing Python diff or priority logic; deeper SQL pushdown remains a possible phase 3B follow-up if those paths become the next hotspot
