# Bulk Variant Seed — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a CLI-driven bulk seed path that writes 200K variants into a new project in seconds, bypassing the import_rows/jobs/preview middleware.

**Architecture:** A `BulkVariantWriter` service orchestrates chunked reads from Excel via openpyxl and writes directly to SQLite using `executemany` through new `bulk_*` repository methods. The CLI script (`scripts/seed_variants.py`) validates preconditions, then delegates to the writer in a single DB transaction.

**Tech Stack:** Python 3.10+, openpyxl (already a dependency), SQLite via `app.db.get_conn`

---

### Task 1: Add bulk repository methods to `_VariantStore`

**Files:**
- Modify: `app/services/variant/store.py`
- Test: `tests/test_bulk_seed.py`

- [ ] **Step 1: Write the failing test for `bulk_create_variants`**

```python
# tests/test_bulk_seed.py
from pathlib import Path
import pytest
from app.db import get_db_path, init_db, get_conn
from app.services.variant.store import _VariantStore
from app.services.shared.utils import now_iso


def reset_db() -> None:
    db_path = get_db_path()
    if Path(db_path).exists():
        Path(db_path).unlink()
    init_db()


def _create_project_and_entries(conn, n=3):
    conn.execute(
        "INSERT INTO projects(name, is_default, created_at) VALUES ('test', 1, '2026-01-01T00:00:00+00:00')"
    )
    conn.execute(
        """INSERT INTO project_schemas(project_id, fixed_columns_json, translation_columns_json,
           remark_columns_json, pivot_language, pivoted_languages_json, created_at)
           VALUES (1, '{"business_key":"Key","source":"MsgStr","file_name":"file_name"}',
           '["fr","en"]', '["context"]', NULL, '[]', '2026-01-01T00:00:00+00:00')"""
    )
    ts = "2026-01-01T00:00:00+00:00"
    for i in range(1, n + 1):
        conn.execute(
            "INSERT INTO entries(project_id, business_key, created_at, updated_at) VALUES (1, ?, ?, ?)",
            (f"key_{i}", ts, ts),
        )


def test_bulk_create_variants():
    reset_db()
    store = _VariantStore()
    ts = now_iso()
    with get_conn() as conn:
        _create_project_and_entries(conn, n=3)
        rows = [
            (1, "file1.xlsx", "Hello", ts),
            (2, "file1.xlsx", "World", ts),
            (3, "file2.xlsx", "Foo", ts),
        ]
        variant_ids = store.bulk_create_variants(rows, conn=conn)
        assert len(variant_ids) == 3
        assert all(isinstance(vid, int) for vid in variant_ids)
        # Verify rows exist
        db_rows = conn.execute("SELECT * FROM variants ORDER BY variant_id").fetchall()
        assert len(db_rows) == 3
        assert db_rows[0]["entry_id"] == 1
        assert db_rows[0]["source"] == "Hello"
        assert db_rows[0]["pivot_status"] == "init"
        assert db_rows[0]["orphaned_at"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_bulk_seed.py::test_bulk_create_variants -v`
Expected: FAIL with `AttributeError: '_VariantStore' object has no attribute 'bulk_create_variants'`

- [ ] **Step 3: Implement `bulk_create_variants` on `_VariantStore`**

Add to `app/services/variant/store.py`:

```python
def bulk_create_variants(
    self,
    rows: list[tuple[int, str, str, str]],
    *,
    conn: sqlite3.Connection,
) -> list[int]:
    if not rows:
        return []
    cursor = conn.execute("SELECT MAX(variant_id) AS max_id FROM variants")
    max_before = cursor.fetchone()["max_id"] or 0
    conn.executemany(
        """
        INSERT INTO variants(
            entry_id, file_name, source, orphaned_at,
            pivot_status, pivot_status_updated_at, created_at, updated_at
        )
        VALUES (?, ?, ?, NULL, 'init', ?, ?, ?)
        """,
        [(entry_id, file_name, source, ts, ts, ts) for entry_id, file_name, source, ts in rows],
    )
    new_rows = conn.execute(
        "SELECT variant_id FROM variants WHERE variant_id > ? ORDER BY variant_id",
        (max_before,),
    ).fetchall()
    return [int(r["variant_id"]) for r in new_rows]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_bulk_seed.py::test_bulk_create_variants -v`
Expected: PASS

- [ ] **Step 5: Write the failing test for `bulk_write_translations`**

```python
def test_bulk_write_translations():
    reset_db()
    store = _VariantStore()
    ts = now_iso()
    with get_conn() as conn:
        _create_project_and_entries(conn, n=2)
        variant_ids = store.bulk_create_variants(
            [(1, "f.xlsx", "Hello", ts), (2, "f.xlsx", "World", ts)],
            conn=conn,
        )
        translation_rows = [
            (variant_ids[0], "fr", "Bonjour", ts),
            (variant_ids[0], "en", "Hello", ts),
            (variant_ids[1], "fr", "Monde", ts),
            (variant_ids[1], "en", "World", ts),
        ]
        store.bulk_write_translations(translation_rows, conn=conn)
        db_rows = conn.execute(
            "SELECT * FROM variant_translations ORDER BY variant_id, lang"
        ).fetchall()
        assert len(db_rows) == 4
        assert db_rows[0]["lang"] == "en"
        assert db_rows[0]["target_text"] == "Hello"
```

- [ ] **Step 6: Run test to verify it fails**

Run: `pytest tests/test_bulk_seed.py::test_bulk_write_translations -v`
Expected: FAIL with `AttributeError: '_VariantStore' object has no attribute 'bulk_write_translations'`

- [ ] **Step 7: Implement `bulk_write_translations` and `bulk_write_remarks`**

Add to `app/services/variant/store.py`:

```python
def bulk_write_translations(
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
        """,
        rows,
    )

def bulk_write_remarks(
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
        """,
        rows,
    )
```

- [ ] **Step 8: Run test to verify it passes**

Run: `pytest tests/test_bulk_seed.py::test_bulk_write_translations -v`
Expected: PASS

- [ ] **Step 9: Write the failing test for `bulk_write_remarks`**

```python
def test_bulk_write_remarks():
    reset_db()
    store = _VariantStore()
    ts = now_iso()
    with get_conn() as conn:
        _create_project_and_entries(conn, n=1)
        variant_ids = store.bulk_create_variants(
            [(1, "f.xlsx", "Hello", ts)],
            conn=conn,
        )
        remark_rows = [(variant_ids[0], "context", "greeting", ts)]
        store.bulk_write_remarks(remark_rows, conn=conn)
        db_rows = conn.execute("SELECT * FROM variant_remarks").fetchall()
        assert len(db_rows) == 1
        assert db_rows[0]["remark_key"] == "context"
        assert db_rows[0]["remark_value"] == "greeting"
```

- [ ] **Step 10: Run test to verify it passes (already implemented)**

Run: `pytest tests/test_bulk_seed.py::test_bulk_write_remarks -v`
Expected: PASS

- [ ] **Step 11: Commit**

```bash
git add app/services/variant/store.py tests/test_bulk_seed.py
git commit -m "feat: add bulk_create_variants, bulk_write_translations, bulk_write_remarks to _VariantStore"
```

---

### Task 2: Add `bulk_bind` to `_ScopeBindingStore`

**Files:**
- Modify: `app/services/variant/bindings.py`
- Test: `tests/test_bulk_seed.py`

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_bulk_seed.py
from app.services.variant.bindings import _ScopeBindingStore


def test_bulk_bind():
    reset_db()
    store = _VariantStore()
    binding_store = _ScopeBindingStore()
    ts = now_iso()
    with get_conn() as conn:
        _create_project_and_entries(conn, n=3)
        variant_ids = store.bulk_create_variants(
            [
                (1, "f.xlsx", "Hello", ts),
                (2, "f.xlsx", "World", ts),
                (3, "f.xlsx", "Foo", ts),
            ],
            conn=conn,
        )
        binding_rows = [
            ("rel", "current", 1, variant_ids[0], ts),
            ("rel", "current", 2, variant_ids[1], ts),
            ("rel", "current", 3, variant_ids[2], ts),
        ]
        binding_store.bulk_bind(binding_rows, conn=conn)
        db_rows = conn.execute(
            "SELECT * FROM scope_bindings ORDER BY entry_id"
        ).fetchall()
        assert len(db_rows) == 3
        assert db_rows[0]["scope_type"] == "rel"
        assert db_rows[0]["scope_value"] == "current"
        assert db_rows[0]["variant_id"] == variant_ids[0]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_bulk_seed.py::test_bulk_bind -v`
Expected: FAIL with `AttributeError: '_ScopeBindingStore' object has no attribute 'bulk_bind'`

- [ ] **Step 3: Implement `bulk_bind`**

Add to `_ScopeBindingStore` in `app/services/variant/bindings.py`:

```python
def bulk_bind(
    self,
    rows: list[tuple[str, str, int, int, str]],
    *,
    conn: sqlite3.Connection,
) -> None:
    if not rows:
        return
    conn.executemany(
        """
        INSERT INTO scope_bindings(scope_type, scope_value, entry_id, variant_id, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        [(st, sv, eid, vid, ts, ts) for st, sv, eid, vid, ts in rows],
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_bulk_seed.py::test_bulk_bind -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/variant/bindings.py tests/test_bulk_seed.py
git commit -m "feat: add bulk_bind to _ScopeBindingStore"
```

---

### Task 3: Create the Excel chunk reader

**Files:**
- Create: `app/services/bulk/__init__.py`
- Create: `app/services/bulk/excel_reader.py`
- Test: `tests/test_bulk_seed.py`

- [ ] **Step 1: Create the package init file**

```python
# app/services/bulk/__init__.py
```

(Empty file.)

- [ ] **Step 2: Write the failing test for `read_excel_chunks`**

Create a test that builds a small `.xlsx` file with openpyxl and reads it back via `read_excel_chunks`.

```python
# append to tests/test_bulk_seed.py
import openpyxl
from app.services.bulk.excel_reader import read_excel_chunks


def _create_test_workbook(path, headers, rows):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws.append(headers)
    for row in rows:
        ws.append(row)
    wb.save(path)


def test_read_excel_chunks_basic(tmp_path):
    workbook_path = tmp_path / "test.xlsx"
    _create_test_workbook(
        workbook_path,
        headers=["Key", "MsgStr", "fr", "en", "context"],
        rows=[
            ["key_1", "Hello", "Bonjour", "Hello", "greeting"],
            ["key_2", "World", "Monde", "World", "noun"],
            ["key_3", "Foo", "Fou", "Foo", "test"],
        ],
    )
    schema = {
        "fixed_columns": {"business_key": "Key", "source": "MsgStr", "file_name": "file_name"},
        "translation_columns": ["fr", "en"],
        "remark_columns": ["context"],
    }
    chunks = list(read_excel_chunks(str(workbook_path), schema, chunk_size=2))
    assert len(chunks) == 2
    assert len(chunks[0]) == 2
    assert len(chunks[1]) == 1
    first_row = chunks[0][0]
    assert first_row["business_key"] == "key_1"
    assert first_row["source"] == "Hello"
    assert first_row["translations"] == {"fr": "Bonjour", "en": "Hello"}
    assert first_row["remarks"] == {"context": "greeting"}
    assert first_row["file_name"] == "test.xlsx"
    assert first_row["sheet_name"] == "Sheet1"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_bulk_seed.py::test_read_excel_chunks_basic -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.bulk'`

- [ ] **Step 4: Implement `read_excel_chunks`**

Create `app/services/bulk/excel_reader.py`:

```python
from __future__ import annotations

from pathlib import Path
from typing import Any, Iterator

import openpyxl

from app.services.shared.io import (
    is_blank_value,
    normalize_content_map,
    normalize_non_content_value,
)


class BulkSeedError(Exception):
    def __init__(self, message: str, *, file_name: str = "", sheet_name: str = "", row_index: int = 0) -> None:
        self.file_name = file_name
        self.sheet_name = sheet_name
        self.row_index = row_index
        super().__init__(message)


def read_excel_chunks(
    workbook_path: str,
    schema: dict[str, Any],
    chunk_size: int = 5000,
) -> Iterator[list[dict[str, Any]]]:
    fixed_columns = schema["fixed_columns"]
    bk_header = fixed_columns["business_key"]
    src_header = fixed_columns["source"]
    translation_cols = schema["translation_columns"]
    remark_cols = schema["remark_columns"]

    wb = openpyxl.load_workbook(workbook_path, read_only=True, data_only=True)
    try:
        for ws in wb.worksheets:
            sheet_name = ws.title
            header_row = next(ws.iter_rows(min_row=1, max_row=1, values_only=True), None)
            if header_row is None:
                continue
            headers = [normalize_non_content_value(h) for h in header_row]
            col_map = _build_column_map(
                headers,
                bk_header=bk_header,
                src_header=src_header,
                translation_cols=translation_cols,
                remark_cols=remark_cols,
                file_name=Path(workbook_path).name,
                sheet_name=sheet_name,
            )
            file_name = Path(workbook_path).name
            chunk: list[dict[str, Any]] = []
            for row_index, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
                parsed = _parse_row(
                    row,
                    col_map=col_map,
                    file_name=file_name,
                    sheet_name=sheet_name,
                    row_index=row_index,
                    translation_cols=translation_cols,
                    remark_cols=remark_cols,
                )
                chunk.append(parsed)
                if len(chunk) >= chunk_size:
                    yield chunk
                    chunk = []
            if chunk:
                yield chunk
    finally:
        wb.close()


def _build_column_map(
    headers: list[str],
    *,
    bk_header: str,
    src_header: str,
    translation_cols: list[str],
    remark_cols: list[str],
    file_name: str,
    sheet_name: str,
) -> dict[str, int]:
    header_index = {h: i for i, h in enumerate(headers) if h}
    col_map: dict[str, int] = {}
    if bk_header not in header_index:
        raise BulkSeedError(
            f"missing required header: {bk_header}",
            file_name=file_name,
            sheet_name=sheet_name,
        )
    col_map["business_key"] = header_index[bk_header]
    if src_header not in header_index:
        raise BulkSeedError(
            f"missing required header: {src_header}",
            file_name=file_name,
            sheet_name=sheet_name,
        )
    col_map["source"] = header_index[src_header]
    for lang in translation_cols:
        if lang in header_index:
            col_map[f"t:{lang}"] = header_index[lang]
    for remark_key in remark_cols:
        if remark_key in header_index:
            col_map[f"r:{remark_key}"] = header_index[remark_key]
    return col_map


def _parse_row(
    row: tuple[Any, ...],
    *,
    col_map: dict[str, int],
    file_name: str,
    sheet_name: str,
    row_index: int,
    translation_cols: list[str],
    remark_cols: list[str],
) -> dict[str, Any]:
    def cell(key: str) -> Any:
        idx = col_map.get(key)
        if idx is None or idx >= len(row):
            return None
        return row[idx]

    business_key = normalize_non_content_value(cell("business_key"))
    source = normalize_non_content_value(cell("source"))
    if is_blank_value(business_key):
        raise BulkSeedError(
            f"blank business_key at row {row_index}",
            file_name=file_name,
            sheet_name=sheet_name,
            row_index=row_index,
        )
    if is_blank_value(source):
        raise BulkSeedError(
            f"blank source at row {row_index}",
            file_name=file_name,
            sheet_name=sheet_name,
            row_index=row_index,
        )
    translations: dict[str, Any] = {}
    for lang in translation_cols:
        key = f"t:{lang}"
        if key in col_map:
            translations[lang] = cell(key)
    remarks: dict[str, Any] = {}
    for remark_key in remark_cols:
        key = f"r:{remark_key}"
        if key in col_map:
            remarks[remark_key] = cell(key)
    return {
        "business_key": business_key,
        "source": source,
        "file_name": file_name,
        "sheet_name": sheet_name,
        "row_index": row_index,
        "translations": normalize_content_map(translations),
        "remarks": {k: normalize_non_content_value(v) for k, v in remarks.items()},
    }
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_bulk_seed.py::test_read_excel_chunks_basic -v`
Expected: PASS

- [ ] **Step 6: Write the failing test for error cases**

```python
def test_read_excel_chunks_fails_on_missing_header(tmp_path):
    workbook_path = tmp_path / "bad.xlsx"
    _create_test_workbook(workbook_path, headers=["Key", "wrong_col"], rows=[["k1", "v1"]])
    schema = {
        "fixed_columns": {"business_key": "Key", "source": "MsgStr", "file_name": "file_name"},
        "translation_columns": ["fr"],
        "remark_columns": [],
    }
    with pytest.raises(BulkSeedError, match="missing required header: MsgStr"):
        list(read_excel_chunks(str(workbook_path), schema))


def test_read_excel_chunks_fails_on_blank_business_key(tmp_path):
    workbook_path = tmp_path / "blank.xlsx"
    _create_test_workbook(
        workbook_path,
        headers=["Key", "MsgStr", "fr"],
        rows=[["", "Hello", "Bonjour"]],
    )
    schema = {
        "fixed_columns": {"business_key": "Key", "source": "MsgStr", "file_name": "file_name"},
        "translation_columns": ["fr"],
        "remark_columns": [],
    }
    with pytest.raises(BulkSeedError, match="blank business_key"):
        list(read_excel_chunks(str(workbook_path), schema))
```

- [ ] **Step 7: Run tests to verify they pass (already implemented)**

Run: `pytest tests/test_bulk_seed.py::test_read_excel_chunks_fails_on_missing_header tests/test_bulk_seed.py::test_read_excel_chunks_fails_on_blank_business_key -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add app/services/bulk/__init__.py app/services/bulk/excel_reader.py tests/test_bulk_seed.py
git commit -m "feat: add chunked Excel reader for bulk seed with normalize and fail-fast"
```

---

### Task 4: Create `BulkVariantWriter`

**Files:**
- Create: `app/services/bulk/writer.py`
- Test: `tests/test_bulk_seed.py`

- [ ] **Step 1: Write the failing integration test**

```python
# append to tests/test_bulk_seed.py
from app.services.bulk.writer import BulkVariantWriter
from app.services.project.service import ProjectService
from app.services.branch.models import BranchRef


def _create_project_with_schema():
    reset_db()
    service = ProjectService()
    project = service.create_project(
        "Test Project",
        ["fr", "en"],
        ["context"],
        business_key_header="Key",
        source_header="MsgStr",
    )
    return int(project["project_id"])


def test_bulk_writer_seed_rel_current(tmp_path):
    project_id = _create_project_with_schema()
    workbook_path = tmp_path / "data.xlsx"
    _create_test_workbook(
        workbook_path,
        headers=["Key", "MsgStr", "fr", "en", "context"],
        rows=[
            ["key_1", "Hello", "Bonjour", "Hello", "greeting"],
            ["key_2", "World", "Monde", "World", "noun"],
            ["key_3", "Foo", "Fou", "Foo", "test"],
        ],
    )
    writer = BulkVariantWriter()
    result = writer.seed(
        project_id=project_id,
        branch_ref=BranchRef.rel_current(),
        workbook_path=str(workbook_path),
        chunk_size=2,
    )
    assert result["entries_created"] == 3
    assert result["variants_created"] == 3
    assert result["bindings_created"] == 3
    # Verify DB state
    with get_conn() as conn:
        entries = conn.execute("SELECT * FROM entries WHERE project_id = ?", (project_id,)).fetchall()
        assert len(entries) == 3
        variants = conn.execute("SELECT * FROM variants").fetchall()
        assert len(variants) == 3
        assert all(v["pivot_status"] == "init" for v in variants)
        assert all(v["orphaned_at"] is None for v in variants)
        translations = conn.execute("SELECT * FROM variant_translations").fetchall()
        assert len(translations) == 6  # 3 variants × 2 languages
        remarks = conn.execute("SELECT * FROM variant_remarks").fetchall()
        assert len(remarks) == 3  # 3 variants × 1 remark column
        bindings = conn.execute("SELECT * FROM scope_bindings").fetchall()
        assert len(bindings) == 3
        assert all(b["scope_type"] == "rel" and b["scope_value"] == "current" for b in bindings)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_bulk_seed.py::test_bulk_writer_seed_rel_current -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.bulk.writer'`

- [ ] **Step 3: Implement `BulkVariantWriter`**

Create `app/services/bulk/writer.py`:

```python
from __future__ import annotations

import sqlite3
from time import perf_counter
from typing import Any

from app.db import get_conn
from app.services.branch.models import BranchRef
from app.services.branch.registry import BranchRegistryService
from app.services.bulk.excel_reader import read_excel_chunks
from app.services.project.service import ProjectService
from app.services.shared.utils import now_iso
from app.services.variant.entries import EntryRepository
from app.services.variant.store import _VariantStore
from app.services.variant.bindings import _ScopeBindingStore


class BulkVariantWriter:
    def __init__(self) -> None:
        self._projects = ProjectService()
        self._registry = BranchRegistryService()
        self._entries = EntryRepository()
        self._variant_store = _VariantStore()
        self._binding_store = _ScopeBindingStore()

    def seed(
        self,
        *,
        project_id: int,
        branch_ref: BranchRef,
        workbook_path: str,
        chunk_size: int = 5000,
    ) -> dict[str, Any]:
        self._projects.require_project(project_id)
        schema = self._projects.get_schema(project_id)

        with get_conn() as conn:
            self._require_no_variants(project_id, conn=conn)
            if branch_ref.is_dev:
                self._registry.ensure_dev_branch(
                    branch_ref.branch_value, project_id=project_id, conn=conn,
                )
                self._registry.require_not_bootstrapped(
                    branch_ref.branch_value, project_id=project_id, conn=conn,
                )

            started = perf_counter()
            scope_type, scope_value = branch_ref.as_tuple()
            total_entries = 0
            total_variants = 0
            total_bindings = 0

            for chunk in read_excel_chunks(workbook_path, schema, chunk_size):
                e, v, b = self._write_chunk(
                    chunk,
                    project_id=project_id,
                    scope_type=scope_type,
                    scope_value=scope_value,
                    schema=schema,
                    conn=conn,
                )
                total_entries += e
                total_variants += v
                total_bindings += b

            if branch_ref.is_dev:
                self._mark_dev_bootstrapped(branch_ref, project_id=project_id, conn=conn)

            elapsed_ms = int((perf_counter() - started) * 1000)

        return {
            "entries_created": total_entries,
            "variants_created": total_variants,
            "bindings_created": total_bindings,
            "elapsed_ms": elapsed_ms,
        }

    def _require_no_variants(self, project_id: int, *, conn: sqlite3.Connection) -> None:
        row = conn.execute(
            """
            SELECT COUNT(*) AS cnt FROM variants
            WHERE entry_id IN (SELECT entry_id FROM entries WHERE project_id = ?)
            """,
            (project_id,),
        ).fetchone()
        if int(row["cnt"]) > 0:
            raise ValueError(f"project {project_id} already has variant data; cannot seed")

    def _write_chunk(
        self,
        chunk: list[dict[str, Any]],
        *,
        project_id: int,
        scope_type: str,
        scope_value: str,
        schema: dict[str, Any],
        conn: sqlite3.Connection,
    ) -> tuple[int, int, int]:
        ts = now_iso()
        business_keys = [row["business_key"] for row in chunk]

        self._entries.insert_many_ignore(project_id, business_keys, ts, conn=conn)
        entry_map = self._entries.get_by_keys(project_id, business_keys, conn=conn)

        variant_insert_rows: list[tuple[int, str, str, str]] = []
        for row in chunk:
            entry_id = int(entry_map[row["business_key"]]["entry_id"])
            variant_insert_rows.append((entry_id, row["file_name"], row["source"], ts))

        variant_ids = self._variant_store.bulk_create_variants(variant_insert_rows, conn=conn)

        translation_rows: list[tuple[int, str, str, str]] = []
        remark_rows: list[tuple[int, str, str, str]] = []
        for variant_id, row in zip(variant_ids, chunk):
            for lang, text in row["translations"].items():
                translation_rows.append((variant_id, lang, text, ts))
            for remark_key, remark_value in row["remarks"].items():
                remark_rows.append((variant_id, remark_key, remark_value, ts))

        self._variant_store.bulk_write_translations(translation_rows, conn=conn)
        self._variant_store.bulk_write_remarks(remark_rows, conn=conn)

        binding_rows: list[tuple[str, str, int, int, str]] = []
        for variant_id, row in zip(variant_ids, chunk):
            entry_id = int(entry_map[row["business_key"]]["entry_id"])
            binding_rows.append((scope_type, scope_value, entry_id, variant_id, ts))

        self._binding_store.bulk_bind(binding_rows, conn=conn)

        return len(business_keys), len(variant_ids), len(binding_rows)

    def _mark_dev_bootstrapped(
        self,
        branch_ref: BranchRef,
        *,
        project_id: int,
        conn: sqlite3.Connection,
    ) -> None:
        marker = now_iso()
        conn.execute(
            """
            UPDATE dev_versions
            SET bootstrapped_at = ?
            WHERE project_id = ? AND version = ? AND bootstrapped_at IS NULL
            """,
            (marker, project_id, branch_ref.branch_value),
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_bulk_seed.py::test_bulk_writer_seed_rel_current -v`
Expected: PASS

- [ ] **Step 5: Write the failing test for dev branch seeding**

```python
def test_bulk_writer_seed_dev_branch(tmp_path):
    project_id = _create_project_with_schema()
    workbook_path = tmp_path / "data.xlsx"
    _create_test_workbook(
        workbook_path,
        headers=["Key", "MsgStr", "fr", "en", "context"],
        rows=[["key_1", "Hello", "Bonjour", "Hello", "greeting"]],
    )
    writer = BulkVariantWriter()
    result = writer.seed(
        project_id=project_id,
        branch_ref=BranchRef.dev("2.4.1"),
        workbook_path=str(workbook_path),
    )
    assert result["variants_created"] == 1
    with get_conn() as conn:
        bindings = conn.execute("SELECT * FROM scope_bindings").fetchall()
        assert bindings[0]["scope_type"] == "dev"
        assert bindings[0]["scope_value"] == "2.4.1"
        dev_row = conn.execute(
            "SELECT * FROM dev_versions WHERE version = '2.4.1'"
        ).fetchone()
        assert dev_row["bootstrapped_at"] is not None
```

- [ ] **Step 6: Run test to verify it passes (already implemented)**

Run: `pytest tests/test_bulk_seed.py::test_bulk_writer_seed_dev_branch -v`
Expected: PASS

- [ ] **Step 7: Write the failing test for the guard — project has existing variants**

```python
def test_bulk_writer_rejects_nonempty_project(tmp_path):
    project_id = _create_project_with_schema()
    workbook_path = tmp_path / "data.xlsx"
    _create_test_workbook(
        workbook_path,
        headers=["Key", "MsgStr", "fr", "en", "context"],
        rows=[["key_1", "Hello", "Bonjour", "Hello", "greeting"]],
    )
    writer = BulkVariantWriter()
    writer.seed(
        project_id=project_id,
        branch_ref=BranchRef.rel_current(),
        workbook_path=str(workbook_path),
    )
    # Second seed should fail
    workbook_path2 = tmp_path / "data2.xlsx"
    _create_test_workbook(
        workbook_path2,
        headers=["Key", "MsgStr", "fr", "en", "context"],
        rows=[["key_2", "World", "Monde", "World", "noun"]],
    )
    with pytest.raises(ValueError, match="already has variant data"):
        writer.seed(
            project_id=project_id,
            branch_ref=BranchRef.rel_current(),
            workbook_path=str(workbook_path2),
        )
```

- [ ] **Step 8: Run test to verify it passes (already implemented)**

Run: `pytest tests/test_bulk_seed.py::test_bulk_writer_rejects_nonempty_project -v`
Expected: PASS

- [ ] **Step 9: Commit**

```bash
git add app/services/bulk/writer.py tests/test_bulk_seed.py
git commit -m "feat: add BulkVariantWriter service for project cold-start seeding"
```

---

### Task 5: Create the CLI script

**Files:**
- Create: `scripts/seed_variants.py`
- Test: `tests/test_bulk_seed.py`

- [ ] **Step 1: Write the failing test for CLI argument parsing**

```python
# append to tests/test_bulk_seed.py
import subprocess
import sys


def test_cli_missing_args():
    result = subprocess.run(
        [sys.executable, "scripts/seed_variants.py"],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "required" in result.stderr.lower() or "error" in result.stderr.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_bulk_seed.py::test_cli_missing_args -v`
Expected: FAIL (script doesn't exist)

- [ ] **Step 3: Implement the CLI script**

Create `scripts/seed_variants.py`:

```python
#!/usr/bin/env python
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import init_db
from app.services.branch.models import BranchRef
from app.services.bulk.writer import BulkVariantWriter


def main() -> None:
    parser = argparse.ArgumentParser(description="Bulk-seed variants into an empty project")
    parser.add_argument("--project-id", type=int, required=True, help="Target project ID (must exist, zero variants)")
    parser.add_argument("--branch", type=str, required=True, help="Target branch, e.g. rel/current or dev/2.4.1")
    parser.add_argument("--workbook", type=str, required=True, help="Path to .xlsx workbook")
    parser.add_argument("--chunk-size", type=int, default=5000, help="Rows per write chunk (default: 5000)")
    args = parser.parse_args()

    workbook_path = Path(args.workbook)
    if not workbook_path.exists():
        print(f"ERROR: workbook not found: {workbook_path}", file=sys.stderr)
        sys.exit(1)

    try:
        branch_ref = BranchRef.parse(args.branch)
    except ValueError as exc:
        print(f"ERROR: invalid branch: {exc}", file=sys.stderr)
        sys.exit(1)

    init_db()
    writer = BulkVariantWriter()
    try:
        result = writer.seed(
            project_id=args.project_id,
            branch_ref=branch_ref,
            workbook_path=str(workbook_path),
            chunk_size=args.chunk_size,
        )
    except (ValueError, KeyError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"Seed complete:")
    print(f"  entries created:  {result['entries_created']}")
    print(f"  variants created: {result['variants_created']}")
    print(f"  bindings created: {result['bindings_created']}")
    print(f"  elapsed:          {result['elapsed_ms']}ms")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_bulk_seed.py::test_cli_missing_args -v`
Expected: PASS

- [ ] **Step 5: Write the end-to-end CLI test**

```python
def test_cli_end_to_end(tmp_path, monkeypatch):
    db_path = tmp_path / "data" / "tms.db"
    monkeypatch.setenv("MOMO_TMS_DB_PATH", str(db_path))
    workbook_path = tmp_path / "data.xlsx"
    _create_test_workbook(
        workbook_path,
        headers=["Key", "MsgStr", "fr", "en", "context"],
        rows=[
            ["key_1", "Hello", "Bonjour", "Hello", "greeting"],
            ["key_2", "World", "Monde", "World", "noun"],
        ],
    )
    # Create project via service
    init_db()
    service = ProjectService()
    project = service.create_project(
        "CLI Test",
        ["fr", "en"],
        ["context"],
        business_key_header="Key",
        source_header="MsgStr",
    )
    project_id = int(project["project_id"])

    result = subprocess.run(
        [
            sys.executable, "scripts/seed_variants.py",
            "--project-id", str(project_id),
            "--branch", "rel/current",
            "--workbook", str(workbook_path),
        ],
        capture_output=True,
        text=True,
        env={**__import__("os").environ, "MOMO_TMS_DB_PATH": str(db_path)},
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert "entries created:  2" in result.stdout
    assert "variants created: 2" in result.stdout
    assert "bindings created: 2" in result.stdout
```

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest tests/test_bulk_seed.py::test_cli_end_to_end -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add scripts/seed_variants.py tests/test_bulk_seed.py
git commit -m "feat: add seed_variants.py CLI script for bulk project initialization"
```

---

### Task 6: Run full test suite and verify no regressions

**Files:**
- No new files

- [ ] **Step 1: Run the bulk seed tests**

Run: `pytest tests/test_bulk_seed.py -v`
Expected: All tests PASS

- [ ] **Step 2: Run the full test suite**

Run: `pytest tests/ -v`
Expected: All existing tests still PASS (no regressions — bulk path is pure additive)

- [ ] **Step 3: Commit (if any fixups needed)**

Only if test failures require adjustments.

---

### Task 7: Final commit with all files

**Files:**
- All new and modified files

- [ ] **Step 1: Verify all files are committed**

Run: `git status`
Expected: Clean working tree

- [ ] **Step 2: If uncommitted files remain, create a final commit**

```bash
git add -A
git commit -m "feat: bulk variant seed — complete implementation with tests"
```
