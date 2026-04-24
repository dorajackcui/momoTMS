# Phase 8: Lifecycle And Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the variant lifecycle model so branch delete becomes pure unbind (last binding → orphan, not trash), project trash is a separate explicit operation targeting orphans only, trashed variants are completely excluded from fill and read models, and `BranchRef.orphan()` is a readable computed scope.

**Architecture:** The changes touch five layers: (1) BranchRef model gains `orphan()` factory with read-only enforcement, (2) TrashRestoreService.delete becomes pure unbind and a new `project_trash()` method targets orphans, (3) fill and read-model queries exclude trashed variants, (4) `ScopeSelector` and repository gain orphan-scope query path, (5) branch summary adds orphan as pseudo-branch. The restore endpoint and its entire code path are removed.

**Tech Stack:** Python, FastAPI, SQLite, pytest, Pydantic

---

## File Structure

### Files to modify

| File | Responsibility |
|------|---------------|
| `app/services/branch/models.py` | Add `BranchKind.ORPHAN`, `BranchRef.orphan()`, `is_orphan` property |
| `app/services/workflows/trash.py` | Change delete to pure unbind; add `project_trash()` method; remove `restore()` |
| `app/services/variant/lifecycle.py` | Remove `restore_variant()`; remove `trash_variant()` trash_days/trash_until; add simpler `trash_orphan()` |
| `app/services/variant/repositories.py` | Remove `restore_variant()` from `VariantCommandRepository` |
| `app/services/variant/store.py` | Remove `restore_variant()` from `_VariantStore`; simplify `trash_variant()` to not use `trash_until` |
| `app/services/workflows/fill.py` | Remove trashed fallback in `_pick_best_candidate()` |
| `app/services/read_models/repository.py` | Add trashed exclusion to same-source history and fill candidate queries; add orphan scope query path; add entry timeline trashed exclusion |
| `app/services/read_models/selectors.py` | Add orphan scope support to `ScopeSelector` |
| `app/services/read_models/derived/branch_summary.py` | Add orphan as pseudo-branch entry |
| `app/services/workflows/application.py` | Remove `trash_restore()` method; add `project_trash()` method |
| `app/routers/workflows.py` | Remove restore route; add project trash route |
| `app/schemas.py` | Remove `VariantTrashRestoreRequest`; add `ProjectTrashRequest`; update `SameSourceCandidateRow` state literal; update `EffectForecastPreview.workflow_kind` if needed |

### Test files to modify

| File | Changes |
|------|---------|
| `tests/test_branch_service.py` | Update `test_release_hotfix_and_trash_restore_round_trip` to orphan semantics; remove restore tests; add project_trash tests |
| `tests/test_io_flows.py` | Update trashed fill tests to expect SRC_MISMATCH instead of trashed fallback |
| `tests/test_variant_api.py` | Update same-source candidate tests; add orphan scope route tests |

---

### Task 1: BranchRef.orphan() Model Extension

**Files:**
- Modify: `app/services/branch/models.py`
- Test: `tests/test_branch_service.py`

This task adds `BranchKind.ORPHAN` and the `BranchRef.orphan()` class method. The orphan ref is not writable and cannot be used in `as_tuple()` (which feeds scope_bindings writes).

- [ ] **Step 1: Write the failing test for BranchRef.orphan()**

Add to `tests/test_branch_service.py` near the top (after imports):

```python
def test_branch_ref_orphan_factory_and_properties() -> None:
    ref = BranchRef.orphan()
    assert str(ref) == "orphan"
    assert ref.is_orphan is True
    assert ref.is_rel is False
    assert ref.is_dev is False
    assert ref.version is None
    assert ref.version_series is None
    assert ref.version_parts is None


def test_branch_ref_orphan_parse_round_trip() -> None:
    ref = BranchRef.parse("orphan")
    assert ref.is_orphan is True
    assert str(ref) == "orphan"


def test_branch_ref_orphan_as_tuple_raises() -> None:
    ref = BranchRef.orphan()
    with pytest.raises(ValueError, match="orphan branch cannot be used as a scope binding"):
        ref.as_tuple()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_branch_service.py::test_branch_ref_orphan_factory_and_properties tests/test_branch_service.py::test_branch_ref_orphan_parse_round_trip tests/test_branch_service.py::test_branch_ref_orphan_as_tuple_raises -v`

Expected: FAIL — `BranchKind` has no `ORPHAN` member, `BranchRef` has no `orphan()` method.

- [ ] **Step 3: Implement BranchRef.orphan() in models.py**

In `app/services/branch/models.py`, make these changes:

1. Add `ORPHAN = "orphan"` to `BranchKind` enum:

```python
class BranchKind(str, Enum):
    REL = "rel"
    DEV = "dev"
    ORPHAN = "orphan"
```

2. Update `__post_init__` to allow orphan:

```python
def __post_init__(self) -> None:
    normalized_value = normalize_non_content_value(self.branch_value)
    if not normalized_value:
        raise ValueError("branch value is required")
    object.__setattr__(self, "branch_value", normalized_value)
    if self.branch_kind == BranchKind.ORPHAN:
        if normalized_value != "orphan":
            raise ValueError(f"invalid orphan branch: {self}")
        return
    if self.branch_kind == BranchKind.REL:
        if normalized_value != "current":
            raise ValueError(f"invalid release branch: {self}")
        return
    derive_version_series(normalized_value)
```

3. Update `parse()` to handle "orphan":

```python
@classmethod
def parse(cls, branch_ref: str) -> BranchRef:
    if branch_ref.strip() == "orphan":
        return cls.orphan()
    if "/" not in branch_ref:
        raise ValueError(f"invalid branch ref: {branch_ref}")
    branch_kind_raw, branch_value = branch_ref.split("/", 1)
    try:
        branch_kind = BranchKind(branch_kind_raw)
    except ValueError as exc:
        raise ValueError(f"invalid branch ref: {branch_ref}") from exc
    return cls(branch_kind=branch_kind, branch_value=branch_value)
```

4. Add `orphan()` class method:

```python
@classmethod
def orphan(cls) -> BranchRef:
    return cls(branch_kind=BranchKind.ORPHAN, branch_value="orphan")
```

5. Add `is_orphan` property:

```python
@property
def is_orphan(self) -> bool:
    return self.branch_kind == BranchKind.ORPHAN
```

6. Update `as_tuple()` to reject orphan:

```python
def as_tuple(self) -> tuple[str, str]:
    if self.is_orphan:
        raise ValueError("orphan branch cannot be used as a scope binding")
    return self.branch_kind.value, self.branch_value
```

7. Update `__str__()` to return just "orphan":

```python
def __str__(self) -> str:
    if self.is_orphan:
        return "orphan"
    return f"{self.branch_kind.value}/{self.branch_value}"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_branch_service.py::test_branch_ref_orphan_factory_and_properties tests/test_branch_service.py::test_branch_ref_orphan_parse_round_trip tests/test_branch_service.py::test_branch_ref_orphan_as_tuple_raises -v`

Expected: PASS

- [ ] **Step 5: Run the full test suite to check for regressions**

Run: `python -m pytest tests/ -v`

Expected: All existing tests pass. The new `ORPHAN` enum value should not break any existing code paths since `as_tuple()` guards against accidental binding writes.

- [ ] **Step 6: Commit**

```bash
git add app/services/branch/models.py tests/test_branch_service.py
git commit -m "feat: add BranchRef.orphan() with read-only enforcement"
```

---

### Task 2: Branch Delete Becomes Pure Unbind

**Files:**
- Modify: `app/services/workflows/trash.py`
- Test: `tests/test_branch_service.py`

This task changes `TrashRestoreService.delete()` so that when the last binding is removed, the variant becomes orphan instead of trashed. The method stops calling `lifecycle.trash_variant()` and instead lets `lifecycle.refresh_orphan_states()` compute the orphan state.

- [ ] **Step 1: Write the failing test for orphan-on-last-binding**

Add to `tests/test_branch_service.py`:

```python
def test_branch_delete_produces_orphan_instead_of_trashed() -> None:
    sample = reset_demo()
    variant_service = TrashRestoreService()
    inspection = EntryTimelineDataset()

    before = inspection.get("common.welcome")
    target_variant_id = before["variants"][0]["variant_id"]
    assert before["variants"][0]["is_trashed"] is False

    result = variant_service.delete(BranchRef.rel_current(), ["common.welcome"])

    assert result["summary"]["orphaned_variant_count"] == 1
    assert "trashed_variant_count" not in result["summary"]
    orphan_row = next(r for r in result["report_rows"] if r["business_key"] == "common.welcome")
    assert orphan_row["status"] == "ORPHANED_VARIANT"

    after = inspection.get("common.welcome")
    variant_after = next(v for v in after["variants"] if v["variant_id"] == target_variant_id)
    assert variant_after["is_orphaned"] is True
    assert variant_after["is_trashed"] is False
    assert variant_after["trashed_at"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_branch_service.py::test_branch_delete_produces_orphan_instead_of_trashed -v`

Expected: FAIL — current code reports `TRASHED_VARIANT` and `trashed_variant_count`.

- [ ] **Step 3: Modify TrashRestoreService.delete() to pure unbind**

Replace the `delete()` method in `app/services/workflows/trash.py`:

```python
def delete(
    self,
    branch_ref: BranchRef,
    business_keys: list[str],
    project_id: int = DEFAULT_PROJECT_ID,
) -> dict[str, list[dict[str, object]] | dict[str, int]]:
    self.projects.require_project(project_id)
    orphaned_variant_count = 0
    removed_binding_count = 0
    not_bound_count = 0
    missing_count = 0
    report_rows: list[dict[str, object]] = []
    with get_conn() as conn:
        for business_key in normalize_business_keys(business_keys):
            entry = self.entries.get_entry(business_key, project_id=project_id, conn=conn)
            if entry is None:
                missing_count += 1
                report_rows.append({"business_key": business_key, "status": "MISSING"})
                continue
            binding = self.binding_lookup.get_binding(int(entry["entry_id"]), branch_ref, conn=conn)
            if binding is None:
                not_bound_count += 1
                report_rows.append(
                    {
                        "business_key": business_key,
                        "branch_ref": str(branch_ref),
                        "status": "NOT_BOUND_IN_SCOPE",
                    }
                )
                continue
            variant_id = int(binding["variant_id"])
            self.binding_commands.remove_binding(int(entry["entry_id"]), branch_ref, conn=conn)
            self.lifecycle.refresh_orphan_states(int(entry["entry_id"]), conn=conn)
            if self.binding_lookup.count_variant_bindings(variant_id, conn=conn) == 0:
                orphaned_variant_count += 1
                report_rows.append(
                    {
                        "business_key": business_key,
                        "branch_ref": str(branch_ref),
                        "variant_id": variant_id,
                        "status": "ORPHANED_VARIANT",
                    }
                )
            else:
                removed_binding_count += 1
                report_rows.append(
                    {
                        "business_key": business_key,
                        "branch_ref": str(branch_ref),
                        "variant_id": variant_id,
                        "status": "REMOVED_BINDING",
                    }
                )
    summary = {
        "branch_ref": str(branch_ref),
        "orphaned_variant_count": orphaned_variant_count,
        "removed_binding_count": removed_binding_count,
        "not_bound_count": not_bound_count,
        "missing_count": missing_count,
    }
    return {"summary": summary, "report_rows": report_rows}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_branch_service.py::test_branch_delete_produces_orphan_instead_of_trashed -v`

Expected: PASS

- [ ] **Step 5: Update the existing trash-and-restore round-trip test**

Rename `test_release_hotfix_and_trash_restore_round_trip` to `test_release_hotfix_and_branch_delete_produces_orphan` and update it to expect orphan semantics:

```python
def test_release_hotfix_and_branch_delete_produces_orphan() -> None:
    sample = reset_demo()
    mutation_service = BranchMutationService()
    variant_service = TrashRestoreService()

    active = mutation_service.apply(
        BranchRef.rel_current(),
        {
            "kind": "direct",
            "changes": [
                {
                    "business_key": sample["active_hotfix"]["business_key"],
                    "translations_by_lang": {
                        sample["active_hotfix"]["lang"]: sample["active_hotfix"]["target_text"],
                    },
                }
            ],
        },
    )
    assert active["summary"]["updated_bound_variant_count"] == 1

    passive = mutation_service.apply(
        BranchRef.rel_current(),
        {
            "kind": "direct",
            "changes": [
                {
                    "business_key": sample["passive_hotfix"]["business_key"],
                    "source": sample["passive_hotfix"]["source"],
                    "translations_by_lang": sample["passive_hotfix"]["translations_by_lang"],
                    "remarks_by_key": sample["passive_hotfix"]["remarks_by_key"],
                    "file_name": sample["passive_hotfix"]["file_name"],
                }
            ],
        },
    )
    assert passive["report_rows"][0]["status"] in {"CREATED_AND_BOUND_VARIANT", "UPDATED_AND_BOUND_EXISTING_VARIANT"}

    before_delete = EntryTimelineDataset().get("common.welcome")
    target_variant_id = before_delete["variants"][0]["variant_id"]
    delete_result = variant_service.delete(BranchRef.rel_current(), ["common.welcome"])
    assert delete_result["summary"]["orphaned_variant_count"] == 1

    after_delete = EntryTimelineDataset().get("common.welcome")
    orphaned = next(v for v in after_delete["variants"] if v["variant_id"] == target_variant_id)
    assert orphaned["is_orphaned"] is True
    assert orphaned["is_trashed"] is False
```

- [ ] **Step 6: Update the delete rollback test**

Update `test_delete_rolls_back_on_failure` — instead of monkeypatching `trash_variant`, monkeypatch `refresh_orphan_states`:

```python
def test_delete_rolls_back_on_failure(monkeypatch) -> None:
    reset_demo()
    variant_service = TrashRestoreService()
    read_service = branch_services()

    def fail_refresh(*args, **kwargs):
        raise RuntimeError("delete refresh failed")

    monkeypatch.setattr(variant_service.lifecycle, "refresh_orphan_states", fail_refresh)

    with pytest.raises(RuntimeError, match="delete refresh failed"):
        variant_service.delete(BranchRef.rel_current(), ["common.welcome"])

    rel_keys = {item["business_key"] for item in read_service.list_branch_entries(BranchRef.rel_current())}
    assert "common.welcome" in rel_keys
```

- [ ] **Step 7: Run all modified tests**

Run: `python -m pytest tests/test_branch_service.py::test_branch_delete_produces_orphan_instead_of_trashed tests/test_branch_service.py::test_release_hotfix_and_branch_delete_produces_orphan tests/test_branch_service.py::test_delete_rolls_back_on_failure -v`

Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add app/services/workflows/trash.py tests/test_branch_service.py
git commit -m "feat: branch delete produces orphan instead of trash on last binding removal"
```

---

### Task 3: Add Project Trash Operation

**Files:**
- Modify: `app/services/workflows/trash.py`
- Modify: `app/services/variant/lifecycle.py`
- Modify: `app/services/workflows/application.py`
- Modify: `app/routers/workflows.py`
- Modify: `app/schemas.py`
- Test: `tests/test_branch_service.py`

This task adds the new `project_trash()` method that targets orphan variants by business_keys and the corresponding API route.

- [ ] **Step 1: Write the failing test for project_trash**

Add to `tests/test_branch_service.py`:

```python
def test_project_trash_trashes_orphan_variants_only() -> None:
    reset_demo()
    read_service = branch_services()
    variant_service = TrashRestoreService()

    variant_service.delete(BranchRef.rel_current(), ["common.welcome"])

    result = variant_service.project_trash(["common.welcome"])

    assert result["summary"]["trashed_count"] == 1
    assert result["summary"]["not_orphan_count"] == 0
    assert result["summary"]["no_orphan_found_count"] == 0
    assert result["summary"]["missing_count"] == 0

    trashed_row = next(r for r in result["report_rows"] if r["business_key"] == "common.welcome")
    assert trashed_row["status"] == "TRASHED"

    after = EntryTimelineDataset().get("common.welcome")
    variant = next(v for v in after["variants"] if v["variant_id"] == trashed_row["variant_id"])
    assert variant["is_trashed"] is True


def test_project_trash_rejects_active_variants() -> None:
    reset_demo()
    variant_service = TrashRestoreService()

    result = variant_service.project_trash(["common.welcome"])

    assert result["summary"]["not_orphan_count"] == 1
    assert result["summary"]["trashed_count"] == 0
    active_row = next(r for r in result["report_rows"] if r["business_key"] == "common.welcome")
    assert active_row["status"] == "NOT_ORPHAN"


def test_project_trash_reports_missing_keys() -> None:
    reset_demo()
    variant_service = TrashRestoreService()

    result = variant_service.project_trash(["nonexistent.key"])

    assert result["summary"]["missing_count"] == 1
    assert result["report_rows"][0]["status"] == "MISSING"


def test_project_trash_reports_no_orphan_found_when_entry_has_no_orphans() -> None:
    reset_demo()
    variant_service = TrashRestoreService()

    result = variant_service.project_trash(["common.welcome"])

    no_orphan_row = next(r for r in result["report_rows"] if r["business_key"] == "common.welcome")
    assert no_orphan_row["status"] == "NOT_ORPHAN"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_branch_service.py::test_project_trash_trashes_orphan_variants_only tests/test_branch_service.py::test_project_trash_rejects_active_variants tests/test_branch_service.py::test_project_trash_reports_missing_keys tests/test_branch_service.py::test_project_trash_reports_no_orphan_found_when_entry_has_no_orphans -v`

Expected: FAIL — `project_trash` method doesn't exist.

- [ ] **Step 3: Add trash_orphan() to VariantLifecycleService**

In `app/services/variant/lifecycle.py`, add a new method that simply sets `trashed_at` without `trash_until`:

```python
def trash_orphan(
    self,
    variant_id: int,
    entry_id: int,
    conn: sqlite3.Connection | None = None,
    timestamp: str | None = None,
) -> None:
    marker = timestamp or now_iso()
    self._variant_commands.trash_variant(variant_id, marker, "", conn=conn)
    self.refresh_orphan_states(entry_id, conn=conn, timestamp=marker)
```

Note: We pass an empty string for `trash_until` since we no longer use time-based cleanup. The `trash_until` column remains in the schema but becomes unused.

- [ ] **Step 4: Add project_trash() to TrashRestoreService**

In `app/services/workflows/trash.py`, add the `project_trash()` method:

```python
def project_trash(
    self,
    business_keys: list[str],
    project_id: int = DEFAULT_PROJECT_ID,
) -> dict[str, list[dict[str, object]] | dict[str, int]]:
    self.projects.require_project(project_id)
    trashed_count = 0
    not_orphan_count = 0
    no_orphan_found_count = 0
    missing_count = 0
    report_rows: list[dict[str, object]] = []
    with get_conn() as conn:
        for business_key in normalize_business_keys(business_keys):
            entry = self.entries.get_entry(business_key, project_id=project_id, conn=conn)
            if entry is None:
                missing_count += 1
                report_rows.append({"business_key": business_key, "status": "MISSING"})
                continue
            entry_id = int(entry["entry_id"])
            variants = self.catalog.list_variants(entry_id, include_trashed=False, conn=conn)
            orphans = [
                v for v in variants
                if self.binding_lookup.count_variant_bindings(int(v["variant_id"]), conn=conn) == 0
            ]
            if not orphans:
                has_active = any(
                    self.binding_lookup.count_variant_bindings(int(v["variant_id"]), conn=conn) > 0
                    for v in variants
                )
                if has_active:
                    not_orphan_count += 1
                    report_rows.append({"business_key": business_key, "status": "NOT_ORPHAN"})
                else:
                    no_orphan_found_count += 1
                    report_rows.append({"business_key": business_key, "status": "NO_ORPHAN_FOUND"})
                continue
            for orphan_variant in orphans:
                variant_id = int(orphan_variant["variant_id"])
                self.lifecycle.trash_orphan(variant_id, entry_id, conn=conn)
                trashed_count += 1
                report_rows.append(
                    {
                        "business_key": business_key,
                        "variant_id": variant_id,
                        "status": "TRASHED",
                    }
                )
    summary = {
        "trashed_count": trashed_count,
        "not_orphan_count": not_orphan_count,
        "no_orphan_found_count": no_orphan_found_count,
        "missing_count": missing_count,
    }
    return {"summary": summary, "report_rows": report_rows}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_branch_service.py::test_project_trash_trashes_orphan_variants_only tests/test_branch_service.py::test_project_trash_rejects_active_variants tests/test_branch_service.py::test_project_trash_reports_missing_keys tests/test_branch_service.py::test_project_trash_reports_no_orphan_found_when_entry_has_no_orphans -v`

Expected: PASS

- [ ] **Step 6: Add the ProjectTrashRequest schema**

In `app/schemas.py`, add after `BranchTrashDeleteRequest`:

```python
class ProjectTrashRequest(BaseModel):
    business_keys: list[str]
```

- [ ] **Step 7: Wire up project_trash in WorkflowApplicationService**

In `app/services/workflows/application.py`, add the `project_trash()` method:

```python
def project_trash(
    self,
    business_keys: list[str],
    project_id: int = DEFAULT_PROJECT_ID,
) -> dict[str, Any]:
    return self._run_job(
        "project_trash",
        {"business_keys": business_keys, "project_id": project_id},
        lambda _job_id: self._wrap_report(
            self.trash_restore_service.project_trash(
                business_keys,
                project_id=project_id,
            )
        ),
        project_id=project_id,
    )
```

- [ ] **Step 8: Add the project trash route**

In `app/routers/workflows.py`, add the route (before the restore route, which will be removed in Task 4):

```python
@router.post("/api/projects/{project_id}/variants/trash", response_model=JobDetail)
def project_trash(project_id: int, payload: ProjectTrashRequest) -> JobDetail:
    return handle_errors(
        lambda: JobDetail(
            **WorkflowApplicationService().project_trash(
                payload.business_keys,
                project_id=project_id,
            )
        )
    )
```

Add `ProjectTrashRequest` to the imports from `app.schemas`.

- [ ] **Step 9: Write an API-level test for the project trash route**

Add to `tests/test_variant_api.py`:

```python
def test_project_trash_route_trashes_orphan_variants() -> None:
    reset_demo()
    with TestClient(app) as client:
        delete_response = client.post(
            "/api/projects/1/variants/trash/delete",
            json={"branch_ref": "rel/current", "business_keys": ["common.welcome"]},
        )
        assert delete_response.status_code == 200
        delete_detail = wait_for_job(client, delete_response.json())
        assert delete_detail["job"]["status"] == "success"

        trash_response = client.post(
            "/api/projects/1/variants/trash",
            json={"business_keys": ["common.welcome"]},
        )
        assert trash_response.status_code == 200
        trash_detail = wait_for_job(client, trash_response.json())
        assert trash_detail["job"]["status"] == "success"
        assert trash_detail["report"]["summary"]["trashed_count"] == 1
```

- [ ] **Step 10: Run full test suite**

Run: `python -m pytest tests/ -v`

Expected: PASS (the existing restore tests will fail — we address that in Task 4).

- [ ] **Step 11: Commit**

```bash
git add app/services/variant/lifecycle.py app/services/workflows/trash.py app/services/workflows/application.py app/routers/workflows.py app/schemas.py tests/test_branch_service.py tests/test_variant_api.py
git commit -m "feat: add project trash operation targeting orphan variants only"
```

---

### Task 4: Remove Restore Endpoint And Code

**Files:**
- Modify: `app/services/workflows/trash.py`
- Modify: `app/services/variant/lifecycle.py`
- Modify: `app/services/variant/repositories.py`
- Modify: `app/services/variant/store.py`
- Modify: `app/services/workflows/application.py`
- Modify: `app/routers/workflows.py`
- Modify: `app/schemas.py`
- Test: `tests/test_branch_service.py`

This task removes the restore code path entirely. Trashed is terminal.

- [ ] **Step 1: Remove the restore route from workflows.py**

In `app/routers/workflows.py`, delete the `project_trash_restore` route (lines 139–148) and remove `VariantTrashRestoreRequest` from the schema imports.

- [ ] **Step 2: Remove trash_restore() from WorkflowApplicationService**

In `app/services/workflows/application.py`, delete the `trash_restore()` method.

- [ ] **Step 3: Remove restore() from TrashRestoreService**

In `app/services/workflows/trash.py`, delete the `restore()` method entirely.

- [ ] **Step 4: Remove restore_variant() from VariantLifecycleService**

In `app/services/variant/lifecycle.py`, delete the `restore_variant()` method. Also remove the old `trash_variant()` method with `trash_days`/`trash_until` if it's still present (it should have been superseded by `trash_orphan()` in Task 3, but `trash_variant` is still called by some code paths that we've already removed). Keep `trash_orphan()` and `refresh_orphan_states()`.

Also clean up imports — remove `datetime`, `timedelta`, `timezone` if the `_trash_until()` helper is removed.

- [ ] **Step 5: Remove restore_variant() from VariantCommandRepository**

In `app/services/variant/repositories.py`, delete the `restore_variant()` method.

- [ ] **Step 6: Remove restore_variant() from _VariantStore**

In `app/services/variant/store.py`, find and delete the `restore_variant()` method.

- [ ] **Step 7: Remove VariantTrashRestoreRequest from schemas**

In `app/schemas.py`, delete the `VariantTrashRestoreRequest` class.

- [ ] **Step 8: Remove restore tests from test_branch_service.py**

Delete these test functions:
- `test_restore_rolls_back_on_failure`
- `test_restore_variants_reports_source_conflicts_and_continues`

Any test that calls `variant_service.restore(...)` must be removed or rewritten.

- [ ] **Step 9: Run full test suite to verify clean removal**

Run: `python -m pytest tests/ -v`

Expected: PASS — no remaining references to `restore()`, `restore_variant()`, or `VariantTrashRestoreRequest`.

- [ ] **Step 10: Commit**

```bash
git add app/services/variant/lifecycle.py app/services/variant/repositories.py app/services/variant/store.py app/services/workflows/trash.py app/services/workflows/application.py app/routers/workflows.py app/schemas.py tests/test_branch_service.py
git commit -m "feat: remove restore endpoint and code path — trashed is terminal"
```

---

### Task 5: Fill Excludes Trashed Variants

**Files:**
- Modify: `app/services/read_models/repository.py`
- Modify: `app/services/workflows/fill.py`
- Test: `tests/test_io_flows.py`

This task removes the trashed-variant fallback from fill. Trashed variants are completely excluded from fill candidate lookup.

- [ ] **Step 1: Update the fill candidate query to exclude trashed**

In `app/services/read_models/repository.py`, method `list_fill_candidate_rows()`, add a `WHERE` filter:

Change the query from:
```sql
WHERE e.project_id = ?
```
to:
```sql
WHERE e.project_id = ?
  AND v.trashed_at IS NULL
```

Also remove the `trashed_at` column from the SELECT and the ORDER BY clause that sorts trashed variants last (the `CASE WHEN v.trashed_at IS NULL THEN 0 ELSE 1 END` line), since all results are now non-trashed.

Update the result mapping to no longer include `trashed_at`:

```python
return [
    {
        "business_key": normalize_non_content_value(row["business_key"]),
        "source": normalize_non_content_value(row["source"]),
        "target_text": normalize_content_value(row["target_text"]),
        "variant_id": int(row["variant_id"]),
        "orphaned_at": row["orphaned_at"],
        "trashed_at": None,
        "updated_at": row["updated_at"],
    }
    for row in rows
]
```

Note: Keep `trashed_at` in the dict as `None` for now to maintain the `FillCandidate` type shape. Clean up the type later in Task 9.

- [ ] **Step 2: Remove trashed fallback from FillService._pick_best_candidate()**

In `app/services/workflows/fill.py`, simplify `_pick_best_candidate()`:

```python
def _pick_best_candidate(
    self,
    combined_key: tuple[str, str],
    candidates: list[FillCandidate],
) -> FillCandidate:
    live_candidates = [candidate for candidate in candidates if candidate["trashed_at"] is None]
    if len(live_candidates) > 1:
        raise RuntimeError(
            "duplicate non-trashed fill candidates found for "
            f"business_key={combined_key[0]!r}, source={combined_key[1]!r}"
        )
    if live_candidates:
        return live_candidates[0]
    raise RuntimeError(
        "no live fill candidate found for "
        f"business_key={combined_key[0]!r}, source={combined_key[1]!r}"
    )
```

Wait — since the query now only returns non-trashed rows, `_pick_best_candidate()` will never see trashed candidates. The method can be simplified further, but the guard above is still correct. The `_build_fill_indexes` method calls this only when candidates exist, and since all candidates are live, the check is effectively a duplicate-detection guard.

Actually, since the query already excludes trashed, and we rely on the canonical invariant (one live variant per source per entry), there should be exactly 0 or 1 candidates per combo. The RuntimeError for >1 is a safety net. The fallback to trashed (lines 248–252) should be removed and replaced with a scenario that should never happen:

```python
def _pick_best_candidate(
    self,
    combined_key: tuple[str, str],
    candidates: list[FillCandidate],
) -> FillCandidate:
    if len(candidates) > 1:
        raise RuntimeError(
            "duplicate fill candidates found for "
            f"business_key={combined_key[0]!r}, source={combined_key[1]!r}"
        )
    return candidates[0]
```

- [ ] **Step 3: Simplify _candidate_state() to remove trashed**

In `app/services/workflows/fill.py`, update `_candidate_state()`:

```python
def _candidate_state(self, candidate: FillCandidate) -> str:
    if candidate["orphaned_at"] is not None:
        return "orphan"
    return "active"
```

- [ ] **Step 4: Update fill tests**

In `tests/test_io_flows.py`:

**a)** `test_fill_uses_trashed_candidate_when_no_live_variant_exists` — this test expects trashed fallback. The new behavior is that trashed variants are excluded, so the workbook row should get `SRC_MISMATCH` instead. Rewrite:

```python
def test_fill_excludes_trashed_variant_and_reports_src_mismatch() -> None:
    sample = reset_demo()
    read_service = branch_services()
    variant_service = TrashRestoreService()
    entry = read_service.entries.get_entry("trash.me")
    assert entry is not None
    original_variant = read_service.catalog.list_variants(int(entry["entry_id"]), include_trashed=True)[0]
    read_service.bindings.bind(int(entry["entry_id"]), BranchRef.rel_current(), int(original_variant["variant_id"]))
    variant_service.delete(BranchRef.rel_current(), ["trash.me"])
    variant_service.project_trash(["trash.me"])

    source_dir = Path(sample["paths"]["root"]) / "trashed-only-source"
    write_fill_workbook(
        source_dir,
        "single.xlsx",
        [
            ["file_name", "business_key", "source", "fr", "en", "context"],
            ["trash.xlsx", "trash.me", "Trash me source", "", "", "trashed-only"],
        ],
    )

    result = FillService().fill_and_export(
        str(source_dir),
        str(Path(sample["paths"]["root"]) / "trashed-only.zip"),
        sample["lang"],
    )

    row = report_row_by_key(result["report_rows"], "trash.me")
    assert row["status"] == "SRC_MISMATCH"
```

**b)** `test_fill_prefers_live_candidate_over_trashed_history` — update to use `project_trash()` after delete, and verify only the live candidate is used (same assertion, just add the explicit project_trash step):

```python
def test_fill_uses_live_candidate_and_ignores_trashed_history() -> None:
    sample = reset_demo()
    read_service = branch_services()
    variant_service = TrashRestoreService()
    entry = read_service.entries.get_entry("trash.me")
    assert entry is not None
    entry_id = int(entry["entry_id"])
    original_variant = read_service.catalog.list_variants(entry_id, include_trashed=True)[0]
    read_service.bindings.bind(entry_id, BranchRef.rel_current(), int(original_variant["variant_id"]))
    variant_service.delete(BranchRef.rel_current(), ["trash.me"])
    variant_service.project_trash(["trash.me"])

    live_variant_id = read_service.catalog.create_variant(
        entry_id,
        read_service.catalog.build_content(
            "trash-live.xlsx",
            "Trash me source",
            {"fr": "Live translation wins", "en": "Live translation wins"},
            {"context": "live replacement"},
        ),
    )
    read_service.bindings.bind(entry_id, BranchRef.rel_current(), live_variant_id)

    source_dir = Path(sample["paths"]["root"]) / "prefer-live-source"
    write_fill_workbook(
        source_dir,
        "single.xlsx",
        [
            ["file_name", "business_key", "source", "fr", "en", "context"],
            ["trash.xlsx", "trash.me", "Trash me source", "", "", "prefer-live"],
        ],
    )

    result = FillService().fill_and_export(
        str(source_dir),
        str(Path(sample["paths"]["root"]) / "prefer-live.zip"),
        sample["lang"],
    )

    row = report_row_by_key(result["report_rows"], "trash.me")
    assert row["status"] == "FILLED"
    assert row["match_variant_id"] == live_variant_id
    assert row["match_variant_state"] == "active"
    assert read_target_text(output_workbook_path(source_dir, "single.xlsx")) == "Live translation wins"
```

**c)** `test_fill_uses_latest_trashed_candidate_when_only_trashed_history_exists` — delete this test entirely. The scenario it tests (choosing between multiple trashed candidates) no longer applies since trashed variants are excluded from fill.

- [ ] **Step 5: Run fill tests**

Run: `python -m pytest tests/test_io_flows.py -v`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app/services/read_models/repository.py app/services/workflows/fill.py tests/test_io_flows.py
git commit -m "feat: exclude trashed variants from fill completely — no fallback"
```

---

### Task 6: Same-Source History And Entry Timeline Exclude Trashed

**Files:**
- Modify: `app/services/read_models/repository.py`
- Modify: `app/schemas.py`
- Test: `tests/test_variant_api.py`

This task adds `WHERE v.trashed_at IS NULL` to same-source candidate lookup and entry timeline queries.

- [ ] **Step 1: Write the failing test for same-source excluding trashed**

Add to `tests/test_variant_api.py`:

```python
def test_same_source_candidates_exclude_trashed_variants() -> None:
    reset_demo()
    variant_service = TrashRestoreService()
    inspection = EntryTimelineDataset()

    before = inspection.get("common.welcome")
    target_variant = before["variants"][0]

    variant_service.delete(BranchRef.rel_current(), ["common.welcome"])
    variant_service.project_trash(["common.welcome"])

    with TestClient(app) as client:
        response = client.get(
            "/api/projects/1/scopes/history/same-source",
            params={"business_key": "common.welcome", "source": target_variant["source"]},
        )
        assert response.status_code == 200
        rows = response.json()["rows"]
        assert all(row["state"] != "trashed" for row in rows)
```

- [ ] **Step 2: Write the failing test for entry timeline excluding trashed**

Add to `tests/test_variant_api.py`:

```python
def test_entry_timeline_excludes_trashed_variants() -> None:
    reset_demo()
    variant_service = TrashRestoreService()

    variant_service.delete(BranchRef.rel_current(), ["common.welcome"])
    variant_service.project_trash(["common.welcome"])

    with TestClient(app) as client:
        response = client.get("/api/projects/1/entries/common.welcome/variants")
        assert response.status_code == 200
        variants = response.json()["variants"]
        assert all(v["is_trashed"] is False for v in variants)
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `python -m pytest tests/test_variant_api.py::test_same_source_candidates_exclude_trashed_variants tests/test_variant_api.py::test_entry_timeline_excludes_trashed_variants -v`

Expected: FAIL — current queries include trashed variants.

- [ ] **Step 4: Add trashed exclusion to same-source history query**

In `app/services/read_models/repository.py`, method `list_same_source_history_rows()`, add to the WHERE clause:

Change:
```sql
WHERE e.project_id = ?
  AND e.business_key = ?
  AND v.source = ?
```
to:
```sql
WHERE e.project_id = ?
  AND e.business_key = ?
  AND v.source = ?
  AND v.trashed_at IS NULL
```

Also remove the ORDER BY clause that sorted trashed variants last:
```sql
CASE WHEN v.trashed_at IS NULL THEN 0 ELSE 1 END,
```

- [ ] **Step 5: Add trashed exclusion to entry timeline query**

In `app/services/read_models/repository.py`, method `get_entry_timeline()`, add to the variants_query WHERE clause:

Change:
```sql
WHERE e.project_id = ? AND e.business_key = ?
```
to:
```sql
WHERE e.project_id = ? AND e.business_key = ? AND v.trashed_at IS NULL
```

- [ ] **Step 6: Update SameSourceCandidateRow schema**

In `app/schemas.py`, update `SameSourceCandidateRow` state literal to remove "trashed":

```python
state: Literal["active", "orphan"]
```

Also remove the `trashed_at`, `trash_until`, and `restored_at` fields from `SameSourceCandidateRow` since the query no longer returns trashed variants. Keep the `orphaned_at` field.

- [ ] **Step 7: Update existing same-source test**

In `tests/test_variant_api.py`, find `test_scope_history_same_source_candidates_prioritize_live_before_trashed` and rename/update to confirm trashed variants are excluded entirely:

```python
def test_scope_history_same_source_candidates_exclude_trashed() -> None:
    # ... (rewrite to verify that after project_trash, the trashed variant
    # no longer appears in the same-source candidates response)
```

- [ ] **Step 8: Run tests**

Run: `python -m pytest tests/test_variant_api.py::test_same_source_candidates_exclude_trashed_variants tests/test_variant_api.py::test_entry_timeline_excludes_trashed_variants -v`

Expected: PASS

- [ ] **Step 9: Run full test suite**

Run: `python -m pytest tests/ -v`

Expected: PASS

- [ ] **Step 10: Commit**

```bash
git add app/services/read_models/repository.py app/schemas.py tests/test_variant_api.py
git commit -m "feat: exclude trashed variants from same-source history and entry timeline"
```

---

### Task 7: Orphan Scope In ScopeSelector And Repository

**Files:**
- Modify: `app/services/read_models/selectors.py`
- Modify: `app/services/read_models/repository.py`
- Test: `tests/test_variant_api.py`

This task adds orphan scope support to the read model layer so that `ScopeSelector.parse("orphan")` returns a selector that queries variants with zero bindings and `trashed_at IS NULL`.

- [ ] **Step 1: Write the failing test for orphan scope members**

Add to `tests/test_variant_api.py`:

```python
def test_orphan_scope_returns_unbound_non_trashed_variants() -> None:
    reset_demo()
    variant_service = TrashRestoreService()

    variant_service.delete(BranchRef.rel_current(), ["common.welcome"])

    with TestClient(app) as client:
        response = client.get("/api/projects/1/scopes/orphan/rows")
        assert response.status_code == 200
        payload = response.json()
        assert payload["scope_ref"] == "orphan"
        orphan_keys = {row["business_key"] for row in payload["rows"]}
        assert "common.welcome" in orphan_keys
        assert all(row["state"] == "orphan" for row in payload["rows"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_variant_api.py::test_orphan_scope_returns_unbound_non_trashed_variants -v`

Expected: FAIL — `ScopeSelector.parse("orphan")` will try to parse "orphan" as a BranchRef, which should now work (from Task 1), but the repository's `_scope_member_where` won't generate the right query for orphan scope.

- [ ] **Step 3: Add orphan scope support to ScopeSelector**

In `app/services/read_models/selectors.py`, update `ScopeSelector.parse()`:

```python
@classmethod
def parse(cls, scope_ref: str) -> ScopeSelector:
    normalized = normalize_non_content_value(scope_ref)
    if not normalized:
        raise ValueError("scope ref is required")
    if normalized == "master":
        return cls.master()
    if normalized == "orphan":
        return cls.orphan()
    return cls.from_branch(BranchRef.parse(normalized))
```

Add the `orphan()` factory and `is_orphan` property:

```python
@classmethod
def orphan(cls) -> ScopeSelector:
    return cls(scope_ref="orphan")

@property
def is_orphan(self) -> bool:
    return self.scope_ref == "orphan"
```

- [ ] **Step 4: Update _scope_member_where in repository to handle orphan scope**

In `app/services/read_models/repository.py`, method `_scope_member_where()`, update the scope filter logic:

Replace the current block:
```python
if not scope_selector.is_master:
    branch_ref = scope_selector.branch_ref
    if branch_ref is None:
        raise ValueError("branch scope selector is required")
    scope_type, scope_value = branch_ref.as_tuple()
    where_clauses.append(
        "EXISTS ("
        "SELECT 1 FROM scope_bindings b "
        "WHERE b.variant_id = v.variant_id "
        "AND b.scope_type = ? "
        "AND b.scope_value = ?"
        ")"
    )
    params.extend([scope_type, scope_value])
```

With:
```python
if scope_selector.is_orphan:
    where_clauses.append(
        "NOT EXISTS ("
        "SELECT 1 FROM scope_bindings b "
        "WHERE b.variant_id = v.variant_id"
        ")"
    )
elif not scope_selector.is_master:
    branch_ref = scope_selector.branch_ref
    if branch_ref is None:
        raise ValueError("branch scope selector is required")
    scope_type, scope_value = branch_ref.as_tuple()
    where_clauses.append(
        "EXISTS ("
        "SELECT 1 FROM scope_bindings b "
        "WHERE b.variant_id = v.variant_id "
        "AND b.scope_type = ? "
        "AND b.scope_value = ?"
        ")"
    )
    params.extend([scope_type, scope_value])
```

Note: The `v.trashed_at IS NULL` filter is already in the where_clauses, so the orphan scope correctly returns only live unbound variants.

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_variant_api.py::test_orphan_scope_returns_unbound_non_trashed_variants -v`

Expected: PASS

- [ ] **Step 6: Run full test suite**

Run: `python -m pytest tests/ -v`

Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add app/services/read_models/selectors.py app/services/read_models/repository.py tests/test_variant_api.py
git commit -m "feat: add orphan computed scope to ScopeSelector and repository"
```

---

### Task 8: Branch Summary Includes Orphan Pseudo-Branch

**Files:**
- Modify: `app/services/read_models/derived/branch_summary.py`
- Test: `tests/test_variant_api.py`

This task adds orphan as a pseudo-branch entry in the branch summary with its variant count.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_variant_api.py`:

```python
def test_branch_summary_includes_orphan_count() -> None:
    reset_demo()
    variant_service = TrashRestoreService()

    variant_service.delete(BranchRef.rel_current(), ["common.welcome"])

    with TestClient(app) as client:
        response = client.get("/api/projects/1/branches", params={"lang": "fr"})
        assert response.status_code == 200
        branches = response.json()["branches"]
        orphan_entry = next((b for b in branches if b["branch_ref"] == "orphan"), None)
        assert orphan_entry is not None
        assert orphan_entry["entry_count"] >= 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_variant_api.py::test_branch_summary_includes_orphan_count -v`

Expected: FAIL — branch summary does not include orphan entry.

- [ ] **Step 3: Add orphan pseudo-branch to BranchSummaryView.build()**

In `app/services/read_models/derived/branch_summary.py`, modify the `build()` method to append an orphan entry. Add this after the `for branch_ref in branch_order:` loop but before the return:

```python
orphan_count = self._count_orphan_variants(project_id)
if orphan_count > 0:
    branches.append(
        {
            "branch_ref": "orphan",
            "entry_count": orphan_count,
            "status_counts": {"orphan": orphan_count},
        }
    )
```

Add the helper method:

```python
def _count_orphan_variants(self, project_id: int) -> int:
    from app.services.read_models.selectors import ScopeSelector
    return self.repository.count_scope_members(project_id, ScopeSelector.orphan())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_variant_api.py::test_branch_summary_includes_orphan_count -v`

Expected: PASS

- [ ] **Step 5: Run full test suite**

Run: `python -m pytest tests/ -v`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app/services/read_models/derived/branch_summary.py tests/test_variant_api.py
git commit -m "feat: branch summary includes orphan as pseudo-branch entry"
```

---

### Task 9: Update Active Docs

**Files:**
- Modify: `docs/system.md`
- Modify: `docs/workflows.md`
- Modify: `design/branch-infra-phase-map.md`

This task updates the active documentation to reflect the Phase 8 changes.

- [ ] **Step 1: Update docs/system.md Variant Lifecycle section**

Replace the current lifecycle section with:

```markdown
## Variant Lifecycle

Three states with strict definitions:

- `active`: referenced by at least one scope binding; participates in fill and read models
- `orphan`: no active binding but still live; participates in fill and read models via `BranchRef.orphan()` computed scope
- `trashed`: explicitly removed from the project via project trash; does not participate in fill, read models, same-source candidates, or entry timeline

State resolution:
1. `trashed_at` is not NULL → **trashed**
2. Has bindings → **active**
3. Otherwise → **orphan**

Allowed transitions:
- **Active → Orphan**: last real binding removed (via branch delete, replace, or any unbind operation)
- **Orphan → Active**: new binding created (via mutation same-source reuse, bootstrap same-source reuse)
- **Orphan → Trashed**: explicit project trash operation
- **Trashed is terminal**: no restore, no cleanup, no way back

`BranchRef.orphan()` is a readable computed scope. It is not a writable branch: mutations, bootstrap, and replace cannot target it. The scope-members query returns all variants with zero bindings and `trashed_at IS NULL`.

Branch delete is a pure unbind operation. The last binding removal produces orphan, not trash. Project trash is a separate explicit operation targeting orphan variants only.
```

- [ ] **Step 2: Update docs/workflows.md Trash And Restore Rules section**

Replace the current section with:

```markdown
## Branch Delete (Unbind) Rules

- branch delete is branch-scoped and takes `branch_ref` plus `business_keys[]`
- branch delete executes in one DB transaction per request
- branch delete removes the active binding in the selected branch
- if the affected variant no longer has any active bindings, it becomes orphan (not trashed)
- if other branches still bind the same variant, branch delete only removes the selected branch binding
- no authority check; an operator can always unbind entries from their own branch
- report statuses: `ORPHANED_VARIANT`, `REMOVED_BINDING`, `NOT_BOUND_IN_SCOPE`, `MISSING`
- summary fields: `orphaned_variant_count`, `removed_binding_count`, `not_bound_count`, `missing_count`

## Project Trash Rules

- project trash is project-scoped and takes `business_keys[]`
- project trash executes in one DB transaction per request
- project trash sets `trashed_at` on orphan variants only (zero bindings)
- active variants (with bindings) are reported as `NOT_ORPHAN` and skipped
- trashed is terminal: no restore, no cleanup, no way back
- no authority check; project trash is a project-level admin action
- report statuses: `TRASHED`, `NOT_ORPHAN`, `NO_ORPHAN_FOUND`, `MISSING`
- summary fields: `trashed_count`, `not_orphan_count`, `no_orphan_found_count`, `missing_count`
```

- [ ] **Step 3: Update docs/workflows.md Fill Rules section**

Update the fill rules:

Change "fill candidate lookup is project-scoped and reads all recorded variants for that project, including `active`, `orphan`, and `trashed`" to:

"fill candidate lookup is project-scoped and reads all live (non-trashed) variants for that project, including `active` and `orphan` states"

Change "when the same `business_key + source` has both non-trashed and trashed candidates, fill always prefers the non-trashed candidate" and "when only trashed same-source history remains, fill uses the candidate with the newest `updated_at`" to:

"trashed variants are completely excluded from fill candidate lookup"

Change "`match_variant_state` (`active`, `orphan`, or `trashed`)" to "`match_variant_state` (`active` or `orphan`)"

- [ ] **Step 4: Update design/branch-infra-phase-map.md Phase 8 status**

Change Phase 8 status from "partially modeled, not fully closed" to "complete".

Update the Phase 8 section:

```markdown
### Phase 8: Lifecycle And Recovery

Status:

- complete

Goal:

- redesign the variant lifecycle model around three terminal-aware states (active, orphan, trashed)

Completed decisions:

- branch delete is pure unbind: last binding removal produces orphan, not trash
- project trash is a separate explicit operation targeting orphan variants only
- trashed is terminal: no restore, no cleanup, no way back
- `BranchRef.orphan()` is a readable computed scope with full read model integration
- trashed variants are excluded from fill, same-source candidates, and entry timeline
- orphan scope appears in branch summary with variant count
- restore endpoint is removed

Artifacts:

- [phase-8-lifecycle-and-recovery-design.md](../phase-8-lifecycle-and-recovery-design.md): Phase 8 lifecycle design spec
- [phase-8-lifecycle-and-recovery-implementation-plan.md](phase-8-lifecycle-and-recovery-implementation-plan.md): implementation plan

Session focus:

- Phase 8 is implemented; lifecycle semantics are validated against branch bootstrap, mutation, and replace flows
```

Update "Suggested Next Session" to point to Phase 9.

Update "Simple Memory Hook":

```
Phase 1 through Phase 8 are done; next converge code, docs, frontend, and compatibility layers onto the intended long-term shape.
```

- [ ] **Step 5: Commit**

```bash
git add docs/system.md docs/workflows.md design/branch-infra-phase-map.md
git commit -m "docs: update active docs and phase map for Phase 8 lifecycle redesign"
```

---

### Task 10: Final Integration Test And Verification

**Files:**
- Test: `tests/test_variant_api.py`

This task adds an end-to-end integration test that exercises the complete Phase 8 lifecycle flow.

- [ ] **Step 1: Write the integration test**

Add to `tests/test_variant_api.py`:

```python
def test_phase_8_lifecycle_end_to_end() -> None:
    """Full lifecycle: active -> orphan -> rebind -> orphan -> project_trash."""
    reset_demo()
    sample = DemoService().get_sample("core-cycle")

    with TestClient(app) as client:
        delete_resp = client.post(
            "/api/projects/1/variants/trash/delete",
            json={"branch_ref": "rel/current", "business_keys": ["common.welcome"]},
        )
        delete_detail = wait_for_job(client, delete_resp.json())
        assert delete_detail["job"]["status"] == "success"
        assert delete_detail["report"]["summary"]["orphaned_variant_count"] == 1

        orphan_rows = client.get("/api/projects/1/scopes/orphan/rows")
        assert orphan_rows.status_code == 200
        orphan_keys = {r["business_key"] for r in orphan_rows.json()["rows"]}
        assert "common.welcome" in orphan_keys

        branches_resp = client.get("/api/projects/1/branches", params={"lang": "fr"})
        orphan_branch = next(
            (b for b in branches_resp.json()["branches"] if b["branch_ref"] == "orphan"),
            None,
        )
        assert orphan_branch is not None
        assert orphan_branch["entry_count"] >= 1

        rebind_resp = client.post(
            "/api/projects/1/branches/mutations",
            json={
                "branch_ref": "rel/current",
                "input": {
                    "kind": "direct",
                    "changes": [
                        {
                            "business_key": "common.welcome",
                            "source": "Welcome {0}",
                            "translations_by_lang": {"fr": "Bienvenue rebind"},
                        }
                    ],
                },
            },
        )
        assert rebind_resp.status_code == 200
        rebind_detail = wait_for_job(client, rebind_resp.json())
        assert rebind_detail["job"]["status"] == "success"

        orphan_rows_after = client.get("/api/projects/1/scopes/orphan/rows")
        orphan_keys_after = {r["business_key"] for r in orphan_rows_after.json()["rows"]}
        assert "common.welcome" not in orphan_keys_after

        delete2_resp = client.post(
            "/api/projects/1/variants/trash/delete",
            json={"branch_ref": "rel/current", "business_keys": ["common.welcome"]},
        )
        delete2_detail = wait_for_job(client, delete2_resp.json())
        assert delete2_detail["job"]["status"] == "success"

        trash_resp = client.post(
            "/api/projects/1/variants/trash",
            json={"business_keys": ["common.welcome"]},
        )
        trash_detail = wait_for_job(client, trash_resp.json())
        assert trash_detail["job"]["status"] == "success"
        assert trash_detail["report"]["summary"]["trashed_count"] >= 1

        orphan_rows_final = client.get("/api/projects/1/scopes/orphan/rows")
        orphan_keys_final = {r["business_key"] for r in orphan_rows_final.json()["rows"]}
        assert "common.welcome" not in orphan_keys_final

        assert client.post(
            "/api/projects/1/variants/trash/restore",
            json={"variant_ids": [1]},
        ).status_code == 404 or client.post(
            "/api/projects/1/variants/trash/restore",
            json={"variant_ids": [1]},
        ).status_code == 405
```

- [ ] **Step 2: Run the integration test**

Run: `python -m pytest tests/test_variant_api.py::test_phase_8_lifecycle_end_to_end -v`

Expected: PASS

- [ ] **Step 3: Run the full test suite**

Run: `python -m pytest tests/ -v`

Expected: All tests PASS.

- [ ] **Step 4: Commit**

```bash
git add tests/test_variant_api.py
git commit -m "test: add Phase 8 lifecycle end-to-end integration test"
```

---

## Success Conditions Checklist

After all tasks are complete, verify against the design spec's 10 success conditions:

| # | Condition | Verified by |
|---|-----------|-------------|
| 1 | Branch delete produces orphan instead of trashed | Task 2 tests |
| 2 | Project trash is separate, targets orphans only | Task 3 tests |
| 3 | Trashed excluded from fill completely | Task 5 tests |
| 4 | Trashed excluded from same-source and entry timeline | Task 6 tests |
| 5 | `BranchRef.orphan()` readable computed scope | Task 7 tests |
| 6 | Orphan in branch summary | Task 8 test |
| 7 | Restore endpoint removed | Task 4 + Task 10 |
| 8 | Replace, bootstrap, mutation correctly produce orphans | Already correct (no code changes needed) |
| 9 | No change for active variants | All existing tests pass |
| 10 | Same-source canonical invariant preserved | No schema change, existing index unchanged |
