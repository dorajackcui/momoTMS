# Phase 5.5: Legacy Naming Cleanup

## Purpose

Clean up legacy `scope`-based naming that remains in operator-facing and service-layer surfaces, while the underlying domain model and internal binding machinery retain `scope` terminology by design.

This cleanup sits between Phase 5 (Preview System) and Phase 6 (Branch-To-Branch Operations). Doing it now preserves traceability: the boundary between "intentionally kept scope" and "legacy remnant" is still clear. After Phases 6-8 add more code on top of these APIs, that boundary blurs and Phase 9 convergence becomes harder.

## Scope

Pure renames only. No semantic changes, no behavior changes, no new features.

## Rename Boundary

Three layers exist in the binding subsystem:

1. **Internal store / repository** (`_ScopeBindingStore`, `ScopeBindingCommandRepository`) — directly operate on the `scope_bindings` table. **Not renamed.** These are internal implementation; their `scope` naming reflects the table they manage.
2. **Service layer** (`BindingCommandService`) — the public API that branch services call. **Renamed.**
3. **Composition layer** (`VariantStateCoordinator`) — composes binding + lifecycle. Also called by branch services. **Renamed.**

## Rename Inventory

### Frontend

| File | Current | New |
|------|---------|-----|
| `frontend/src/shared/api/queryKeys.ts` | `invalidateProjectScope()` | `invalidateProject()` |
| `frontend/src/shared/api/queryKeys.ts` | `queryKeys.scopeRows()` | `queryKeys.branchRows()` |
| `frontend/src/shared/api/queryKeys.ts` | `queryKeys.scopeLookup()` | `queryKeys.branchLookup()` |
| `frontend/src/shared/api/queryKeys.ts` | cache key strings `"scope-rows"`, `"scope-lookup"` | `"branch-rows"`, `"branch-lookup"` |
| `frontend/src/app/shell/AppShell.tsx` | hint: `"Scope catalog, lookup, apply, replace, and trash flows."` | `"Branch catalog, lookup, apply, replace, and trash flows."` |
| `frontend/src/pages/branches/BranchOpsPage.tsx` | `scopeRowsQuery` variable | `branchRowsQuery` |
| All pages importing `invalidateProjectScope` | import + call sites | follow rename to `invalidateProject` |

Frontend call sites for `invalidateProjectScope`: `VariantDrawer.tsx`, `BranchOpsPage.tsx`, `IntakePage.tsx`, `RunsPage.tsx`, `VariantsPage.tsx`.

### Schema + Router

| File | Current | New |
|------|---------|-----|
| `app/schemas.py` | `class ScopedTrashDeleteRequest` | `class BranchTrashDeleteRequest` |
| `app/routers/workflows.py` | import and usage of `ScopedTrashDeleteRequest` | `BranchTrashDeleteRequest` |

### BindingCommandService (`app/services/variant/bindings.py`)

| Current | New | Callers |
|---------|-----|---------|
| `bind_scope()` | `bind()` | bootstrap.py, direct_mutation.py, import_batch_mutation.py, demo/service.py, state_coordinator.py |
| `clear_scope_bindings()` | `clear_bindings()` | replace.py, state_coordinator.py |
| `remove_scope_binding_rows()` | `remove_binding_rows()` | replace.py, state_coordinator.py |
| `remove_scope_bindings()` | `remove_bindings()` | state_coordinator.py |

### VariantStateCoordinator (`app/services/variant/state_coordinator.py`)

| Current | New | Callers |
|---------|-----|---------|
| `bind_scope()` | `bind()` | (internal delegation only — but tests call through it) |
| `remove_scope_bindings()` | `remove_bindings()` | tests |

### BranchReplaceService (`app/services/branch/replace.py`)

| Current | New |
|---------|-----|
| `_cleanup_scope_bindings()` | `_cleanup_bindings()` |

### PivotReviewService (`app/services/workflows/pivot_review.py`)

| Current | New |
|---------|-----|
| `_variant_visible_in_scope()` | `_variant_visible_in_branch()` |
| `"not_visible_in_scope_count"` summary key | `"not_visible_in_branch_count"` |

### Tests

All test files follow method renames mechanically:

| File | Approximate call sites |
|------|----------------------|
| `tests/test_branch_service.py` | ~25 `bind_scope` calls, 2 `remove_scope_binding*` references |
| `tests/test_io_flows.py` | ~5 `bind_scope` calls |
| `tests/test_variant_api.py` | ~6 `bind_scope` calls |
| `tests/test_variant_refactor_services.py` | ~2 `bind_scope` calls |
| `tests/test_variant_pivot.py` | ~1 `bind_scope` call |

## Explicitly Not Renamed

These items remain as-is because they are internal implementation or have a different design timeline:

| Item | Reason |
|------|--------|
| `_ScopeBindingStore` class and its methods | Internal; directly operates on `scope_bindings` table |
| `ScopeBindingCommandRepository` class and its methods | Internal; repository layer for `scope_bindings` table |
| `ScopeBindingQueryRepository` class and its methods | Internal; query layer for `scope_bindings` table |
| `BindingCommandService.clear_scope()` | Internal; wraps repository `clear_scope()`, not operator-facing |
| `VariantStateCoordinator.clear_scope()` | Only called by `trash_restore.py` internally |
| `scope_bindings` table name | Database schema; rename would require migration |
| `ScopeSelector`, `ScopeMembershipDataset` | Internal read-model selector machinery |
| Scope compatibility routes (`/scopes/{scope_ref}/rows`, etc.) | Deferred to Phase 9 — requires frontend route migration |
| Legacy `status` field alongside canonical semantic fields | Deferred to Phase 9 — requires frontend contract migration |
| `scope_ref` field in `MasterQueryRow` and related response types | These reflect the read-model scope concept which is intentionally preserved |

## Docs Update

- `docs/workflows.md`: update `not_visible_in_scope_count` reference if present
- `docs/contracts.md`: update `ScopedTrashDeleteRequest` reference if present
- `design/branch-infra-phase-map.md`: record Phase 5.5 as complete after landing

## Verification

- All existing tests pass after rename (pure mechanical change)
- `scripts/validate_docs.py` passes
- Architecture tests in `test_services_architecture.py` pass
- Frontend build succeeds
