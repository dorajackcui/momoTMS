# Phase 5.5: Legacy Naming Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rename legacy `scope`-based method names and identifiers in service-layer, frontend, and schema surfaces to align with branch-first terminology.

**Architecture:** Pure mechanical renames across four layers — backend service methods, schema classes, frontend query helpers, and tests. Internal binding store/repository classes are unchanged. No semantic or behavioral changes.

**Tech Stack:** Python (FastAPI, SQLite), TypeScript (React, TanStack Query)

**Design spec:** `design/archive/phase-5.5-legacy-naming-cleanup-design.md`

---

### Task 1: Rename BindingCommandService methods

**Files:**
- Modify: `app/services/variant/bindings.py:581-640`

- [ ] **Step 1: Rename `bind_scope` to `bind`**

In `app/services/variant/bindings.py`, rename the method definition at line 599:

```python
# BEFORE (line 599)
    def bind_scope(
        self,
        entry_id: int,
        scope_ref: Any,
        variant_id: int,
        conn: sqlite3.Connection | None = None,
        timestamp: str | None = None,
    ) -> None:

# AFTER
    def bind(
        self,
        entry_id: int,
        scope_ref: Any,
        variant_id: int,
        conn: sqlite3.Connection | None = None,
        timestamp: str | None = None,
    ) -> None:
```

- [ ] **Step 2: Rename `clear_scope_bindings` to `clear_bindings`**

In `app/services/variant/bindings.py`, rename the method definition at line 581:

```python
# BEFORE (line 581)
    def clear_scope_bindings(

# AFTER
    def clear_bindings(
```

- [ ] **Step 3: Rename `remove_scope_binding_rows` to `remove_binding_rows`**

In `app/services/variant/bindings.py`, rename the method definition at line 590:

```python
# BEFORE (line 590)
    def remove_scope_binding_rows(

# AFTER
    def remove_binding_rows(
```

- [ ] **Step 4: Rename `remove_scope_bindings` to `remove_bindings`**

In `app/services/variant/bindings.py`, rename the method definition at line 627. Also update the internal self-call at line 639:

```python
# BEFORE (line 627)
    def remove_scope_bindings(
        ...
            removed.extend(self.remove_scope_binding_rows(project_id, scope_type, scope_values, conn=conn))

# AFTER
    def remove_bindings(
        ...
            removed.extend(self.remove_binding_rows(project_id, scope_type, scope_values, conn=conn))
```

---

### Task 2: Rename VariantStateCoordinator methods

**Files:**
- Modify: `app/services/variant/state_coordinator.py:36-86`

- [ ] **Step 1: Rename `bind_scope` to `bind`**

In `app/services/variant/state_coordinator.py`, rename the method definition at line 36, and update the internal delegation call at line 46:

```python
# BEFORE (line 36)
    def bind_scope(
        ...
        self._binding_commands.bind_scope(entry_id, scope_ref, variant_id, conn=conn, timestamp=marker)

# AFTER
    def bind(
        ...
        self._binding_commands.bind(entry_id, scope_ref, variant_id, conn=conn, timestamp=marker)
```

- [ ] **Step 2: Update `clear_scope` to call renamed method**

In `app/services/variant/state_coordinator.py`, update the internal call at line 66:

```python
# BEFORE (line 66)
        removed = self._binding_commands.clear_scope_bindings(project_id, scope_type, scope_value)

# AFTER
        removed = self._binding_commands.clear_bindings(project_id, scope_type, scope_value)
```

- [ ] **Step 3: Rename `remove_scope_bindings` to `remove_bindings`**

In `app/services/variant/state_coordinator.py`, rename the method definition at line 70, and update the internal call at line 82:

```python
# BEFORE (line 70)
    def remove_scope_bindings(
        ...
            removed.extend(self._binding_commands.remove_scope_binding_rows(project_id, scope_type, scope_values, conn=conn))

# AFTER
    def remove_bindings(
        ...
            removed.extend(self._binding_commands.remove_binding_rows(project_id, scope_type, scope_values, conn=conn))
```

---

### Task 3: Update branch service callers

**Files:**
- Modify: `app/services/branch/bootstrap.py` (lines 401, 432)
- Modify: `app/services/branch/direct_mutation.py` (lines 296, 342, 368, 391)
- Modify: `app/services/branch/import_batch_mutation.py` (lines 252, 293, 320, 354)
- Modify: `app/services/branch/replace.py` (lines 62, 80, 115, 128)
- Modify: `app/services/demo/service.py` (lines 97, 99)

- [ ] **Step 1: Update bootstrap.py**

Replace all `bind_scope(` calls with `bind(` at lines 401 and 432:

```python
# BEFORE
self.bindings.bind_scope(

# AFTER
self.bindings.bind(
```

- [ ] **Step 2: Update direct_mutation.py**

Replace all `bind_scope(` calls with `bind(` at lines 296, 342, 368, 391:

```python
# BEFORE
self.bindings.bind_scope(entry_id, branch_ref, variant_id, conn=conn)
self.bindings.bind_scope(entry_id, branch_ref, target_variant_id, conn=conn)

# AFTER
self.bindings.bind(entry_id, branch_ref, variant_id, conn=conn)
self.bindings.bind(entry_id, branch_ref, target_variant_id, conn=conn)
```

- [ ] **Step 3: Update import_batch_mutation.py**

Replace all `bind_scope(` calls with `bind(` at lines 252, 293, 320, 354:

```python
# BEFORE
self.bindings.bind_scope(

# AFTER
self.bindings.bind(
```

- [ ] **Step 4: Update replace.py**

Three renames in `app/services/branch/replace.py`:

At line 62, `clear_scope_bindings` → `clear_bindings`:
```python
# BEFORE
removed_target_bindings = self.binding_commands.clear_scope_bindings(

# AFTER
removed_target_bindings = self.binding_commands.clear_bindings(
```

At line 80, `_cleanup_scope_bindings` → `_cleanup_bindings`:
```python
# BEFORE
removed_binding_rows = self._cleanup_scope_bindings(cleanup_branch_refs, project_id, conn)

# AFTER
removed_binding_rows = self._cleanup_bindings(cleanup_branch_refs, project_id, conn)
```

At line 115, rename the method definition:
```python
# BEFORE
    def _cleanup_scope_bindings(

# AFTER
    def _cleanup_bindings(
```

At line 128, `remove_scope_binding_rows` → `remove_binding_rows`:
```python
# BEFORE
                self.binding_commands.remove_scope_binding_rows(

# AFTER
                self.binding_commands.remove_binding_rows(
```

- [ ] **Step 5: Update demo/service.py**

Replace all `bind_scope(` calls with `bind(` at lines 97 and 99:

```python
# BEFORE
self.binding_commands.bind_scope(

# AFTER
self.binding_commands.bind(
```

- [ ] **Step 6: Run backend tests to verify renames**

Run:
```
.venv/Scripts/python.exe -m pytest -q
```

Expected: all tests pass (no behavioral changes).

---

### Task 4: Rename PivotReviewService methods and summary key

**Files:**
- Modify: `app/services/workflows/pivot_review.py` (lines 62, 107, 113)

- [ ] **Step 1: Rename method definition**

At line 113:
```python
# BEFORE
    def _variant_visible_in_scope(

# AFTER
    def _variant_visible_in_branch(
```

- [ ] **Step 2: Update call site**

At line 62:
```python
# BEFORE
                if not self._variant_visible_in_scope(int(entry["entry_id"]), variant_id, branch_ref, conn=conn):

# AFTER
                if not self._variant_visible_in_branch(int(entry["entry_id"]), variant_id, branch_ref, conn=conn):
```

- [ ] **Step 3: Rename summary key**

At line 107:
```python
# BEFORE
            "not_visible_in_scope_count": not_visible_count,

# AFTER
            "not_visible_in_branch_count": not_visible_count,
```

---

### Task 5: Rename ScopedTrashDeleteRequest

**Files:**
- Modify: `app/schemas.py` (line 425)
- Modify: `app/routers/workflows.py` (lines 19, 126)

- [ ] **Step 1: Rename class in schemas.py**

At line 425:
```python
# BEFORE
class ScopedTrashDeleteRequest(BaseModel):

# AFTER
class BranchTrashDeleteRequest(BaseModel):
```

- [ ] **Step 2: Update import in workflows.py**

At line 19:
```python
# BEFORE
    ScopedTrashDeleteRequest,

# AFTER
    BranchTrashDeleteRequest,
```

- [ ] **Step 3: Update parameter type in workflows.py**

At line 126:
```python
# BEFORE
def project_trash_delete(project_id: int, payload: ScopedTrashDeleteRequest) -> JobDetail:

# AFTER
def project_trash_delete(project_id: int, payload: BranchTrashDeleteRequest) -> JobDetail:
```

---

### Task 6: Rename frontend query keys and invalidation helper

**Files:**
- Modify: `frontend/src/shared/api/queryKeys.ts`

- [ ] **Step 1: Rename `scopeRows` to `branchRows`**

At lines 10-14:
```typescript
// BEFORE
  scopeRows: (
    projectId: number,
    scopeRef: string,
    params: Record<string, unknown>,
  ) => ["scope-rows", projectId, scopeRef, params] as const,

// AFTER
  branchRows: (
    projectId: number,
    scopeRef: string,
    params: Record<string, unknown>,
  ) => ["branch-rows", projectId, scopeRef, params] as const,
```

- [ ] **Step 2: Rename `scopeLookup` to `branchLookup`**

At lines 15-19:
```typescript
// BEFORE
  scopeLookup: (
    projectId: number,
    scopeRef: string,
    params: Record<string, unknown>,
  ) => ["scope-lookup", projectId, scopeRef, params] as const,

// AFTER
  branchLookup: (
    projectId: number,
    scopeRef: string,
    params: Record<string, unknown>,
  ) => ["branch-lookup", projectId, scopeRef, params] as const,
```

- [ ] **Step 3: Rename `invalidateProjectScope` to `invalidateProject`**

At line 39, rename function declaration:
```typescript
// BEFORE
export async function invalidateProjectScope(

// AFTER
export async function invalidateProject(
```

Also update the cache key strings inside the function body at lines 55-56:
```typescript
// BEFORE
    queryClient.invalidateQueries({ queryKey: ["scope-rows", projectId] }),
    queryClient.invalidateQueries({ queryKey: ["scope-lookup", projectId] }),

// AFTER
    queryClient.invalidateQueries({ queryKey: ["branch-rows", projectId] }),
    queryClient.invalidateQueries({ queryKey: ["branch-lookup", projectId] }),
```

---

### Task 7: Update frontend pages to use renamed exports

**Files:**
- Modify: `frontend/src/pages/branches/BranchOpsPage.tsx` (lines 24, 160, 163, 168, 202, 206, 279, 337-340)
- Modify: `frontend/src/pages/variants/VariantsPage.tsx` (lines 14, 111, 130)
- Modify: `frontend/src/pages/intake/IntakePage.tsx` (lines 19, 115)
- Modify: `frontend/src/pages/runs/RunsPage.tsx` (lines 9, 55)
- Modify: `frontend/src/features/variant-drawer/VariantDrawer.tsx` (lines 6, 43)
- Modify: `frontend/src/app/shell/AppShell.tsx` (line 48)

- [ ] **Step 1: Update BranchOpsPage.tsx**

At line 24, update import:
```typescript
// BEFORE
import { invalidateProjectScope, queryKeys } from "@/shared/api/queryKeys";

// AFTER
import { invalidateProject, queryKeys } from "@/shared/api/queryKeys";
```

At line 160, rename variable `scopeRowsQuery` → `branchRowsQuery`:
```typescript
// BEFORE
  const scopeRowsQuery = useQuery({

// AFTER
  const branchRowsQuery = useQuery({
```

At line 163, update query key call:
```typescript
// BEFORE
        ? queryKeys.scopeRows(projectId, scopeRef, {

// AFTER
        ? queryKeys.branchRows(projectId, scopeRef, {
```

At line 168, update idle key:
```typescript
// BEFORE
        : ["scope-rows", "idle"],

// AFTER
        : ["branch-rows", "idle"],
```

At line 202, update lookup query key:
```typescript
// BEFORE
        ? queryKeys.scopeLookup(projectId, lookupRequest.scopeRef, {

// AFTER
        ? queryKeys.branchLookup(projectId, lookupRequest.scopeRef, {
```

At line 206, update idle key:
```typescript
// BEFORE
        : ["scope-lookup", "idle"],

// AFTER
        : ["branch-lookup", "idle"],
```

At line 279, update invalidation call:
```typescript
// BEFORE
      await invalidateProjectScope(queryClient, projectId, {

// AFTER
      await invalidateProject(queryClient, projectId, {
```

At lines 337-340, update all `scopeRowsQuery` references to `branchRowsQuery`:
```typescript
// BEFORE
          rows={scopeRowsQuery.data?.rows || []}
          totalRows={scopeRowsQuery.data?.total_rows || 0}
          ...
          error={scopeRowsQuery.error instanceof Error ? scopeRowsQuery.error.message : null}

// AFTER
          rows={branchRowsQuery.data?.rows || []}
          totalRows={branchRowsQuery.data?.total_rows || 0}
          ...
          error={branchRowsQuery.error instanceof Error ? branchRowsQuery.error.message : null}
```

- [ ] **Step 2: Update VariantsPage.tsx**

At line 14, update import:
```typescript
// BEFORE
import { invalidateProjectScope, queryKeys } from "@/shared/api/queryKeys";

// AFTER
import { invalidateProject, queryKeys } from "@/shared/api/queryKeys";
```

At lines 111 and 130, update calls:
```typescript
// BEFORE
      await invalidateProjectScope(queryClient, shell.projectId, {

// AFTER
      await invalidateProject(queryClient, shell.projectId, {
```

- [ ] **Step 3: Update IntakePage.tsx**

At line 19, update import:
```typescript
// BEFORE
import { invalidateProjectScope, queryKeys } from "@/shared/api/queryKeys";

// AFTER
import { invalidateProject, queryKeys } from "@/shared/api/queryKeys";
```

At line 115, update call:
```typescript
// BEFORE
      await invalidateProjectScope(queryClient, shell.projectId);

// AFTER
      await invalidateProject(queryClient, shell.projectId);
```

- [ ] **Step 4: Update RunsPage.tsx**

At line 9, update import:
```typescript
// BEFORE
import { invalidateProjectScope, queryKeys } from "@/shared/api/queryKeys";

// AFTER
import { invalidateProject, queryKeys } from "@/shared/api/queryKeys";
```

At line 55, update call:
```typescript
// BEFORE
      await invalidateProjectScope(queryClient, shell.projectId, {

// AFTER
      await invalidateProject(queryClient, shell.projectId, {
```

- [ ] **Step 5: Update VariantDrawer.tsx**

At line 6, update import:
```typescript
// BEFORE
import { invalidateProjectScope, queryKeys } from "@/shared/api/queryKeys";

// AFTER
import { invalidateProject, queryKeys } from "@/shared/api/queryKeys";
```

At line 43, update call:
```typescript
// BEFORE
      await invalidateProjectScope(queryClient, props.projectId, {

// AFTER
      await invalidateProject(queryClient, props.projectId, {
```

- [ ] **Step 6: Update AppShell.tsx hint text**

At line 48:
```typescript
// BEFORE
    hint: "Scope catalog, lookup, apply, replace, and trash flows.",

// AFTER
    hint: "Branch catalog, lookup, apply, replace, and trash flows.",
```

- [ ] **Step 7: Build frontend to verify**

Run:
```
npm run build:app
```

Expected: build succeeds with no errors.

---

### Task 8: Update test files

**Files:**
- Modify: `tests/test_branch_service.py`
- Modify: `tests/test_io_flows.py`
- Modify: `tests/test_variant_api.py`
- Modify: `tests/test_variant_refactor_services.py`
- Modify: `tests/test_variant_pivot.py`

- [ ] **Step 1: Update test_branch_service.py — `bind_scope` → `bind`**

Replace all `bind_scope(` with `bind(` across all call sites. There are approximately 25 direct call sites plus 4 monkeypatch references.

Monkeypatch references need special attention:

At line 459:
```python
# BEFORE
    original_bind_scope = mutation_service.bindings.bind_scope

# AFTER
    original_bind = mutation_service.bindings.bind
```

At line 466:
```python
# BEFORE
        return original_bind_scope(*args, **kwargs)

# AFTER
        return original_bind(*args, **kwargs)
```

At line 468:
```python
# BEFORE
    monkeypatch.setattr(mutation_service.bindings, "bind_scope", fail_on_second_bind)

# AFTER
    monkeypatch.setattr(mutation_service.bindings, "bind", fail_on_second_bind)
```

At lines 504, 511, 513 — same pattern as above (second monkeypatch block):
```python
# BEFORE
    original_bind_scope = mutation_service.bindings.bind_scope
        return original_bind_scope(*args, **kwargs)
    monkeypatch.setattr(mutation_service.bindings, "bind_scope", fail_on_second_bind)

# AFTER
    original_bind = mutation_service.bindings.bind
        return original_bind(*args, **kwargs)
    monkeypatch.setattr(mutation_service.bindings, "bind", fail_on_second_bind)
```

At line 440, update the `remove_scope_binding_rows` monkeypatch:
```python
# BEFORE
    monkeypatch.setattr(replace_service.binding_commands, "remove_scope_binding_rows", fail_cleanup)

# AFTER
    monkeypatch.setattr(replace_service.binding_commands, "remove_binding_rows", fail_cleanup)
```

At line 1436, update `remove_scope_bindings` call:
```python
# BEFORE
    services.bindings.remove_scope_bindings([BranchRef.dev("2.4.2")])

# AFTER
    services.bindings.remove_bindings([BranchRef.dev("2.4.2")])
```

All remaining `bind_scope(` occurrences are direct calls — replace with `bind(`:
Lines: 162, 377, 378, 546, 695, 696, 747, 768, 861, 920, 921, 1265, 1277, 1339, 1340, 1390, 1391, 1435, 1489, 1542, 1596, 1597, 1643, 1688, 1728.

- [ ] **Step 2: Update test_io_flows.py**

Replace all `bind_scope(` with `bind(` at lines: 95, 129, 141, 174, 186.

```python
# BEFORE
    read_service.bindings.bind_scope(

# AFTER
    read_service.bindings.bind(
```

- [ ] **Step 3: Update test_variant_api.py**

Replace all `bind_scope(` with `bind(` at lines: 87, 586, 628, 671, 759, 760.

```python
# BEFORE
    services.bindings.bind_scope(
    bindings.bind_scope(

# AFTER
    services.bindings.bind(
    bindings.bind(
```

- [ ] **Step 4: Update test_variant_refactor_services.py**

Replace all `bind_scope(` with `bind(` at lines: 96, 97.

```python
# BEFORE
    bindings.bind_scope(int(entry["entry_id"]), BranchRef.rel_current(), variant_id)
    bindings.bind_scope(int(entry["entry_id"]), BranchRef.dev("2.4.1"), dev_variant_id)

# AFTER
    bindings.bind(int(entry["entry_id"]), BranchRef.rel_current(), variant_id)
    bindings.bind(int(entry["entry_id"]), BranchRef.dev("2.4.1"), dev_variant_id)
```

- [ ] **Step 5: Update test_variant_pivot.py**

Replace `bind_scope(` with `bind(` at line 59:

```python
# BEFORE
        bindings.bind_scope(int(entry["entry_id"]), branch_ref, variant_id)

# AFTER
        bindings.bind(int(entry["entry_id"]), branch_ref, variant_id)
```

- [ ] **Step 6: Run full backend test suite**

Run:
```
.venv/Scripts/python.exe -m pytest -q
```

Expected: all tests pass.

---

### Task 9: Verify and record completion

- [ ] **Step 1: Run docs validator**

Run:
```
.venv/Scripts/python.exe scripts/validate_docs.py
```

Expected: passes. If it flags `not_visible_in_scope_count` or `ScopedTrashDeleteRequest` in docs, update the relevant docs file.

- [ ] **Step 2: Run full backend test suite one final time**

Run:
```
.venv/Scripts/python.exe -m pytest -q
```

Expected: all tests pass.

- [ ] **Step 3: Run frontend build**

Run:
```
npm run build:app
```

Expected: build succeeds.

- [ ] **Step 4: Run architecture tests specifically**

Run:
```
.venv/Scripts/python.exe -m pytest -q tests/test_services_architecture.py -v
```

Expected: all assertions pass. The existing architecture test at line 103 (`assert "scope_bindings" not in registry_lower`) is not affected since we did not rename the internal registry layer.
