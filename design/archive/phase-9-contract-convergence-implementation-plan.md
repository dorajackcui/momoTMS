# Phase 9: Contract Convergence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Converge code, docs, frontend, and compatibility layers onto the branch-first contract established through Phases 1-8. Remove scope branch aliases, legacy master routes, all restore artifacts, and dead `trash_until`/`restored_at` columns.

**Architecture:** Backend scope routes narrow to master/orphan only; branch-ref reads go through canonical branch routes. Frontend switches from scope API calls to branch routes. All restore code, DB columns, and UI are removed. Schema bumps to variant-v11.

**Tech Stack:** Python/FastAPI, SQLite, React/TypeScript, pytest, Playwright

---

### Task 1: Remove restore dead code from backend variant store and lifecycle

**Files:**
- Modify: `app/services/variant/store.py:63-107` (remove `restore_if_trashed` from `update()`)
- Modify: `app/services/variant/store.py:349-369` (remove `trash_until` from `trash_variant()`)
- Modify: `app/services/variant/store.py:475-505` (remove `trash_until`, `restored_at` from `_hydrate_rows()`)
- Modify: `app/services/variant/store.py:507-558` (remove from `hydrate_variant_rows()` required_columns)
- Modify: `app/services/variant/repositories.py:24-40` (remove `restore_if_trashed` from `update()`)
- Modify: `app/services/variant/repositories.py:76-83` (remove `trash_until` from `trash_variant()`)
- Modify: `app/services/variant/catalog.py:60-87` (remove `restore_if_trashed` from `update_variant()`)
- Modify: `app/services/variant/records.py:17-35` (remove `trash_until`, `restored_at` from VariantRecord)
- Modify: `app/services/variant/lifecycle.py:40-49` (remove empty-string `trash_until` arg from `trash_orphan()`)

- [ ] **Step 1: Remove `trash_until` and `restored_at` from VariantRecord TypedDict**

In `app/services/variant/records.py`, remove the two fields:

```python
class VariantRecord(TypedDict):
    variant_id: int
    entry_id: int
    file_name: str
    source: str
    translations: dict[str, str]
    remarks: dict[str, str]
    orphaned_at: str | None
    trashed_at: str | None
    pivot_status: PivotStatus
    pivot_changed_by_scope_type: str | None
    pivot_changed_by_scope_value: str | None
    pivot_changed_at: str | None
    pivot_reviewed_at: str | None
    pivot_status_updated_at: str
    created_at: str
    updated_at: str
```

- [ ] **Step 2: Remove `restore_if_trashed` from `_VariantStore.update()`**

In `app/services/variant/store.py`, simplify the `update()` method to remove the `restore_if_trashed` parameter and the entire restore branch. The method should always execute the simple update:

```python
def update(
    self,
    variant_id: int,
    file_name: str,
    source: str,
    timestamp: str,
    conn: sqlite3.Connection | None = None,
) -> None:
    if conn is not None:
        conn.execute(
            """
            UPDATE variants
            SET file_name = ?,
                source = ?,
                updated_at = ?
            WHERE variant_id = ?
            """,
            (file_name, source, timestamp, variant_id),
        )
        return
    with get_conn() as local_conn:
        self.update(
            variant_id,
            file_name,
            source,
            timestamp,
            conn=local_conn,
        )
```

- [ ] **Step 3: Remove `trash_until` from `_VariantStore.trash_variant()`**

```python
def trash_variant(
    self,
    variant_id: int,
    timestamp: str,
    conn: sqlite3.Connection | None = None,
) -> None:
    if conn is not None:
        conn.execute(
            """
            UPDATE variants
            SET trashed_at = ?,
                updated_at = ?
            WHERE variant_id = ?
            """,
            (timestamp, timestamp, variant_id),
        )
        return
    with get_conn() as local_conn:
        self.trash_variant(variant_id, timestamp, conn=local_conn)
```

- [ ] **Step 4: Remove `trash_until` and `restored_at` from `_hydrate_rows()` return dicts**

In the list comprehension inside `_hydrate_rows()`, remove the two lines:

```python
"trash_until": row["trash_until"],
"restored_at": row["restored_at"],
```

- [ ] **Step 5: Remove `trash_until` and `restored_at` from `hydrate_variant_rows()` required_columns set**

In `hydrate_variant_rows()`, remove `"trash_until"` and `"restored_at"` from the `required_columns` set.

- [ ] **Step 6: Remove `restore_if_trashed` from `VariantCommandRepository.update()`**

In `app/services/variant/repositories.py`, remove the parameter and stop passing it through:

```python
def update(
    self,
    variant_id: int,
    file_name: str,
    source: str,
    timestamp: str,
    conn: sqlite3.Connection | None = None,
) -> None:
    self._store.update(
        variant_id,
        file_name,
        source,
        timestamp,
        conn=conn,
    )
```

- [ ] **Step 7: Remove `trash_until` from `VariantCommandRepository.trash_variant()`**

```python
def trash_variant(
    self,
    variant_id: int,
    timestamp: str,
    conn: sqlite3.Connection | None = None,
) -> None:
    self._store.trash_variant(variant_id, timestamp, conn=conn)
```

- [ ] **Step 8: Remove `restore_if_trashed` from `VariantCatalogService.update_variant()`**

In `app/services/variant/catalog.py`, remove the parameter and stop passing it through:

```python
def update_variant(
    self,
    variant_id: int,
    content: VariantContent,
    actor_scope: tuple[str, str] | None = None,
    conn: sqlite3.Connection | None = None,
) -> None:
    previous_variant = self.get_variant(variant_id, conn=conn)
    timestamp = now_iso()
    self._commands.update(
        variant_id,
        content["file_name"],
        content["source"],
        timestamp,
        conn=conn,
    )
    self._commands.overwrite_translations(variant_id, content["translations"], timestamp, conn=conn)
    self._commands.overwrite_remarks(variant_id, content["remarks"], timestamp, conn=conn)
    self._pivot.refresh_variant(
        variant_id=variant_id,
        old_variant=previous_variant,
        new_translations=content["translations"],
        actor_scope=actor_scope,
        timestamp=timestamp,
        conn=conn,
    )
```

- [ ] **Step 9: Remove empty-string `trash_until` from `VariantLifecycleService.trash_orphan()`**

In `app/services/variant/lifecycle.py`, line 48 currently passes `""` as `trash_until`. Change to:

```python
def trash_orphan(
    self,
    variant_id: int,
    entry_id: int,
    conn: sqlite3.Connection | None = None,
    timestamp: str | None = None,
) -> None:
    marker = timestamp or now_iso()
    self._variant_commands.trash_variant(variant_id, marker, conn=conn)
    self.refresh_orphan_states(entry_id, conn=conn, timestamp=marker)
```

- [ ] **Step 10: Run tests to verify nothing broke**

Run: `.\.venv\Scripts\python.exe -m pytest -q tests/test_branch_service.py tests/test_io_flows.py`

Expected: some tests may fail due to `trash_until`/`restored_at` assertions. Note failures for Task 6.

- [ ] **Step 11: Commit**

```bash
git add app/services/variant/store.py app/services/variant/repositories.py app/services/variant/catalog.py app/services/variant/records.py app/services/variant/lifecycle.py
git commit -m "refactor: remove restore_if_trashed, trash_until, and restored_at from variant layer"
```

---

### Task 2: Remove restore dead code from read models, bootstrap, and import batch mutation

**Files:**
- Modify: `app/services/read_models/types.py` (remove `trash_until`, `restored_at` from VariantSnapshot, HistoryCandidate, EntryTimelineItem, BranchEntryView)
- Modify: `app/services/read_models/hydrate.py` (remove from all hydration dicts)
- Modify: `app/services/read_models/repository.py:460-461` (remove from SELECT)
- Modify: `app/services/branch/bootstrap.py:477-478` (remove from variant cache dict)
- Modify: `app/services/branch/import_batch_mutation.py:488-489` (remove from variant cache dict)

- [ ] **Step 1: Remove `trash_until` and `restored_at` from read model types**

In `app/services/read_models/types.py`:

Remove `trash_until: str | None` and `restored_at: str | None` from:
- `VariantSnapshot` (lines 26-27)
- `HistoryCandidate` (lines 71-72)
- `EntryTimelineItem` (lines 92-93)
- `BranchEntryView` (lines 113-114)

- [ ] **Step 2: Remove from hydration dicts in `ReadModelHydrator`**

In `app/services/read_models/hydrate.py`, remove every `"trash_until": variant["trash_until"],` and `"restored_at": variant["restored_at"],` line from:
- `history_candidates()` (lines 113-114)
- `entry_timeline_items()` (lines 156-157)
- `branch_entry_views()` (lines 197-198)
- `variant_snapshot()` (lines 222-223)

- [ ] **Step 3: Remove from `_select_variant_rows()` SELECT list**

In `app/services/read_models/repository.py`, remove these two lines from the SELECT clause in `_select_variant_rows()`:

```
v.trash_until,
v.restored_at,
```

(Lines 460-461)

- [ ] **Step 4: Remove from bootstrap variant cache dict**

In `app/services/branch/bootstrap.py`, remove from the new-variant cache dict around line 477-478:

```python
"trash_until": None,
"restored_at": None,
```

- [ ] **Step 5: Remove from import batch mutation variant cache dict**

In `app/services/branch/import_batch_mutation.py`, remove from the new-variant cache dict around line 488-489:

```python
"trash_until": None,
"restored_at": None,
```

- [ ] **Step 6: Commit**

```bash
git add app/services/read_models/types.py app/services/read_models/hydrate.py app/services/read_models/repository.py app/services/branch/bootstrap.py app/services/branch/import_batch_mutation.py
git commit -m "refactor: remove trash_until and restored_at from read models, bootstrap, and import batch mutation"
```

---

### Task 3: Rename TrashRestoreService to TrashService and bump schema to variant-v11

**Files:**
- Rename: `app/services/workflows/trash.py` (renamed from trash_restore.py)
- Modify: `app/services/workflows/trash.py` (rename class)
- Modify: `app/services/workflows/application.py:15,31,244,262` (update import and references)
- Modify: `app/db.py:12` (bump SCHEMA_VERSION)
- Modify: `app/db.py:115-129` (remove trash_until and restored_at columns)

- [ ] **Step 1: Rename file and class**

Rename `app/services/workflows/trash.py` (already renamed from `trash_restore.py`). In the file, change the class name from `TrashRestoreService` to `TrashService`.

- [ ] **Step 2: Update imports in `application.py`**

In `app/services/workflows/application.py`:

Change line 15:
```python
from app.services.workflows.trash import TrashService
```

Change line 31:
```python
self.trash_service = TrashService()
```

Change line 244:
```python
self.trash_service.delete(
```

Change line 262:
```python
self.trash_service.project_trash(
```

- [ ] **Step 3: Bump schema version and remove columns from DB schema**

In `app/db.py`, change line 12:
```python
SCHEMA_VERSION = "variant-v11"
```

In the CREATE TABLE variants statement (starting around line 115), remove:
```sql
trash_until TEXT,
restored_at TEXT,
```

The `trashed_at TEXT,` line stays.

- [ ] **Step 4: Run tests to see current state**

Run: `.\.venv\Scripts\python.exe -m pytest -q`

Expected: tests that reference `TrashRestoreService` by import or `trash_until`/`restored_at` in assertions will fail. Note which tests need updating.

- [ ] **Step 5: Commit**

```bash
git add app/services/workflows/trash.py app/services/workflows/application.py app/db.py
git commit -m "refactor: rename TrashRestoreService to TrashService and bump schema to variant-v11"
```

---

### Task 4: Update tests for backend changes

**Files:**
- Modify: `tests/test_branch_service.py:17` (update import)
- Modify: `tests/test_io_flows.py:12` (update import)
- Modify: `tests/test_variant_api.py:20,562,677,1120-1121` (update import and remove `trash_until`/`restored_at` assertions)

- [ ] **Step 1: Update `TrashRestoreService` imports in test files**

In `tests/test_branch_service.py` line 17, change:
```python
from app.services.workflows.trash import TrashService
```

In `tests/test_io_flows.py` line 12, change:
```python
from app.services.workflows.trash import TrashService
```

In `tests/test_variant_api.py` line 20, change:
```python
from app.services.workflows.trash import TrashService
```

- [ ] **Step 2: Update all usages of `TrashRestoreService()` to `TrashService()`**

In `tests/test_variant_api.py`, change line 562:
```python
trash_service = TrashService()
```

And update references on lines 565-566 from `trash_restore.delete(...)` / `trash_restore.project_trash(...)` to `trash_service.delete(...)` / `trash_service.project_trash(...)`.

Same pattern at line 677: change to `trash_service = TrashService()` and update lines 682-683.

Apply the same rename in `tests/test_branch_service.py` and `tests/test_io_flows.py` for any `TrashRestoreService()` instantiations.

- [ ] **Step 3: Remove `trash_until` and `restored_at` from test assertions**

In `tests/test_variant_api.py` around lines 1120-1121, remove `"trash_until"` and `"restored_at"` from any expected-fields lists or assertions.

Search all test files for any other `trash_until` or `restored_at` references in assertions and remove them.

- [ ] **Step 4: Run full backend test suite**

Run: `.\.venv\Scripts\python.exe -m pytest -q`

Expected: PASS. All backend tests green.

- [ ] **Step 5: Commit**

```bash
git add tests/test_branch_service.py tests/test_io_flows.py tests/test_variant_api.py
git commit -m "test: update tests for TrashService rename and removed restore columns"
```

---

### Task 5: Narrow scope routes and remove legacy master routes

**Files:**
- Modify: `app/routers/scopes_read_models.py:72-111` (narrow scope routes to master/orphan only)
- Modify: `app/routers/scopes_read_models.py:183-236` (remove legacy master routes)
- Modify: `app/routers/scopes_read_models.py:6-16` (remove unused schema imports)
- Modify: `app/schemas.py:177-183,193-198,257-275` (remove ScopeRowsResponse, ScopeLookupResponse, MasterQueryRow, MasterEntryResponse, MasterSearchResponse)

- [ ] **Step 1: Narrow scope route handlers to reject branch refs**

In `app/routers/scopes_read_models.py`, modify `project_scope_rows()` to validate that the scope ref is `master` or `orphan`, returning 400 for branch refs. Replace the handler:

```python
@router.get("/api/projects/{project_id}/scopes/{scope_ref:path}/rows", response_model=BranchRowsResponse)
def project_scope_rows(
    project_id: int,
    scope_ref: str,
    search_business_key: str | None = Query(default=None),
    search_source: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int | None = Query(default=None, ge=1),
) -> BranchRowsResponse:
    def run() -> BranchRowsResponse:
        selector = ScopeSelector.parse(scope_ref)
        if not selector.is_master and not selector.is_orphan:
            raise ValueError(f"scope route only accepts master or orphan, got: {scope_ref}")
        payload = _scope_rows_payload(
            project_id,
            selector,
            search_business_key=search_business_key,
            search_source=search_source,
            page=page,
            page_size=page_size,
        )
        payload.pop("scope_ref", None)
        return BranchRowsResponse(
            branch_ref=str(selector),
            **payload,
        )

    return handle_errors(run)
```

- [ ] **Step 2: Narrow scope lookup handler the same way**

```python
@router.get("/api/projects/{project_id}/scopes/{scope_ref:path}/lookup", response_model=BranchLookupResponse)
def project_scope_lookup(
    project_id: int,
    scope_ref: str,
    business_key: str | None = Query(default=None),
    source: str | None = Query(default=None),
) -> BranchLookupResponse:
    def run() -> BranchLookupResponse:
        selector = ScopeSelector.parse(scope_ref)
        if not selector.is_master and not selector.is_orphan:
            raise ValueError(f"scope route only accepts master or orphan, got: {scope_ref}")
        payload = _scope_lookup_payload(
            project_id,
            selector,
            business_key=business_key,
            source=source,
        )
        payload.pop("scope_ref", None)
        return BranchLookupResponse(
            branch_ref=str(selector),
            **payload,
        )

    return handle_errors(run)
```

- [ ] **Step 3: Remove legacy master route handlers**

Delete the `project_master_entry()` and `project_master_search()` functions entirely (lines 183-236).

- [ ] **Step 4: Remove unused schema imports**

Update the imports at the top of `scopes_read_models.py` to remove `ScopeRowsResponse`, `ScopeLookupResponse`, `MasterEntryResponse`, `MasterQueryRow`, `MasterSearchResponse`. Keep `BranchRowsResponse` and `BranchLookupResponse`.

```python
from app.schemas import (
    BranchListResponse,
    BranchLookupResponse,
    BranchRowsResponse,
    SameSourceCandidatesResponse,
)
```

- [ ] **Step 5: Remove schema classes from `schemas.py`**

Delete these classes from `app/schemas.py`:
- `ScopeRowsResponse` (lines 177-183)
- `ScopeLookupResponse` (lines 193-198)
- `MasterQueryRow` (lines 257-264)
- `MasterEntryResponse` (lines 267-270)
- `MasterSearchResponse` (lines 273-275)

- [ ] **Step 6: Run tests to verify route changes**

Run: `.\.venv\Scripts\python.exe -m pytest -q tests/test_variant_api.py tests/test_services_architecture.py`

Expected: some test failures for tests hitting scope routes with branch refs or legacy master routes.

- [ ] **Step 7: Commit**

```bash
git add app/routers/scopes_read_models.py app/schemas.py
git commit -m "feat: narrow scope routes to master/orphan only and remove legacy master routes"
```

---

### Task 6: Update tests for route surface changes

**Files:**
- Modify: `tests/test_variant_api.py` (update scope route tests, remove legacy master tests)
- Modify: `tests/test_services_architecture.py` (update doc assertions)

- [ ] **Step 1: Update the core-cycle E2E test in `test_variant_api.py`**

Around lines 126-152, the test calls scope routes with branch refs and legacy master routes. Update:

Change the master scope rows assertion (line 126-131):
```python
master_rows_response = client.get("/api/projects/1/scopes/master/rows")
assert master_rows_response.status_code == 200
master_rows_payload = master_rows_response.json()
assert master_rows_payload["branch_ref"] == "master"
assert any(row["state"] == "orphan" for row in master_rows_payload["rows"])
assert any(row["business_key"] == "common.welcome" for row in master_rows_payload["rows"])
```

Change the rel/current read to use the branch route (lines 133-138):
```python
rel_rows_response = client.get("/api/projects/1/branches/rel/current/rows")
assert rel_rows_response.status_code == 200
assert all(
    any(binding["branch_ref"] == "rel/current" for binding in row["bindings"])
    for row in rel_rows_response.json()["rows"]
)
```

Change the dev lookup to use the branch route (lines 140-148):
```python
dev_lookup_response = client.get(
    f"/api/projects/1/branches/dev/{sample['dev_version']}/lookup",
    params={"business_key": "dev.mutable"},
)
assert dev_lookup_response.status_code == 200
dev_lookup_payload = dev_lookup_response.json()
assert dev_lookup_payload["branch_ref"] == f"dev/{sample['dev_version']}"
assert dev_lookup_payload["mode"] == "business_key"
assert [row["business_key"] for row in dev_lookup_payload["rows"]] == ["dev.mutable"]
```

Remove the legacy master entry test (lines 150-152):
```python
# Remove these lines entirely:
# master_response = client.get("/api/projects/1/branches/master/entries/rel.locked.same")
# assert master_response.status_code == 200
# assert all(row["scope_ref"] == "master" for row in master_response.json()["results"])
```

- [ ] **Step 2: Add tests for scope route rejection of branch refs**

After the existing scope route tests, add tests verifying that scope routes reject branch refs with 400:

```python
scope_rel_response = client.get("/api/projects/1/scopes/rel/current/rows")
assert scope_rel_response.status_code == 400

scope_dev_response = client.get(f"/api/projects/1/scopes/dev/{sample['dev_version']}/rows")
assert scope_dev_response.status_code == 400
```

- [ ] **Step 3: Update the 404-for-missing-project test**

In `test_scope_read_routes_return_404_for_missing_project()` (line 280+), remove the scope-with-branch-ref and legacy master route entries since those routes are gone. Update:

```python
responses = [
    client.get("/api/projects/999/variants"),
    client.get("/api/projects/999/branches"),
    client.get("/api/projects/999/scopes/master/rows"),
    client.get("/api/projects/999/scopes/master/lookup", params={"business_key": "common.welcome"}),
    client.get(
        "/api/projects/999/history/same-source-candidates",
        params={"business_key": "common.welcome", "source": "Welcome {0}"},
    ),
    client.get("/api/projects/999/branches/dev"),
]
```

Remove:
- `client.get("/api/projects/999/scopes/rel/current/rows")`
- `client.get("/api/projects/999/branches/master/entries/common.welcome")`
- `client.get("/api/projects/999/branches/master/search", params={"source": "Welcome {0}"})`

- [ ] **Step 4: Update architecture test assertions**

In `tests/test_services_architecture.py`, around lines 120-122:

Remove the assertion for scope routes with `compatibility alias` since they're gone:
```python
# Remove:
# assert "compatibility alias" in contracts_doc
# assert "scope-aware" in contracts_doc
```

Keep the assertions for scope routes that remain (master/orphan):
```python
assert "GET /api/projects/{project_id}/scopes/{scope_ref:path}/rows" in contracts_doc
assert "GET /api/projects/{project_id}/scopes/{scope_ref:path}/lookup" in contracts_doc
```

(These should still be documented in contracts.md as master/orphan routes.)

- [ ] **Step 5: Run full test suite**

Run: `.\.venv\Scripts\python.exe -m pytest -q`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add tests/test_variant_api.py tests/test_services_architecture.py
git commit -m "test: update tests for narrowed scope routes and removed legacy master routes"
```

---

### Task 7: Frontend — remove restore UI and stale types

**Files:**
- Modify: `frontend/src/domains/variants/api.ts:42-47` (remove `restoreVariants`)
- Modify: `frontend/src/domains/variants/types.ts:20-21` (remove `trash_until`, `restored_at`)
- Modify: `frontend/src/domains/branches/types.ts:20-21,104-138,125-138,152-153` (remove stale types)
- Modify: `frontend/src/pages/branches/BranchOpsPage.tsx` (remove restore UI)
- Modify: `frontend/src/pages/variants/VariantsPage.tsx` (remove restore)
- Modify: `frontend/src/features/variant-drawer/VariantDrawer.tsx` (remove restore)
- Modify: `frontend/src/app/shell/AppShell.tsx:58` (remove "restore" from hint)
- Modify: `frontend/src/pages/runs/RunsPage.tsx:163` (remove "restore" from empty state)

- [ ] **Step 1: Remove `restoreVariants` from variants API**

In `frontend/src/domains/variants/api.ts`, delete the `restoreVariants` function (lines 42-47).

- [ ] **Step 2: Remove `trash_until` and `restored_at` from variant types**

In `frontend/src/domains/variants/types.ts`, remove from `EntryVariantInspection`:
```
trash_until: string | null;
restored_at: string | null;
```
(Lines 20-21)

In `frontend/src/domains/branches/types.ts`, remove from `EntryVariantView`:
```
trash_until: string | null;
restored_at: string | null;
```
(Lines 20-21)

Also remove from `SameSourceCandidateRow`:
```
trash_until: string | null;
restored_at: string | null;
```
(Lines 152-153)

- [ ] **Step 3: Remove stale scope and master types from branch types**

In `frontend/src/domains/branches/types.ts`, delete:
- `MasterQueryRow` type (lines 104-112)
- `MasterEntryResponse` type (lines 114-118)
- `MasterSearchResponse` type (lines 120-123)
- `ScopeRowsResponse` type (lines 125-131)
- `ScopeLookupResponse` type (lines 133-138)

Add new types to replace them:
```typescript
export type BranchRowsResponse = {
  branch_ref: string;
  rows: ProjectVariantRow[];
  total_rows: number;
  page: number;
  page_size: number;
};

export type BranchLookupResponse = {
  branch_ref: string;
  mode: "business_key" | "source";
  value: string;
  rows: ProjectVariantRow[];
};
```

- [ ] **Step 4: Remove restore mutation from VariantDrawer**

In `frontend/src/features/variant-drawer/VariantDrawer.tsx`:

Remove the `restoreVariants` import (line 5) — change to:
```typescript
import { getEntryVariants } from "@/domains/variants/api";
```

Remove the entire `restoreMutation` block (lines 37-53).

Remove the `restored_at` line from the KeyValueList (line 109):
```
["restored_at", formatTimestamp(variant.restored_at)],
```

Remove the restore button block (lines 134-143):
```tsx
{variant.is_trashed ? (
  <div className={styles.toolbar}>
    <button ... >
      Restore this variant
    </button>
  </div>
) : null}
```

- [ ] **Step 5: Remove restore mutation from VariantsPage**

In `frontend/src/pages/variants/VariantsPage.tsx`:

Remove the `restoreVariants` import (line 10).

Remove the `restoreMutation` block (lines 105-119).

Remove the restore button (lines 410-413).

- [ ] **Step 6: Remove restore from BranchOpsPage TrashTab**

In `frontend/src/pages/branches/BranchOpsPage.tsx`:

Remove `restoreVariants` import (line 23).

Remove `restoreIds` state (line 90):
```
const [restoreIds, setRestoreIds] = useState("");
```

Rename the tab label from `"Trash / Restore"` to `"Trash"` (line 57):
```typescript
{ key: "trash", label: "Trash" },
```

In the TrashTab call (lines 480-504), remove the restore-related props:
```tsx
<TrashTab
  deleteKeys={deleteKeys}
  onDeleteKeysChange={setDeleteKeys}
  onDelete={() =>
    runJobMutation.mutate({
      devVersion:
        shell.branchRef?.startsWith("dev/") ? shell.branchRef.slice(4) : null,
      run: () =>
        deleteBranchBusinessKeys(
          projectId,
          shell.branchRef || "rel/current",
          parseLineSeparatedList(deleteKeys),
        ),
    })
  }
/>
```

Simplify the `TrashTab` function component (lines 867-905) to remove all restore props and UI:

```tsx
function TrashTab(props: {
  deleteKeys: string;
  onDeleteKeysChange: (value: string) => void;
  onDelete: () => void;
}) {
  return (
    <Panel kicker="Trash" title="Branch delete and project trash">
      <label className={ui.field}>
        <span className={ui.fieldLabel}>Delete business keys</span>
        <textarea
          className={ui.textarea}
          value={props.deleteKeys}
          onChange={(event) => props.onDeleteKeysChange(event.target.value)}
          placeholder="One key per line"
        />
        <button className={buttonClassName("danger")} onClick={props.onDelete}>
          Delete from branch
        </button>
      </label>
    </Panel>
  );
}
```

Also remove `parseVariantIdList` from the import on line 44 if it's only used for restore.

- [ ] **Step 7: Update text references to "restore"**

In `frontend/src/app/shell/AppShell.tsx` line 58, change:
```typescript
hint: "Orphan history, timeline inspection, and trash actions.",
```

In `frontend/src/pages/runs/RunsPage.tsx` line 163, change:
```
body="Run import, apply, replace, fill, QA, or trash actions to populate this page."
```

- [ ] **Step 8: Build frontend to verify**

Run: `npm run build:app`

Expected: Build succeeds with no TypeScript errors.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/domains/variants/api.ts frontend/src/domains/variants/types.ts frontend/src/domains/branches/types.ts frontend/src/features/variant-drawer/VariantDrawer.tsx frontend/src/pages/variants/VariantsPage.tsx frontend/src/pages/branches/BranchOpsPage.tsx frontend/src/app/shell/AppShell.tsx frontend/src/pages/runs/RunsPage.tsx
git commit -m "feat: remove restore UI and stale scope/master types from frontend"
```

---

### Task 8: Frontend — switch from scope API calls to branch routes

**Files:**
- Modify: `frontend/src/domains/branches/api.ts` (add `getBranchRows`, `lookupBranch`; narrow `getScopeRows`, `lookupScope`; remove master functions)
- Modify: `frontend/src/pages/branches/BranchOpsPage.tsx` (route calls based on scope vs branch)

- [ ] **Step 1: Add branch route functions and narrow scope functions**

In `frontend/src/domains/branches/api.ts`, rewrite the scope/branch API functions:

Remove `lookupMasterByKey` and `lookupMasterBySource` functions.

Update imports at top — remove `MasterEntryResponse`, `MasterSearchResponse`, `ScopeRowsResponse`, `ScopeLookupResponse`. Add `BranchRowsResponse`, `BranchLookupResponse`:

```typescript
import type {
  BranchListResponse,
  BranchLookupResponse,
  BranchMutationInput,
  BranchReplacePreview,
  BranchRowsResponse,
  DevBranchDetail,
  SameSourceCandidatesResponse,
} from "@/domains/branches/types";
```

Replace the `getScopeRows` function (keep name, it now only handles master/orphan):

```typescript
export function getScopeRows(
  projectId: number,
  scopeRef: string,
  params: {
    search_business_key?: string;
    search_source?: string;
    page?: number;
    page_size?: number;
  },
) {
  const query = buildQueryString(params);
  return fetchJson<BranchRowsResponse>(
    `/api/projects/${projectId}/scopes/${encodeURIComponent(scopeRef)}/rows?${query}`,
  );
}
```

Add `getBranchRows`:

```typescript
export function getBranchRows(
  projectId: number,
  branchRef: string,
  params: {
    search_business_key?: string;
    search_source?: string;
    page?: number;
    page_size?: number;
  },
) {
  const query = buildQueryString(params);
  return fetchJson<BranchRowsResponse>(
    `/api/projects/${projectId}/branches/${encodeURIComponent(branchRef)}/rows?${query}`,
  );
}
```

Replace `lookupScope`:

```typescript
export function lookupScope(
  projectId: number,
  scopeRef: string,
  params: {
    business_key?: string;
    source?: string;
  },
) {
  const query = buildQueryString(params);
  return fetchJson<BranchLookupResponse>(
    `/api/projects/${projectId}/scopes/${encodeURIComponent(scopeRef)}/lookup?${query}`,
  );
}
```

Add `lookupBranch`:

```typescript
export function lookupBranch(
  projectId: number,
  branchRef: string,
  params: {
    business_key?: string;
    source?: string;
  },
) {
  const query = buildQueryString(params);
  return fetchJson<BranchLookupResponse>(
    `/api/projects/${projectId}/branches/${encodeURIComponent(branchRef)}/lookup?${query}`,
  );
}
```

- [ ] **Step 2: Update BranchOpsPage imports**

In `frontend/src/pages/branches/BranchOpsPage.tsx`, update imports:

```typescript
import {
  deleteBranchBusinessKeys,
  executeBranchReplace,
  getBranchRows,
  getSameSourceCandidates,
  getScopeRows,
  lookupBranch,
  lookupScope,
  previewBranchReplace,
  runBranchMutation,
} from "@/domains/branches/api";
```

Remove the `MasterQueryRow` import from the types import. Replace with `BranchLookupResponse`:

```typescript
import type {
  BranchReplacePreview,
  SameSourceCandidateRow,
} from "@/domains/branches/types";
```

- [ ] **Step 3: Update branchRowsQuery to route based on scopeRef**

In BranchOpsPage, change the `branchRowsQuery` (around line 157) to call the right API:

```typescript
const branchRowsQuery = useQuery({
  queryKey:
    projectId && shell.lang
      ? queryKeys.branchRows(projectId, scopeRef, {
          search_business_key: scopeSearchKey,
          search_source: scopeSearchSource,
          page: scopePage,
        })
      : ["branch-rows", "idle"],
  queryFn: () => {
    const params = {
      search_business_key: scopeSearchKey || undefined,
      search_source: scopeSearchSource || undefined,
      page: scopePage,
      page_size: PAGE_SIZE,
    };
    if (scopeRef === "master" || scopeRef === "orphan") {
      return getScopeRows(projectId!, scopeRef, params);
    }
    return getBranchRows(projectId!, scopeRef, params);
  },
  enabled: Boolean(projectId && shell.lang),
});
```

- [ ] **Step 4: Rename `lookupScopeRef` to `lookupRef` and update lookup query**

Rename state variable:
```typescript
const [lookupRef, setLookupRef] = useState("master");
```

Update the lookupQuery (around line 196) to route based on ref:

```typescript
const lookupQuery = useQuery({
  queryKey:
    projectId && lookupRequest
      ? queryKeys.branchLookup(projectId, lookupRequest.scopeRef, {
          [lookupRequest.mode === "key" ? "business_key" : "source"]:
            lookupRequest.value,
        })
      : ["branch-lookup", "idle"],
  queryFn: async () => {
    if (!projectId || !lookupRequest) {
      return { rows: [] as Array<Record<string, unknown>> };
    }
    const params = {
      business_key:
        lookupRequest.mode === "key" ? lookupRequest.value : undefined,
      source: lookupRequest.mode === "source" ? lookupRequest.value : undefined,
    };
    const ref = lookupRequest.scopeRef;
    const payload =
      ref === "master" || ref === "orphan"
        ? await lookupScope(projectId, ref, params)
        : await lookupBranch(projectId, ref, params);
    return {
      rows: payload.rows.map((row) => ({
        business_key: row.business_key,
        scope_ref: payload.branch_ref,
        variant_id: row.variant_id,
        file_name: row.file_name,
        source: row.source,
        translations: row.translations,
        remarks: row.remarks,
      })),
    };
  },
  enabled: Boolean(projectId && lookupRequest),
});
```

Update all references from `lookupScopeRef` to `lookupRef` throughout the file (in the useEffect on line 119-123, in the LookupTab props, etc.).

- [ ] **Step 5: Update LookupTab prop types**

Change the `lookupScopeRef` prop name to `lookupRef` in the LookupTab component and all its references.

- [ ] **Step 6: Build and verify**

Run: `npm run build:app`

Expected: Build succeeds.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/domains/branches/api.ts frontend/src/pages/branches/BranchOpsPage.tsx
git commit -m "feat: switch frontend from scope API calls to branch routes"
```

---

### Task 9: Update documentation

**Files:**
- Modify: `docs/contracts.md`
- Modify: `docs/workflows.md`
- Modify: `docs/system.md`
- Modify: `design/branch-infra-phase-map.md`

- [ ] **Step 1: Update `docs/contracts.md`**

Changes to make:

1. Remove `POST /api/projects/{project_id}/variants/trash/restore` from the HTTP route inventory under "Workflow actions"
2. Remove the two legacy master routes from "Branch read models":
   - `GET /api/projects/{project_id}/branches/master/entries/{business_key}`
   - `GET /api/projects/{project_id}/branches/master/search`
3. Add `compatibility alias` notes on scope routes to specify they only accept `master` and `orphan`
4. Remove `MasterEntryResponse`, `MasterSearchResponse` references
5. Remove `ScopeRowsResponse`, `ScopeLookupResponse` references
6. Update "Scope catalog reads" section to note scope routes only accept `master` and `orphan`, and return `BranchRowsResponse`/`BranchLookupResponse`
7. Remove the "Scope lookup" paragraph about `legacy GET /api/projects/{project_id}/branches/master/entries/{business_key}` and `.../master/search` transition routes
8. In "Frontend and Backend Contract" section, change "the live frontend still uses the scope-aware compatibility aliases" to say the frontend uses canonical branch routes for branch reads and scope routes for master/orphan
9. Remove `trash_until` and `restored_at` from all response descriptions (if mentioned in variant row descriptions)
10. Update schema version reference from `variant-v10` to `variant-v11`
11. Remove "compatibility alias" and "scope-aware" wording that described the now-removed branch-ref scope aliases

- [ ] **Step 2: Update `docs/workflows.md`**

1. Change line 3 from "trash or restore workflows" to "trash workflows"
2. Change `trash.py` reference in the workflows location line
3. Change "TrashRestoreService" references to "TrashService" if present
4. Remove the phrase "(restore removed; trash-only)" — just say "trash workflows"

- [ ] **Step 3: Update `docs/system.md`**

1. Update schema version from `variant-v10` to `variant-v11`
2. No other changes needed — `trash_until` and `restored_at` are not mentioned in the variant description there

- [ ] **Step 4: Update `design/branch-infra-phase-map.md`**

Mark Phase 9 as complete:

```markdown
### Phase 9: Contract Convergence

Status:

- complete

Goal:

- converge code, docs, frontend, and compatibility layers onto the intended long-term shape

Completed decisions:

- scope routes narrowed to master and orphan only; branch-ref scope aliases removed
- legacy master routes removed
- ScopeRowsResponse and ScopeLookupResponse unified into BranchRowsResponse and BranchLookupResponse
- frontend switched from scope-aware API calls to canonical branch routes
- all restore artifacts removed: frontend UI, API function, docs, backend dead code, DB columns
- trash_until and restored_at columns dropped; schema bumped to variant-v11
- TrashRestoreService renamed to TrashService

Artifacts:

- [phase-9-contract-convergence-design.md](phase-9-contract-convergence-design.md): Phase 9 design spec
- [phase-9-contract-convergence-implementation-plan.md](phase-9-contract-convergence-implementation-plan.md): implementation plan
```

Update "Current Status" to say Phase 1 through Phase 9 are complete.

Update "Suggested Next Session" to reflect post-Phase-9 state. Remove the Phase 9 suggestion. The remaining open items from the phase map are Phase 7 (pivot workflow) completion.

Update the memory hook:

```
Phase 1 through Phase 9 are done; pivot workflow and preview (Phase 7) remain partially open.
```

- [ ] **Step 5: Run docs validator**

Run: `.\.venv\Scripts\python.exe scripts\validate_docs.py`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add docs/contracts.md docs/workflows.md docs/system.md design/branch-infra-phase-map.md
git commit -m "docs: update active docs and phase map for Phase 9 contract convergence"
```

---

### Task 10: Final verification

**Files:** None (verification only)

- [ ] **Step 1: Run full backend test suite**

Run: `.\.venv\Scripts\python.exe -m pytest -q`

Expected: PASS

- [ ] **Step 2: Build frontend**

Run: `npm run build:app`

Expected: Build succeeds.

- [ ] **Step 3: Run docs validator**

Run: `.\.venv\Scripts\python.exe scripts\validate_docs.py`

Expected: PASS

- [ ] **Step 4: Run end-to-end tests if available**

Run: `npm run test:e2e`

Expected: PASS (or note what wasn't run and why)

- [ ] **Step 5: Verify no remaining restore references**

Search for any remaining `restore` references that should have been removed:

```bash
grep -rn "restoreVariants\|restore_if_trashed\|trash_until\|restored_at" app/ frontend/src/ tests/ --include="*.py" --include="*.ts" --include="*.tsx"
```

Expected: No matches in code files (static build output under `app/static/` is stale and will be rebuilt).

- [ ] **Step 6: Verify scope routes reject branch refs**

Start the dev server and manually verify:
- `GET /api/projects/1/scopes/rel/current/rows` returns 400
- `GET /api/projects/1/scopes/master/rows` returns 200 with `branch_ref: "master"`
- `GET /api/projects/1/branches/rel/current/rows` returns 200 with `branch_ref: "rel/current"`
