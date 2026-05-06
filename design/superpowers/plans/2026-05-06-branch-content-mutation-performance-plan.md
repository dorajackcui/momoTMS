# Branch Content Mutation Performance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `workbook_batch + mutation_type=content` run as a chunked bulk content mutation path while preserving current branch-cycle semantics and report contracts.

**Architecture:** Keep the public mutation route and `ContentBatchMutationApplier` entrypoint, but replace the row-at-a-time internals with chunk-level resolution, in-memory authority classification, sparse write-sets, and batched DB writes. Add only the repository primitives needed for content mutation now, with names and data shapes that can later support a shared range/import mutation resolver.

**Tech Stack:** Python 3.11, FastAPI service layer, SQLite, pytest, openpyxl-backed workbook batch fixtures, existing branch-cycle smoke runner.

---

## Scope Check

This plan implements only the first performance pass from
`design/2026-05-06-branch-content-mutation-performance-design.md`.

In scope:

- content mutation for `workbook_batch + mutation_type = content`
- schema-owned translation/remark sparse updates
- mapped blank cells clear values by writing `""`
- bulk authority checks for rel-owned shared variants
- pivot state updates when pivot-language content changes
- stage/progress timing that supports `scripts/run_branch_cycle_smoke.py`
- focused TDD and branch workflow regressions

Out of scope:

- range mutation optimization
- `import_batch` mutation optimization
- branch bootstrap changes beyond using the current behavior in tests
- frontend changes
- old database migrations beyond normal schema rebuild or reseed

## File Structure

Core implementation files:

- `app/db.py`: add `idx_scope_bindings_entry_variant` to the rebuilt schema.
- `app/services/workbooks/batches.py`: expose `iter_row_chunks()` so content mutation can process workbook rows in bounded chunks.
- `app/services/variant/store.py`: add bulk upsert/update helpers for translations, remarks, variant metadata, pivot changed state, and bulk variant lookup by ids.
- `app/services/variant/repositories.py`: expose the new store helpers through command/query repositories.
- `app/services/variant/catalog.py`: expose the new bulk helpers through `VariantCatalogService`.
- `app/services/branch/content_batch_mutation.py`: replace per-row apply with chunk resolve/classify/write while keeping `apply()` as the public service entrypoint.

Tests and verification files:

- `tests/test_tdd_branch_cycle.py`: extend focused branch-cycle coverage for schema sparse behavior, blank clears, authority filtering, pivot, and performance-stage visibility.
- `tests/test_bulk_seed.py`: add low-level bulk store helper coverage if the helper is not already covered elsewhere.
- `docs/workflows.md`: update only if the implementation changes documented workflow facts.
- `docs/testing.md`: update only if verification commands or focused flow wording changes.

No new public API routes are required.

---

### Task 1: Lock Content Mutation Semantics With Focused TDD

**Files:**

- Modify: `tests/test_tdd_branch_cycle.py`

- [ ] **Step 1: Add a helper for custom workbook headers**

Add this helper below the existing `write_workbook()` helper in `tests/test_tdd_branch_cycle.py`:

```python
def write_custom_workbook(
    root: Path,
    relative_path: str,
    headers: list[str],
    rows: list[list[object]],
) -> Path:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Sheet1"
    sheet.append(headers)
    for row in rows:
        sheet.append(row)
    output_path = root / relative_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(output_path)
    workbook.close()
    return output_path
```

- [ ] **Step 2: Add the failing sparse/blank/extra-column test**

Append this test to `tests/test_tdd_branch_cycle.py`:

```python
def test_tdd_content_mutation_uses_schema_fields_clears_blanks_and_ignores_extra_columns(tmp_path) -> None:
    init_db()
    project = ProjectService().create_project(
        "TDD Content Sparse",
        ["en", "fr", "es"],
        ["Version", "SpeakerName"],
        pivot_language="en",
        pivoted_languages=["fr", "es"],
        business_key_header="Key",
        source_header="MsgStr",
    )
    project_id = int(project["project_id"])

    release_workbook = write_workbook(
        tmp_path / "release",
        "2.4diff3.xlsx",
        [
            ["content.same", "Shared source", "Shared source", "FR rel", "ES rel", "2.4", "RelSpeaker"],
            ["content.dev", "Dev source", "Old EN", "Old FR", "Old ES", "2.4", "OldSpeaker"],
        ],
    )
    BulkVariantWriter().seed(
        project_id=project_id,
        branch_ref=BranchRef.rel_current(),
        workbook_path=str(release_workbook),
    )

    dev_ref = BranchRef.dev("2.5.3")
    bootstrap_root = tmp_path / "bootstrap"
    write_workbook(
        bootstrap_root,
        "2.5diff3.xlsx",
        [
            ["content.same", "Shared source", "Shared source edited", "FR filtered", "ES filtered", "2.5", "DevSpeaker"],
            ["content.dev", "Dev source", "New EN", "", "New ES", "", "NewSpeaker"],
        ],
    )
    bootstrap_batch = WorkbookBatchService().create_batch_from_directory(
        bootstrap_root,
        project_id,
        WorkbookWorkflowContext(workflow_kind="create_branch"),
    )
    BranchBootstrapService().bootstrap(dev_ref, bootstrap_batch["workbook_batch_id"], project_id=project_id)

    # Content workbook deliberately omits the schema column "es" and includes an
    # extra non-schema column. Missing schema columns must preserve old values;
    # mapped blank cells must clear existing values.
    content_root = tmp_path / "content"
    write_custom_workbook(
        content_root,
        "2.5content.xlsx",
        ["Key", "MsgStr", "en", "fr", "Version", "SpeakerName", "TranslatorNote"],
        [
            ["content.same", "Shared source", "Blocked EN", "Blocked FR", "2.5", "BlockedSpeaker", "ignored"],
            ["content.dev", "Dev source", "New EN", "", "", "NewSpeaker", "ignored"],
        ],
    )
    content_batch = WorkbookBatchService().create_batch_from_directory(
        content_root,
        project_id,
        WorkbookWorkflowContext(workflow_kind="branch_mutation", mutation_type="content"),
    )

    mutation = BranchMutationService().apply(
        dev_ref,
        {
            "kind": "workbook_batch",
            "mutation_type": "content",
            "workbook_batch_id": content_batch["workbook_batch_id"],
        },
        project_id=project_id,
    )

    rows = {row["business_key"]: row for row in mutation["report_rows"]}
    assert mutation["summary"]["processed_count"] == 2
    assert mutation["summary"]["updated_bound_variant_count"] == 1
    assert mutation["summary"]["noop_count"] == 1
    assert mutation["summary"]["content_filtered_by_authority_count"] == 1
    assert rows["content.same"]["status"] == "NOOP"
    assert rows["content.same"]["content_filtered_by_authority"] is True
    assert rows["content.dev"]["status"] == "UPDATED_BOUND_VARIANT"

    catalog = VariantCatalogService()
    dev_rows = branch_rows(dev_ref, project_id)
    same_variant = catalog.get_variant(int(dev_rows["content.same"]["variant_id"]))
    dev_variant = catalog.get_variant(int(dev_rows["content.dev"]["variant_id"]))

    assert same_variant["translations"]["fr"] == "FR rel"
    assert same_variant["remarks"]["SpeakerName"] == "RelSpeaker"
    assert "TranslatorNote" not in same_variant["remarks"]

    assert dev_variant["translations"]["en"] == "New EN"
    assert dev_variant["translations"]["fr"] == ""
    assert "es" not in dev_variant["translations"]
    assert dev_variant["remarks"]["Version"] == ""
    assert dev_variant["remarks"]["SpeakerName"] == "NewSpeaker"
    assert "TranslatorNote" not in dev_variant["remarks"]
    assert dev_variant["pivot_status"] == "changed"
    assert dev_variant["pivot_changed_by_scope_type"] == "dev"
    assert dev_variant["pivot_changed_by_scope_value"] == "2.5.3"
```

- [ ] **Step 3: Add the failing duplicate-row order test**

Append this test to `tests/test_tdd_branch_cycle.py`:

```python
def test_tdd_content_mutation_preserves_duplicate_key_row_order_within_batch(tmp_path) -> None:
    init_db()
    project = ProjectService().create_project(
        "TDD Content Duplicate Order",
        ["en", "fr"],
        [],
        pivot_language="en",
        pivoted_languages=["fr"],
        business_key_header="Key",
        source_header="MsgStr",
    )
    project_id = int(project["project_id"])
    dev_ref = BranchRef.dev("2.5.3")

    bootstrap_root = tmp_path / "bootstrap"
    write_custom_workbook(
        bootstrap_root,
        "bootstrap.xlsx",
        ["Key", "MsgStr", "en", "fr"],
        [["dup.key", "Dup source", "ignored", "ignored"]],
    )
    bootstrap_batch = WorkbookBatchService().create_batch_from_directory(
        bootstrap_root,
        project_id,
        WorkbookWorkflowContext(workflow_kind="create_branch"),
    )
    BranchBootstrapService().bootstrap(dev_ref, bootstrap_batch["workbook_batch_id"], project_id=project_id)

    content_root = tmp_path / "content"
    write_custom_workbook(
        content_root,
        "content.xlsx",
        ["Key", "MsgStr", "en", "fr"],
        [
            ["dup.key", "Dup source", "Dup source", "FR final"],
            ["dup.key", "Dup source", "Dup source", "FR final"],
        ],
    )
    content_batch = WorkbookBatchService().create_batch_from_directory(
        content_root,
        project_id,
        WorkbookWorkflowContext(workflow_kind="branch_mutation", mutation_type="content"),
    )
    mutation = BranchMutationService().apply(
        dev_ref,
        {
            "kind": "workbook_batch",
            "mutation_type": "content",
            "workbook_batch_id": content_batch["workbook_batch_id"],
        },
        project_id=project_id,
    )

    assert [row["status"] for row in mutation["report_rows"]] == ["UPDATED_BOUND_VARIANT", "NOOP"]
    assert mutation["summary"]["updated_bound_variant_count"] == 1
    assert mutation["summary"]["noop_count"] == 1

    variant_id = int(branch_rows(dev_ref, project_id)["dup.key"]["variant_id"])
    variant = VariantCatalogService().get_variant(variant_id)
    assert variant["translations"] == {"en": "Dup source", "fr": "FR final"}
```

- [ ] **Step 4: Run the new tests to capture current behavior**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_tdd_branch_cycle.py::test_tdd_content_mutation_uses_schema_fields_clears_blanks_and_ignores_extra_columns tests/test_tdd_branch_cycle.py::test_tdd_content_mutation_preserves_duplicate_key_row_order_within_batch
```

Expected: the sparse parser test should PASS if current semantics already match. The duplicate-row order test may FAIL before the bulk cache update exists; keep it as the regression lock for preserving row order.

- [ ] **Step 5: Run the existing focused branch-cycle test**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_tdd_branch_cycle.py::test_tdd_branch_cycle_release_bulk_seed_dev_bootstrap_then_translation_fill
```

Expected: PASS before implementation. If it fails because of unrelated existing worktree changes, stop and inspect before touching content mutation.

- [ ] **Step 6: Commit the semantic tests**

Run:

```powershell
git add tests/test_tdd_branch_cycle.py
git commit -m "test: lock content mutation sparse schema semantics"
```

---

### Task 2: Add Binding Index And Bulk Store Primitives

**Files:**

- Modify: `app/db.py`
- Modify: `app/services/variant/store.py`
- Modify: `app/services/variant/repositories.py`
- Modify: `app/services/variant/catalog.py`
- Test: `tests/test_bulk_seed.py`

- [ ] **Step 1: Add failing tests for bulk upsert and pivot helpers**

Append these tests to `tests/test_bulk_seed.py`:

```python
def test_bulk_upsert_translations_replaces_existing_value() -> None:
    reset_db()
    store = _VariantStore()
    ts = now_iso()
    with get_conn() as conn:
        _create_project_and_entries(conn, n=1)
        variant_id = store.bulk_create_variants([(1, "f.xlsx", "Hello", ts)], conn=conn)[0]
        store.bulk_write_translations([(variant_id, "fr", "Bonjour", ts)], conn=conn)
        store.bulk_upsert_translations([(variant_id, "fr", "", "2026-01-02T00:00:00+00:00")], conn=conn)
        row = conn.execute(
            "SELECT target_text, updated_at FROM variant_translations WHERE variant_id = ? AND lang = 'fr'",
            (variant_id,),
        ).fetchone()
        assert row["target_text"] == ""
        assert row["updated_at"] == "2026-01-02T00:00:00+00:00"


def test_bulk_upsert_remarks_replaces_existing_value() -> None:
    reset_db()
    store = _VariantStore()
    ts = now_iso()
    with get_conn() as conn:
        _create_project_and_entries(conn, n=1)
        variant_id = store.bulk_create_variants([(1, "f.xlsx", "Hello", ts)], conn=conn)[0]
        store.bulk_write_remarks([(variant_id, "context", "old", ts)], conn=conn)
        store.bulk_upsert_remarks([(variant_id, "context", "", "2026-01-02T00:00:00+00:00")], conn=conn)
        row = conn.execute(
            "SELECT remark_value, updated_at FROM variant_remarks WHERE variant_id = ? AND remark_key = 'context'",
            (variant_id,),
        ).fetchone()
        assert row["remark_value"] == ""
        assert row["updated_at"] == "2026-01-02T00:00:00+00:00"


def test_bulk_update_variant_files_and_pivot_changed() -> None:
    reset_db()
    store = _VariantStore()
    ts = now_iso()
    with get_conn() as conn:
        _create_project_and_entries(conn, n=1)
        variant_id = store.bulk_create_variants([(1, "old.xlsx", "Hello", ts)], conn=conn)[0]
        store.bulk_update_variant_files([(variant_id, "new.xlsx", "2026-01-02T00:00:00+00:00")], conn=conn)
        store.bulk_set_pivot_changed(
            [(variant_id, "dev", "2.5.3", "2026-01-02T00:00:00+00:00")],
            conn=conn,
        )
        row = conn.execute("SELECT * FROM variants WHERE variant_id = ?", (variant_id,)).fetchone()
        assert row["file_name"] == "new.xlsx"
        assert row["updated_at"] == "2026-01-02T00:00:00+00:00"
        assert row["pivot_status"] == "changed"
        assert row["pivot_changed_by_scope_type"] == "dev"
        assert row["pivot_changed_by_scope_value"] == "2.5.3"
        assert row["pivot_changed_at"] == "2026-01-02T00:00:00+00:00"
        assert row["pivot_status_updated_at"] == "2026-01-02T00:00:00+00:00"


def test_scope_bindings_entry_variant_index_exists() -> None:
    reset_db()
    with get_conn() as conn:
        rows = conn.execute("PRAGMA index_list('scope_bindings')").fetchall()
    index_names = {row["name"] for row in rows}
    assert "idx_scope_bindings_entry_variant" in index_names
```

- [ ] **Step 2: Run the new low-level tests to verify they fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_bulk_seed.py::test_bulk_upsert_translations_replaces_existing_value tests/test_bulk_seed.py::test_bulk_upsert_remarks_replaces_existing_value tests/test_bulk_seed.py::test_bulk_update_variant_files_and_pivot_changed tests/test_bulk_seed.py::test_scope_bindings_entry_variant_index_exists
```

Expected: FAIL with missing helper methods and missing index.

- [ ] **Step 3: Add the binding index to the rebuilt schema**

In `app/db.py`, after `idx_scope_bindings_variant`, add:

```python
        CREATE INDEX idx_scope_bindings_entry_variant
        ON scope_bindings(entry_id, variant_id);
```

- [ ] **Step 4: Add bulk store helpers**

Add these methods to `_VariantStore` in `app/services/variant/store.py`:

```python
    def get_many(
        self,
        variant_ids: list[int],
        conn: sqlite3.Connection | None = None,
    ) -> dict[int, VariantRecord]:
        if not variant_ids:
            return {}
        unique_ids = sorted(set(int(variant_id) for variant_id in variant_ids))
        placeholders = ", ".join("?" for _ in unique_ids)
        query = f"""
            SELECT *
            FROM variants
            WHERE variant_id IN ({placeholders})
            ORDER BY variant_id
        """
        if conn is not None:
            rows = conn.execute(query, unique_ids).fetchall()
            hydrated = self._hydrate_rows(rows, conn=conn)
        else:
            with get_conn() as local_conn:
                rows = local_conn.execute(query, unique_ids).fetchall()
                hydrated = self._hydrate_rows(rows, conn=local_conn)
        return {int(variant["variant_id"]): variant for variant in hydrated}

    def bulk_upsert_translations(
        self,
        rows: list[tuple[int, str, str, str]],
        *,
        conn: sqlite3.Connection,
    ) -> None:
        if not rows:
            return
        conn.executemany(
            """
            INSERT INTO variant_translations(variant_id, lang, target_text, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(variant_id, lang)
            DO UPDATE SET
                target_text = excluded.target_text,
                updated_at = excluded.updated_at
            """,
            rows,
        )

    def bulk_upsert_remarks(
        self,
        rows: list[tuple[int, str, str, str]],
        *,
        conn: sqlite3.Connection,
    ) -> None:
        if not rows:
            return
        conn.executemany(
            """
            INSERT INTO variant_remarks(variant_id, remark_key, remark_value, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(variant_id, remark_key)
            DO UPDATE SET
                remark_value = excluded.remark_value,
                updated_at = excluded.updated_at
            """,
            rows,
        )

    def bulk_update_variant_files(
        self,
        rows: list[tuple[int, str, str]],
        *,
        conn: sqlite3.Connection,
    ) -> None:
        if not rows:
            return
        conn.executemany(
            """
            UPDATE variants
            SET file_name = ?,
                updated_at = ?
            WHERE variant_id = ?
            """,
            [(file_name, updated_at, variant_id) for variant_id, file_name, updated_at in rows],
        )

    def bulk_set_pivot_changed(
        self,
        rows: list[tuple[int, str, str, str]],
        *,
        conn: sqlite3.Connection,
    ) -> None:
        if not rows:
            return
        conn.executemany(
            """
            UPDATE variants
            SET pivot_status = 'changed',
                pivot_changed_by_scope_type = ?,
                pivot_changed_by_scope_value = ?,
                pivot_changed_at = ?,
                pivot_status_updated_at = ?
            WHERE variant_id = ?
            """,
            [
                (scope_type, scope_value, timestamp, timestamp, variant_id)
                for variant_id, scope_type, scope_value, timestamp in rows
            ],
        )
```

- [ ] **Step 5: Expose helpers through repositories**

In `app/services/variant/repositories.py`, add to `VariantCommandRepository`:

```python
    def bulk_upsert_translations(
        self,
        rows: list[tuple[int, str, str, str]],
        *,
        conn: sqlite3.Connection,
    ) -> None:
        self._store.bulk_upsert_translations(rows, conn=conn)

    def bulk_upsert_remarks(
        self,
        rows: list[tuple[int, str, str, str]],
        *,
        conn: sqlite3.Connection,
    ) -> None:
        self._store.bulk_upsert_remarks(rows, conn=conn)

    def bulk_update_variant_files(
        self,
        rows: list[tuple[int, str, str]],
        *,
        conn: sqlite3.Connection,
    ) -> None:
        self._store.bulk_update_variant_files(rows, conn=conn)

    def bulk_set_pivot_changed(
        self,
        rows: list[tuple[int, str, str, str]],
        *,
        conn: sqlite3.Connection,
    ) -> None:
        self._store.bulk_set_pivot_changed(rows, conn=conn)
```

Add to `VariantQueryRepository`:

```python
    def get_many(
        self,
        variant_ids: list[int],
        conn: sqlite3.Connection | None = None,
    ) -> dict[int, VariantRecord]:
        return self._store.get_many(variant_ids, conn=conn)
```

- [ ] **Step 6: Expose helpers through `VariantCatalogService`**

In `app/services/variant/catalog.py`, add:

```python
    def get_variants(
        self,
        variant_ids: list[int],
        conn: sqlite3.Connection | None = None,
    ) -> dict[int, VariantRecord]:
        return self._queries.get_many(variant_ids, conn=conn)

    def bulk_upsert_translations(
        self,
        rows: list[tuple[int, str, str, str]],
        *,
        conn: sqlite3.Connection,
    ) -> None:
        self._commands.bulk_upsert_translations(rows, conn=conn)

    def bulk_upsert_remarks(
        self,
        rows: list[tuple[int, str, str, str]],
        *,
        conn: sqlite3.Connection,
    ) -> None:
        self._commands.bulk_upsert_remarks(rows, conn=conn)

    def bulk_update_variant_files(
        self,
        rows: list[tuple[int, str, str]],
        *,
        conn: sqlite3.Connection,
    ) -> None:
        self._commands.bulk_update_variant_files(rows, conn=conn)

    def bulk_set_pivot_changed(
        self,
        rows: list[tuple[int, str, str, str]],
        *,
        conn: sqlite3.Connection,
    ) -> None:
        self._commands.bulk_set_pivot_changed(rows, conn=conn)
```

- [ ] **Step 7: Run low-level tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_bulk_seed.py::test_bulk_upsert_translations_replaces_existing_value tests/test_bulk_seed.py::test_bulk_upsert_remarks_replaces_existing_value tests/test_bulk_seed.py::test_bulk_update_variant_files_and_pivot_changed tests/test_bulk_seed.py::test_scope_bindings_entry_variant_index_exists
```

Expected: PASS.

- [ ] **Step 8: Commit**

Run:

```powershell
git add app/db.py app/services/variant/store.py app/services/variant/repositories.py app/services/variant/catalog.py tests/test_bulk_seed.py
git commit -m "feat: add bulk content mutation store primitives"
```

---

### Task 3: Add Chunk Reader API For Workbook Batches

**Files:**

- Modify: `app/services/workbooks/batches.py`
- Test: `tests/test_workbook_intake.py`

- [ ] **Step 1: Add failing chunk reader test**

Append this test to `tests/test_workbook_intake.py`:

```python
def test_workbook_batch_service_iter_row_chunks_preserves_order(tmp_path) -> None:
    reset_demo()
    project = ProjectService().create_project(
        "Chunked Batch Project",
        ["fr"],
        [],
        business_key_header="Key",
        source_header="MsgStr",
    )
    project_id = int(project["project_id"])
    root = tmp_path / "batch-chunks"
    write_workbook(
        root,
        "batch.xlsx",
        [
            ["Key", "MsgStr", "fr"],
            ["chunk.1", "Source 1", "FR 1"],
            ["chunk.2", "Source 2", "FR 2"],
            ["chunk.3", "Source 3", "FR 3"],
        ],
    )
    batch = WorkbookBatchService().create_batch_from_directory(
        root,
        project_id,
        WorkbookWorkflowContext(workflow_kind="branch_mutation", mutation_type="content"),
    )
    chunks = list(
        WorkbookBatchService().iter_row_chunks(
            batch["workbook_batch_id"],
            project_id,
            ok_only=True,
            chunk_size=2,
        )
    )
    assert [[row["business_key"] for row in chunk] for chunk in chunks] == [
        ["chunk.1", "chunk.2"],
        ["chunk.3"],
    ]
```

`tests/test_workbook_intake.py` already has `write_workbook()` and `reset_demo()`, so use those local helpers.

- [ ] **Step 2: Run the failing test**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_workbook_intake.py::test_workbook_batch_service_iter_row_chunks_preserves_order
```

Expected: FAIL with `AttributeError: 'WorkbookBatchService' object has no attribute 'iter_row_chunks'`.

- [ ] **Step 3: Implement `iter_row_chunks()`**

Add this method to `WorkbookBatchService` in `app/services/workbooks/batches.py`, immediately below `iter_rows()`:

```python
    def iter_row_chunks(
        self,
        workbook_batch_id: int,
        project_id: int = DEFAULT_PROJECT_ID,
        *,
        ok_only: bool = False,
        chunk_size: int | None = None,
    ) -> Iterator[list[dict[str, Any]]]:
        self.require_batch_project(workbook_batch_id, project_id)
        limit = int(chunk_size or self.READ_CHUNK_SIZE)
        last_id = 0
        while True:
            rows = self._load_chunk(workbook_batch_id, last_id, ok_only=ok_only, limit=limit)
            if not rows:
                break
            last_id = int(rows[-1]["import_row_id"])
            yield rows
```

Update `_load_chunk()` in the same file to accept the explicit limit:

```python
    def _load_chunk(
        self,
        workbook_batch_id: int,
        after_row_id: int,
        *,
        ok_only: bool,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
```

At the end of `_load_chunk()`, replace:

```python
        params.append(self.READ_CHUNK_SIZE)
```

with:

```python
        params.append(int(limit or self.READ_CHUNK_SIZE))
```

- [ ] **Step 4: Run the chunk reader test**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_workbook_intake.py::test_workbook_batch_service_iter_row_chunks_preserves_order
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```powershell
git add app/services/workbooks/batches.py tests/test_workbook_intake.py
git commit -m "feat: add chunk iteration for workbook batches"
```

---

### Task 4: Implement Chunk-Level Content Mutation Resolve And Write

**Files:**

- Modify: `app/services/branch/content_batch_mutation.py`
- Test: `tests/test_tdd_branch_cycle.py`

- [ ] **Step 1: Add internal dataclasses and constants**

In `app/services/branch/content_batch_mutation.py`, add imports:

```python
from dataclasses import dataclass, field
from app.services.project.service import ProjectService
from app.services.shared.io import normalize_content_map, normalize_non_content_map, normalize_non_content_value
from app.services.shared.utils import now_iso
```

Add these dataclasses above `ContentBatchMutationApplier`:

```python
@dataclass
class _ResolvedContentRow:
    row: dict[str, Any]
    entry: dict[str, Any] | None = None
    binding: dict[str, Any] | None = None
    variant: dict[str, Any] | None = None
    bound_refs: list[BranchRef] = field(default_factory=list)


@dataclass
class _ContentWriteSet:
    translation_rows: list[tuple[int, str, str, str]] = field(default_factory=list)
    remark_rows: list[tuple[int, str, str, str]] = field(default_factory=list)
    variant_file_rows: list[tuple[int, str, str]] = field(default_factory=list)
    pivot_changed_rows: list[tuple[int, str, str, str]] = field(default_factory=list)
```

Add the chunk size to the class:

```python
    READ_CHUNK_SIZE = 1000
```

- [ ] **Step 2: Add `ProjectService` dependency**

Update `ContentBatchMutationApplier.__init__()` signature:

```python
        projects: ProjectService | None = None,
```

Set the instance property:

```python
        self.projects = projects or ProjectService()
```

- [ ] **Step 3: Replace the apply loop with chunk processing**

In `ContentBatchMutationApplier.apply()`, replace the `for row in self.batches.iter_rows(...)` loop with:

```python
        schema = self.projects.get_schema(project_id)
        for chunk_rows in self.batches.iter_row_chunks(
            workbook_batch_id,
            project_id,
            ok_only=True,
            chunk_size=self.READ_CHUNK_SIZE,
        ):
            elapsed_seconds = perf_counter() - started
            if max_elapsed_seconds is not None and elapsed_seconds > max_elapsed_seconds:
                raise TimeoutError(
                    "content mutation exceeded "
                    f"{max_elapsed_seconds:.1f}s after {len(report_rows)} rows"
                )
            chunk_result = self._apply_chunk(
                branch_ref,
                chunk_rows,
                project_id,
                schema,
                conn,
            )
            for report_row in chunk_result["report_rows"]:
                status_counts.update([report_row["status"]])
                semantic_counts.add_row(report_row)
                filtered_count += int(bool(report_row.get("content_filtered_by_authority")))
                report_rows.append(report_row)
                if (
                    progress_callback is not None
                    and progress_interval > 0
                    and len(report_rows) % progress_interval == 0
                ):
                    progress_callback(
                        self._progress_payload(
                            branch_ref,
                            workbook_batch_id,
                            len(report_rows),
                            status_counts,
                            filtered_count=filtered_count,
                            started=started,
                        )
                    )
```

Keep the existing summary construction unchanged.

- [ ] **Step 4: Add `_apply_chunk()`**

Add this method to `ContentBatchMutationApplier`:

```python
    def _apply_chunk(
        self,
        branch_ref: BranchRef,
        rows: list[dict[str, Any]],
        project_id: int,
        schema: dict[str, Any],
        conn: sqlite3.Connection,
    ) -> dict[str, Any]:
        timestamp = now_iso()
        resolved_rows = self._resolve_chunk(branch_ref, rows, project_id, conn)
        write_set = _ContentWriteSet()
        report_rows: list[dict[str, Any]] = []
        scope_type, scope_value = branch_ref.as_tuple()

        for resolved in resolved_rows:
            row = resolved.row
            payload = row["payload"]
            if resolved.entry is None or resolved.binding is None or resolved.variant is None:
                report_rows.append(self._report(row, "MISSING_IN_SCOPE", "none", "none", "stay_current", "missing"))
                continue

            variant = resolved.variant
            requested_source = normalize_non_content_value(payload.get("source"))
            if variant["source"] != requested_source:
                report_rows.append(self._report(row, "SOURCE_MISMATCH", "none", "none", "stay_current", "missing"))
                continue

            merged = self._merge_schema_payload(variant, payload)
            if self.resolution.variant_matches(variant, merged):
                report_rows.append(
                    self._report(
                        row,
                        "NOOP",
                        "none",
                        "none",
                        "stay_current",
                        "noop",
                        variant_id=int(variant["variant_id"]),
                    )
                )
                continue

            decision = AuthorityPolicy.evaluate_content_edit(
                branch_ref,
                resolved.bound_refs,
                content_changed=True,
            )
            if decision.filtered:
                report_rows.append(
                    self._report(
                        row,
                        "NOOP",
                        "none",
                        "filtered",
                        "stay_current",
                        "noop",
                        variant_id=int(variant["variant_id"]),
                        content_filtered_by_authority=True,
                    )
                )
                continue

            variant_id = int(variant["variant_id"])
            self._append_sparse_writes(write_set, variant, merged, timestamp)
            if self._pivot_language_changed(schema, variant, merged):
                write_set.pivot_changed_rows.append((variant_id, scope_type, scope_value, timestamp))
            self._update_variant_cache_after_write(variant, merged)
            report_rows.append(
                self._report(
                    row,
                    "UPDATED_BOUND_VARIANT",
                    "none",
                    "update",
                    "stay_current",
                    "applied",
                    variant_id=variant_id,
                )
            )

        self._flush_write_set(write_set, conn)
        return {"report_rows": report_rows}
```

- [ ] **Step 5: Add `_resolve_chunk()`**

Add this method:

```python
    def _resolve_chunk(
        self,
        branch_ref: BranchRef,
        rows: list[dict[str, Any]],
        project_id: int,
        conn: sqlite3.Connection,
    ) -> list[_ResolvedContentRow]:
        business_keys = sorted({normalize_non_content_value(row["payload"].get("business_key")) for row in rows})
        entries_by_key = self.entries.get_entries_by_keys(business_keys, project_id=project_id, conn=conn)
        entry_ids = [int(entry["entry_id"]) for entry in entries_by_key.values()]
        target_bindings = self.binding_lookup.get_bindings_for_entries(entry_ids, branch_ref, conn=conn)
        variant_ids = sorted({int(binding["variant_id"]) for binding in target_bindings.values()})
        variants_by_id = self.catalog.get_variants(variant_ids, conn=conn)
        all_bindings_by_entry = self.binding_lookup.list_bindings_for_entries(entry_ids, conn=conn)

        resolved: list[_ResolvedContentRow] = []
        for row in rows:
            business_key = normalize_non_content_value(row["payload"].get("business_key"))
            entry = entries_by_key.get(business_key)
            if entry is None:
                resolved.append(_ResolvedContentRow(row=row))
                continue
            entry_id = int(entry["entry_id"])
            binding = target_bindings.get(entry_id)
            if binding is None:
                resolved.append(_ResolvedContentRow(row=row, entry=entry))
                continue
            variant = variants_by_id.get(int(binding["variant_id"]))
            if variant is None:
                resolved.append(_ResolvedContentRow(row=row, entry=entry, binding=binding))
                continue
            bound_refs = self.resolution.bound_branch_refs_for_variant(
                all_bindings_by_entry.get(entry_id, []),
                int(variant["variant_id"]),
            )
            resolved.append(
                _ResolvedContentRow(
                    row=row,
                    entry=entry,
                    binding=binding,
                    variant=variant,
                    bound_refs=bound_refs,
                )
            )
        return resolved
```

- [ ] **Step 6: Add schema-aware merge and write helpers**

Add these methods:

```python
    def _merge_schema_payload(
        self,
        variant: dict[str, Any],
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        translations = dict(variant["translations"])
        translations.update(payload.get("translations", {}))
        remarks = dict(variant["remarks"])
        remarks.update(payload.get("remarks", {}))
        file_name = payload.get("file_name")
        if file_name is None:
            file_name = variant["file_name"]
        return {
            "file_name": normalize_non_content_value(file_name),
            "source": normalize_non_content_value(variant["source"]),
            "translations": normalize_content_map(translations),
            "remarks": normalize_non_content_map(remarks),
        }

    def _append_sparse_writes(
        self,
        write_set: _ContentWriteSet,
        variant: dict[str, Any],
        merged: dict[str, Any],
        timestamp: str,
    ) -> None:
        variant_id = int(variant["variant_id"])
        for lang, new_text in dict(merged["translations"]).items():
            if dict(variant["translations"]).get(lang) != new_text:
                write_set.translation_rows.append((variant_id, lang, str(new_text), timestamp))
        for remark_key, new_value in dict(merged["remarks"]).items():
            if dict(variant["remarks"]).get(remark_key) != new_value:
                write_set.remark_rows.append((variant_id, remark_key, str(new_value), timestamp))
        if variant["file_name"] != merged["file_name"]:
            write_set.variant_file_rows.append((variant_id, str(merged["file_name"]), timestamp))
        else:
            write_set.variant_file_rows.append((variant_id, str(variant["file_name"]), timestamp))

    def _pivot_language_changed(
        self,
        schema: dict[str, Any],
        variant: dict[str, Any],
        merged: dict[str, Any],
    ) -> bool:
        pivot_language = schema.get("pivot_language")
        if not pivot_language:
            return False
        old_value = dict(variant["translations"]).get(str(pivot_language), "")
        new_value = dict(merged["translations"]).get(str(pivot_language), "")
        return old_value != new_value

    def _flush_write_set(self, write_set: _ContentWriteSet, conn: sqlite3.Connection) -> None:
        self.catalog.bulk_upsert_translations(write_set.translation_rows, conn=conn)
        self.catalog.bulk_upsert_remarks(write_set.remark_rows, conn=conn)
        unique_file_rows: dict[int, tuple[int, str, str]] = {}
        for variant_id, file_name, timestamp in write_set.variant_file_rows:
            unique_file_rows[int(variant_id)] = (int(variant_id), file_name, timestamp)
        self.catalog.bulk_update_variant_files(list(unique_file_rows.values()), conn=conn)
        unique_pivot_rows: dict[int, tuple[int, str, str, str]] = {}
        for variant_id, scope_type, scope_value, timestamp in write_set.pivot_changed_rows:
            unique_pivot_rows[int(variant_id)] = (int(variant_id), scope_type, scope_value, timestamp)
        self.catalog.bulk_set_pivot_changed(list(unique_pivot_rows.values()), conn=conn)

    def _update_variant_cache_after_write(
        self,
        variant: dict[str, Any],
        merged: dict[str, Any],
    ) -> None:
        variant["file_name"] = merged["file_name"]
        variant["translations"] = dict(merged["translations"])
        variant["remarks"] = dict(merged["remarks"])
```

- [ ] **Step 7: Run focused branch-cycle tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_tdd_branch_cycle.py
```

Expected: PASS.

- [ ] **Step 8: Run content mutation service tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_branch_service.py -k "content_mutation or workbook_content or lower_authority"
```

Expected: PASS.

- [ ] **Step 9: Commit**

Run:

```powershell
git add app/services/branch/content_batch_mutation.py tests/test_tdd_branch_cycle.py
git commit -m "feat: bulk apply workbook content mutations"
```

---

### Task 5: Cover Progress Reporting And Stage Timing

**Files:**

- Modify: `app/services/branch/content_batch_mutation.py`
- Test: `tests/test_tdd_branch_cycle.py`

- [ ] **Step 1: Add failing progress/stage test**

Append this test to `tests/test_tdd_branch_cycle.py`:

```python
def test_tdd_content_mutation_reports_progress_and_stage_timing(tmp_path) -> None:
    init_db()
    project = ProjectService().create_project(
        "TDD Content Progress",
        ["en", "fr", "es"],
        ["Version", "SpeakerName"],
        pivot_language="en",
        pivoted_languages=["fr", "es"],
        business_key_header="Key",
        source_header="MsgStr",
    )
    project_id = int(project["project_id"])

    release_workbook = write_workbook(
        tmp_path / "release",
        "2.4diff3.xlsx",
        [["progress.key", "Old source", "Old source", "FR old", "ES old", "2.4", "Speaker"]],
    )
    BulkVariantWriter().seed(
        project_id=project_id,
        branch_ref=BranchRef.rel_current(),
        workbook_path=str(release_workbook),
    )

    dev_ref = BranchRef.dev("2.5.3")
    dev_root = tmp_path / "dev"
    write_workbook(
        dev_root,
        "2.5diff3.xlsx",
        [["progress.key", "New source", "New source", "FR new", "ES new", "2.5", "Speaker"]],
    )
    bootstrap_batch = WorkbookBatchService().create_batch_from_directory(
        dev_root,
        project_id,
        WorkbookWorkflowContext(workflow_kind="create_branch"),
    )
    BranchBootstrapService().bootstrap(dev_ref, bootstrap_batch["workbook_batch_id"], project_id=project_id)

    content_batch = WorkbookBatchService().create_batch_from_directory(
        dev_root,
        project_id,
        WorkbookWorkflowContext(workflow_kind="branch_mutation", mutation_type="content"),
    )
    progress_payloads: list[dict] = []
    with get_conn() as conn:
        result = BranchMutationService().content_batch.apply(
            dev_ref,
            int(content_batch["workbook_batch_id"]),
            project_id,
            conn=conn,
            progress_callback=progress_payloads.append,
            progress_interval=1,
            max_elapsed_seconds=300,
        )

    assert progress_payloads
    assert progress_payloads[-1]["processed_count"] == 1
    assert result["summary"]["processed_count"] == 1
    assert result["summary"]["stages"][0]["stage"] == "apply_content_mutation"
    assert result["summary"]["stages"][0]["meta"]["processed_count"] == 1
```

- [ ] **Step 2: Run the progress test**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_tdd_branch_cycle.py::test_tdd_content_mutation_reports_progress_and_stage_timing
```

Expected: PASS if existing progress support remains compatible; otherwise FAIL and fix the specific regression.

- [ ] **Step 3: Run focused tests again**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_tdd_branch_cycle.py
```

Expected: PASS.

- [ ] **Step 4: Commit**

Run:

```powershell
git add app/services/branch/content_batch_mutation.py tests/test_tdd_branch_cycle.py
git commit -m "test: cover content mutation progress and stage timing"
```

---

### Task 6: Add Large Smoke Gate And Query Plan Check

**Files:**

- Modify: `scripts/run_branch_cycle_smoke.py`
- Create: `scripts/check_content_mutation_query_plan.py`
- Test: no pytest required for the local smoke-only helper

- [ ] **Step 1: Add a query plan helper script**

Create `scripts/check_content_mutation_query_plan.py`:

```python
#!/usr/bin/env python
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.db import get_conn, init_db


def main() -> int:
    parser = argparse.ArgumentParser(description="Check query plans used by bulk content mutation.")
    parser.add_argument("--db-path", type=Path, help="Optional MOMO_TMS_DB_PATH override.")
    args = parser.parse_args()
    if args.db_path is not None:
        os.environ["MOMO_TMS_DB_PATH"] = str(args.db_path)
    init_db()
    with get_conn() as conn:
        plans = {
            "scope_bindings_entry_in": conn.execute(
                "EXPLAIN QUERY PLAN SELECT * FROM scope_bindings WHERE entry_id IN (1, 2, 3)"
            ).fetchall(),
            "scope_bindings_entry_variant": conn.execute(
                "EXPLAIN QUERY PLAN SELECT * FROM scope_bindings WHERE entry_id IN (1, 2, 3) AND variant_id IN (1, 2, 3)"
            ).fetchall(),
        }
    failed = False
    for name, rows in plans.items():
        print(f"[{name}]")
        text = "\n".join(str(tuple(row)) for row in rows)
        print(text)
        if "scope_bindings" in name and "idx_scope_bindings_entry_variant" not in text:
            failed = True
            print(f"ERROR: expected idx_scope_bindings_entry_variant in {name}", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Run the query plan helper**

Run:

```powershell
.\.venv\Scripts\python.exe scripts\check_content_mutation_query_plan.py
```

Expected: PASS and output mentions `idx_scope_bindings_entry_variant`.

- [ ] **Step 3: Run smoke setup through content batch only**

Run:

```powershell
.\.venv\Scripts\python.exe scripts\run_branch_cycle_smoke.py --reset --stop-after content-batch
```

Expected: PASS through `content-batch`. This validates release seed, bootstrap parsing, bootstrap execution, and content workbook parsing without running full mutation.

- [ ] **Step 4: Run full large smoke with the default guard**

Run:

```powershell
.\.venv\Scripts\python.exe scripts\run_branch_cycle_smoke.py --reset
```

Expected:

- PASS
- no `content mutation exceeded 300.0s` error
- summary prints `updated_bound_variant_count`, `noop_count`, and `content_filtered_by_authority_count`
- `stage.apply_content_mutation.elapsed_ms <= 60000` is the first-pass target

- [ ] **Step 5: Commit the query plan helper**

```powershell
git add scripts/check_content_mutation_query_plan.py
git commit -m "chore: add content mutation query plan helper"
```

---

### Task 7: Docs And Final Regression

**Files:**

- Modify: `docs/workflows.md` only if runtime behavior wording changed.
- Modify: `docs/testing.md` only if verification commands or smoke usage changed.
- Modify: `docs/contracts.md` only if route or response contract changed.

- [ ] **Step 1: Inspect docs for needed changes**

Run:

```powershell
rg -n "content mutation|workbook_batch|Focused branch-cycle|run_branch_cycle_smoke|mutation_type" docs
```

Expected: identify whether docs already match the implementation. If behavior is unchanged and commands already exist, no docs edit is required.

- [ ] **Step 2: Run focused TDD flow**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_tdd_branch_cycle.py
```

Expected: PASS.

- [ ] **Step 3: Run branch workflow regression**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_branch_service.py tests/test_io_flows.py
```

Expected: PASS.

- [ ] **Step 4: Run low-level bulk/helper tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_bulk_seed.py tests/test_workbook_intake.py
```

Expected: PASS.

- [ ] **Step 5: Run docs validation if docs changed**

If any `docs/*.md` file changed, run:

```powershell
.\.venv\Scripts\python.exe scripts\validate_docs.py
```

Expected: PASS.

- [ ] **Step 6: Commit final docs or fixups**

If there are docs or fixup changes:

```powershell
git add docs/workflows.md docs/testing.md docs/contracts.md app/services/branch/content_batch_mutation.py app/services/workbooks/batches.py app/services/variant/store.py app/services/variant/repositories.py app/services/variant/catalog.py app/db.py tests/test_tdd_branch_cycle.py tests/test_bulk_seed.py tests/test_workbook_intake.py
git commit -m "docs: document content mutation performance verification"
```

If there are no remaining changes, skip this commit.

---

### Task 8: Final Verification And Closeout

**Files:**

- No new files unless previous tasks produced fixups.

- [ ] **Step 1: Check git status**

Run:

```powershell
git status --short
```

Expected: only unrelated pre-existing local files remain, or a clean working tree if this work was done in an isolated branch/worktree.

- [ ] **Step 2: Capture performance evidence**

Record the relevant smoke lines in the final response:

```text
stage.apply_content_mutation.elapsed_ms: <value>
processed_count: <value>
updated_bound_variant_count: <value>
noop_count: <value>
content_filtered_by_authority_count: <value>
```

- [ ] **Step 3: Final response**

Include:

- summary of content mutation bulkization
- compatibility statement: no route/input/report contract changes
- verification commands and results
- large smoke timing and whether it met `<= 60s`
- any tests not run and why
