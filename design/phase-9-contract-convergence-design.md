# Phase 9: Contract Convergence Design

## Purpose

Converge code, docs, frontend, and compatibility layers onto the intended long-term shape established through Phases 1-8. Reduce the compatibility surface, remove dead restore artifacts, and align the frontend to branch-first routes.

## Scope

Contract surface convergence only. No workflow service boundary reorganization, no fill/QA decomposition, no pivot service restructuring.

## Decisions

- scope routes stay for `master` and `orphan` only; branch-ref scope aliases are removed
- legacy master routes (`/branches/master/entries/{key}` and `/branches/master/search`) are removed
- `ScopeRowsResponse` and `ScopeLookupResponse` are removed; scope routes return `BranchRowsResponse` and `BranchLookupResponse` with `branch_ref` populated as `"master"` or `"orphan"`
- frontend switches from scope-aware API calls to canonical branch routes
- all restore artifacts are removed: frontend UI, API function, docs reference, backend dead code including DB columns
- `trash_until` and `restored_at` columns are dropped; schema bumps to `variant-v11`
- `restore_if_trashed` parameter is removed from variant store, repository, and catalog
- `TrashRestoreService` is renamed to `TrashService`

## Section 1: Scope Route Convergence

### Scope route narrowing

The two scope routes (`/scopes/{scope_ref}/rows` and `/scopes/{scope_ref}/lookup`) currently accept any scope ref including branch refs. After convergence:

- `/scopes/master/rows` and `/scopes/master/lookup` stay as the canonical master-read surface
- `/scopes/orphan/rows` and `/scopes/orphan/lookup` stay as the canonical orphan-read surface
- branch refs (`rel/current`, `dev/x.y.z`) passed to scope routes return `400`
- callers must use `/branches/{branch_ref}/rows` and `/branches/{branch_ref}/lookup` for branch reads

Implementation: change `ScopeSelector.parse()` in the scope route handlers to reject branch refs, or introduce a guard in the route handler that only allows `master` and `orphan` before calling the shared payload builder.

### Legacy master route removal

Both `/branches/master/entries/{key}` and `/branches/master/search` are deleted from `scopes_read_models.py`. Their dedicated response schemas (`MasterEntryResponse`, `MasterQueryRow`, `MasterSearchResponse`) are removed from `schemas.py`.

### Response schema unification

`ScopeRowsResponse` and `ScopeLookupResponse` are removed from `schemas.py`. The scope routes for `master` and `orphan` return `BranchRowsResponse` and `BranchLookupResponse` with `branch_ref` populated as `"master"` or `"orphan"`.

The shared payload builders (`_scope_rows_payload` and `_scope_lookup_payload`) continue to return a `scope_ref` key internally. The route handlers pop `scope_ref` and replace it with `branch_ref` set to the literal scope name, matching the pattern already used by the branch route handlers.

## Section 2: Frontend Alignment

### Scope-to-branch API switch

In `frontend/src/domains/branches/api.ts`:

- `getScopeRows()` stays as the function name but narrows to scope-only reads (master, orphan) calling `/scopes/{scopeRef}/rows`
- `lookupScope()` stays as the function name but narrows to scope-only reads calling `/scopes/{scopeRef}/lookup`
- new `getBranchRows()` calls `/branches/{branchRef}/rows` for branch reads
- new `lookupBranch()` calls `/branches/{branchRef}/lookup` for branch reads
- `lookupMasterByKey()` and `lookupMasterBySource()` are removed

In `frontend/src/domains/branches/types.ts`:

- `ScopeRowsResponse` and `ScopeLookupResponse` are removed
- `MasterQueryRow`, `MasterEntryResponse`, and `MasterSearchResponse` are removed
- add `BranchRowsResponse` and `BranchLookupResponse` types matching the unified backend response shape (both scope and branch routes now return the same shape with `branch_ref`)

### BranchOpsPage update

The page currently passes `scopeRef` (which can be "master", "rel/current", or "dev/x.y.z") into `getScopeRows`. After convergence:

- when `scopeRef === "master"` or `scopeRef === "orphan"`, call `getScopeRows()` (which now only handles scope-route reads)
- otherwise, call `getBranchRows()`
- same split for lookup: `lookupScope()` for master/orphan, `lookupBranch()` for branch refs
- rename `lookupScopeRef` state variable to `lookupRef`

### Restore UI removal

- remove `restoreVariants()` from `frontend/src/domains/variants/api.ts`
- remove restore mutation, restore button, and "Restore variant IDs" input from `BranchOpsPage.tsx`
- rename "Trash / Restore" tab to "Trash"
- remove restore button and mutation from `VariantsPage.tsx`
- remove restore button and mutation from `VariantDrawer.tsx`
- remove `restored_at` display from `VariantDrawer.tsx`

### Frontend type cleanup

Remove `restored_at` and `trash_until` from:

- `EntryVariantView` in `frontend/src/domains/branches/types.ts`
- `SameSourceCandidateRow` in `frontend/src/domains/branches/types.ts`
- variant types in `frontend/src/domains/variants/types.ts`

## Section 3: Backend Cleanup

### Restore dead code removal

Phase 8 made trashed terminal with no restore. The following restore artifacts are now dead code:

DB schema:

- drop `trash_until` column from `variants` table
- drop `restored_at` column from `variants` table
- bump schema version from `variant-v10` to `variant-v11`

Variant store (`app/services/variant/store.py`):

- remove `restore_if_trashed` parameter from `ensure_or_create_variant()`
- remove the restore branch inside `ensure_or_create_variant()` that sets `trashed_at = NULL, trash_until = NULL, restored_at = ?`
- remove `trash_until` parameter from `trash_variant()`
- remove `trash_until` and `restored_at` from variant row assembly and column lists

Variant repository (`app/services/variant/repositories.py`):

- remove `restore_if_trashed` parameter from `ensure_canonical_variant()`
- remove `trash_until` parameter from `trash_variant()`

Variant catalog (`app/services/variant/catalog.py`):

- remove `restore_if_trashed` parameter from `resolve_or_create_canonical_variant()`

Variant records (`app/services/variant/records.py`):

- remove `trash_until` and `restored_at` fields from variant record types

Read model types (`app/services/read_models/types.py`):

- remove `trash_until` and `restored_at` from `ProjectVariantRow`, `SameSourceCandidateRow`, `EntryVariantRow`, `OrphanVariantRow`

Read model hydration (`app/services/read_models/hydrate.py`):

- remove `trash_until` and `restored_at` from all hydration paths

Read model repository (`app/services/read_models/repository.py`):

- remove `v.trash_until` and `v.restored_at` from SELECT column lists

Bootstrap and import batch mutation:

- remove `"trash_until": None` and `"restored_at": None` from new-variant dicts in `bootstrap.py` and `import_batch_mutation.py`

Workflow service:

- rename `TrashRestoreService` to `TrashService` in `app/services/workflows/trash_restore.py`
- rename the file to `app/services/workflows/trash.py`
- update imports in `application.py`

### Schema response cleanup

Remove from `app/schemas.py`:

- `ScopeRowsResponse`
- `ScopeLookupResponse`
- `MasterEntryResponse`
- `MasterQueryRow`
- `MasterSearchResponse`

Remove `trash_until` and `restored_at` from response models that expose variant data (if any exist in `schemas.py` beyond the read model types).

## Section 4: Documentation Alignment

### contracts.md

- remove `POST /api/projects/{project_id}/variants/trash/restore` from HTTP route inventory
- remove `trash_until` and `restored_at` from all response shape descriptions
- remove scope routes for branch refs from inventory; keep only `/scopes/master/rows`, `/scopes/master/lookup`, `/scopes/orphan/rows`, `/scopes/orphan/lookup`
- remove legacy master routes from inventory
- remove `MasterEntryResponse`, `MasterSearchResponse`, `ScopeRowsResponse`, `ScopeLookupResponse` references
- update "Frontend and Backend Contract" section to say frontend uses branch-first routes
- update schema version to `variant-v11`
- add note that scope routes only accept `master` and `orphan`

### workflows.md

- remove "restore" from "trash or restore workflows" references
- update `TrashRestoreService` reference to `TrashService`
- update file reference from `trash_restore.py` to `trash.py`

### system.md

- update schema version reference to `variant-v11`
- remove `trash_until` and `restored_at` from any variant field descriptions

### branch-infra-phase-map.md

- mark Phase 9 as complete with completed decisions and artifacts
- update suggested next session

### Test updates

- update `test_services_architecture.py` route assertions to match the reduced route surface (no scope branch aliases, no legacy master routes)
- update `test_variant_api.py` to use branch routes for branch-ref reads, test that scope routes reject branch refs with 400, and test master/orphan scope routes return `BranchRowsResponse` shape
- remove `trash_until` and `restored_at` from test assertions and expected row shapes
- add tests for the schema version bump behavior

## Out Of Scope

- workflow service boundary reorganization (TrashService stays in workflows/)
- fill/QA service decomposition
- pivot service restructuring
- any new feature work
- frontend routing changes beyond API call alignment

## Success Condition

After Phase 9:

- the only scope routes accept `master` and `orphan`; branch reads go through `/branches/{branch_ref}/...`
- no legacy master routes exist
- the frontend calls branch-first routes for branch reads and scope routes only for master/orphan
- all restore artifacts are removed from code, docs, frontend, and DB schema
- `trash_until` and `restored_at` are gone from the entire stack
- schema version is `variant-v11`
- all active docs match the converged contract surface
- tests validate the new route surface and reject the old compatibility paths
