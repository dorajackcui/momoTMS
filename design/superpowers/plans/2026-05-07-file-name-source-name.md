# Source.Name File Name Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `variants.file_name` come from the workbook `Source.Name` column and stop deriving it from imported workbook paths.

**Architecture:** Keep `file_path` as import transport metadata in `import_rows`, while `payload.file_name` becomes an optional sparse business field. Classic import, workbook batch intake, bootstrap, content mutation, and bulk seed all converge on the same rule: only mapped `Source.Name` supplies `file_name`; missing mapping means omit the payload key and preserve existing values.

**Tech Stack:** FastAPI services in Python, SQLite persistence, openpyxl workbook parsing, pytest regressions, Markdown docs validation.

---

## File Structure

- Modify `app/services/project/service.py`: expose optional `file_name` mapping with default header `Source.Name`, and remove `file_name` from fixed project schema.
- Modify `app/services/imports/service.py`: persist `payload.file_name` only when the file-name mapping exists.
- Modify `app/services/workbooks/models.py`: add optional `file_name` to parsed workbook rows.
- Modify `app/services/workbooks/parser.py`: resolve optional `Source.Name` and parse it as non-content metadata.
- Modify `app/services/workbooks/batches.py`: include `payload.file_name` only when parsed from the workbook.
- Modify `app/services/branch/bootstrap.py`: remove `row["file_path"]` fallback for created bare variants.
- Modify `app/services/bulk/excel_reader.py`: read optional `Source.Name` instead of using `Path(workbook_path).name` as row `file_name`.
- Modify tests in `tests/test_project_service.py`, `tests/test_workbook_intake.py`, `tests/test_branch_service.py`, and `tests/test_bulk_seed.py`.
- Modify active docs `docs/system.md` and `docs/workflows.md`.

### Task 1: Classic Import Mapping

**Files:**
- Modify: `tests/test_project_service.py`
- Modify: `tests/test_branch_service.py`
- Modify: `app/services/project/service.py`
- Modify: `app/services/imports/service.py`

- [ ] **Step 1: Write failing tests for optional Source.Name mapping**

Add `test_preview_and_resolve_headers_suggest_source_name_file_name_mapping` in `tests/test_project_service.py`:

```python
def test_preview_and_resolve_headers_suggest_source_name_file_name_mapping() -> None:
    reset_db()
    service = ProjectService()

    project = service.create_project("File Name Mapping", ["fr"], ["context"])
    project_id = int(project["project_id"])
    preview = service.preview_headers(["Source.Name", "business_key", "source", "fr"], project_id)
    mapping = service.resolve_headers(["Source.Name", "business_key", "source", "fr"], project_id)

    assert preview["suggested_mapping"]["file_name"] == "Source.Name"
    assert mapping["file_name"] == 1
```

Add `test_import_batch_reads_file_name_from_source_name_column` and
`test_import_batch_omits_file_name_when_source_name_is_absent` in
`tests/test_branch_service.py` near the import-batch sparse patch tests:

```python
def test_import_batch_reads_file_name_from_source_name_column(tmp_path) -> None:
    reset_demo()

    import_root = tmp_path / "source-name-import"
    write_import_workbook(
        import_root,
        "bundle/upload.xlsx",
        [
            ["Source.Name", "business_key", "source", "fr"],
            ["business/sheet-value.xlsx", "source.name.import", "Source text", "Bonjour"],
        ],
    )
    batch = ImportService().import_directory(str(import_root))
    report = ImportService().import_report(batch["import_batch_id"])

    assert report["rows"][0]["file_path"] == "bundle/upload.xlsx"
    assert report["rows"][0]["payload"]["file_name"] == "business/sheet-value.xlsx"


def test_import_batch_omits_file_name_when_source_name_is_absent(tmp_path) -> None:
    reset_demo()

    import_root = tmp_path / "missing-source-name-import"
    write_import_workbook(
        import_root,
        "bundle/upload.xlsx",
        [
            ["business_key", "source", "fr"],
            ["source.name.absent", "Source text", "Bonjour"],
        ],
    )
    batch = ImportService().import_directory(str(import_root))
    report = ImportService().import_report(batch["import_batch_id"])

    assert report["rows"][0]["file_path"] == "bundle/upload.xlsx"
    assert "file_name" not in report["rows"][0]["payload"]
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_project_service.py::test_preview_and_resolve_headers_suggest_source_name_file_name_mapping tests/test_branch_service.py::test_import_batch_reads_file_name_from_source_name_column tests/test_branch_service.py::test_import_batch_omits_file_name_when_source_name_is_absent
```

Expected: the first test fails because `file_name` mapping is not resolved from `Source.Name`, and the import tests fail because payload currently uses workbook path or lacks the new sparse behavior.

- [ ] **Step 3: Implement classic import mapping**

In `app/services/project/service.py`:

- Set `FIXED_COLUMNS` to only `business_key` and `source`.
- Add `FILE_NAME_HEADER = "Source.Name"`.
- Stop storing `file_name` in `fixed_columns`.
- In `preview_headers`, suggest `file_name` as `"Source.Name"` only when present.
- In `resolve_headers`, resolve optional `file_name` before translation and remark columns.

In `app/services/imports/service.py`:

- Change `_extract_payload` so the base payload contains `business_key`, `source`, `translations`, and `remarks`.
- If `mapping["file_name"]` is not `None`, set `payload["file_name"]` from that cell using non-content normalization.
- Never set `payload["file_name"]` from `file_path`.

- [ ] **Step 4: Run focused tests to verify pass**

Run the same pytest command from Step 2. Expected: all selected tests pass.

### Task 2: Workbook Batch And Branch Workflows

**Files:**
- Modify: `tests/test_workbook_intake.py`
- Modify: `tests/test_branch_service.py`
- Modify: `app/services/workbooks/models.py`
- Modify: `app/services/workbooks/parser.py`
- Modify: `app/services/workbooks/batches.py`
- Modify: `app/services/branch/bootstrap.py`

- [ ] **Step 1: Write failing tests for workbook batch sparse file_name behavior**

Add `test_workbook_batch_reads_file_name_from_source_name_column` in
`tests/test_workbook_intake.py`:

```python
def test_workbook_batch_reads_file_name_from_source_name_column(tmp_path) -> None:
    reset_demo()
    project = ProjectService().create_project(
        "Batch Source Name Project",
        ["fr"],
        ["context"],
        business_key_header="key",
        source_header="source_text",
    )
    root = tmp_path / "batch-source-name"
    write_workbook(
        root,
        "bundle/messages.xlsx",
        [
            ["Source.Name", "key", "source_text", "fr"],
            ["business/from-column.xlsx", "hello.key", "Hello", "Bonjour"],
        ],
    )

    batch = WorkbookBatchService().create_batch_from_directory(
        root,
        int(project["project_id"]),
        WorkbookWorkflowContext(workflow_kind="branch_mutation", mutation_type="range"),
    )
    rows = list(WorkbookBatchService().iter_rows(batch["workbook_batch_id"], int(project["project_id"])))

    assert rows[0]["file_path"] == "bundle/messages.xlsx"
    assert rows[0]["payload"]["file_name"] == "business/from-column.xlsx"
```

Add `test_workbook_content_mutation_preserves_and_clears_file_name_by_source_name_mapping`
in `tests/test_branch_service.py` near the workbook content mutation test:

```python
def test_workbook_content_mutation_preserves_and_clears_file_name_by_source_name_mapping(tmp_path) -> None:
    reset_demo()
    services = branch_services()
    entry = services.entries.get_or_create_entry("content.file.name", project_id=1)
    variant_id = services.catalog.create_variant(
        int(entry["entry_id"]),
        services.catalog.build_content(
            "business/original.xlsx",
            "Current source",
            {"fr": "Original"},
            {"context": "Original context"},
        ),
    )
    services.bindings.bind(int(entry["entry_id"]), BranchRef.dev("2.4.3"), variant_id)

    preserve_root = tmp_path / "content-preserve-file-name"
    write_import_workbook(
        preserve_root,
        "bundle/upload.xlsx",
        [
            ["business_key", "source", "fr"],
            ["content.file.name", "Current source", "Updated once"],
        ],
    )
    preserve_batch = WorkbookBatchService().create_batch_from_directory(
        preserve_root,
        1,
        WorkbookWorkflowContext(workflow_kind="branch_mutation", mutation_type="content"),
    )
    BranchMutationService().apply(
        BranchRef.dev("2.4.3"),
        {
            "kind": "workbook_batch",
            "mutation_type": "content",
            "workbook_batch_id": preserve_batch["workbook_batch_id"],
        },
    )
    assert services.catalog.get_variant(variant_id)["file_name"] == "business/original.xlsx"

    clear_root = tmp_path / "content-clear-file-name"
    write_import_workbook(
        clear_root,
        "bundle/upload.xlsx",
        [
            ["Source.Name", "business_key", "source", "fr"],
            ["", "content.file.name", "Current source", "Updated twice"],
        ],
    )
    clear_batch = WorkbookBatchService().create_batch_from_directory(
        clear_root,
        1,
        WorkbookWorkflowContext(workflow_kind="branch_mutation", mutation_type="content"),
    )
    BranchMutationService().apply(
        BranchRef.dev("2.4.3"),
        {
            "kind": "workbook_batch",
            "mutation_type": "content",
            "workbook_batch_id": clear_batch["workbook_batch_id"],
        },
    )

    updated = services.catalog.get_variant(variant_id)
    assert updated["file_name"] == ""
    assert updated["translations"]["fr"] == "Updated twice"
```

Add `test_branch_bootstrap_created_variant_does_not_fallback_to_file_path`
in `tests/test_branch_service.py`:

```python
def test_branch_bootstrap_created_variant_does_not_fallback_to_file_path(tmp_path) -> None:
    reset_demo()
    root = tmp_path / "bootstrap-file-name"
    write_import_workbook(
        root,
        "bundle/bootstrap.xlsx",
        [
            ["business_key", "source"],
            ["bootstrap.file.name", "Bootstrap source"],
        ],
    )
    batch = WorkbookBatchService().create_batch_from_directory(
        root,
        1,
        WorkbookWorkflowContext(workflow_kind="create_branch"),
    )
    dev_ref = BranchRef.dev("2.4.3")
    BranchBootstrapService().bootstrap(dev_ref, batch["workbook_batch_id"], project_id=1)

    rows = branch_rows(dev_ref)
    variant = branch_services().catalog.get_variant(int(rows["bootstrap.file.name"]["variant_id"]))
    assert variant["file_name"] == ""
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_workbook_intake.py::test_workbook_batch_reads_file_name_from_source_name_column tests/test_branch_service.py::test_workbook_content_mutation_preserves_and_clears_file_name_by_source_name_mapping tests/test_branch_service.py::test_branch_bootstrap_created_variant_does_not_fallback_to_file_path
```

Expected: tests fail because workbook batches still use upload paths as file names and bootstrap falls back to `file_path`.

- [ ] **Step 3: Implement workbook batch and bootstrap behavior**

In `app/services/workbooks/models.py`, add:

```python
    file_name: str | None = None
```

to `WorkbookRow`.

In `app/services/workbooks/parser.py`:

- Add `file_name` to resolved mapping as `normalized.get("Source.Name")`.
- Extract `file_name` only when the index exists.
- Pass the optional value into `WorkbookRow`.

In `app/services/workbooks/batches.py`:

- Build payload without `file_name` by default.
- Add `payload["file_name"] = row.file_name` only when `row.file_name is not None`.

In `app/services/branch/bootstrap.py`:

- Change `file_name = payload.get("file_name") or row["file_path"]` to `file_name = payload.get("file_name")`.

- [ ] **Step 4: Run focused tests to verify pass**

Run the same pytest command from Step 2. Expected: all selected tests pass.

### Task 3: Bulk Seed

**Files:**
- Modify: `tests/test_bulk_seed.py`
- Modify: `app/services/bulk/excel_reader.py`

- [ ] **Step 1: Write failing tests for bulk seed Source.Name behavior**

Update `test_read_excel_chunks_basic` headers and rows to include `Source.Name`,
then assert the parsed row uses that value:

```python
headers=["Source.Name", "Key", "MsgStr", "fr", "en", "context"],
rows=[
    ["business/test.xlsx", "key_1", "Hello", "Bonjour", "Hello", "greeting"],
    ["business/test.xlsx", "key_2", "World", "Monde", "World", "noun"],
    ["business/test.xlsx", "key_3", "Foo", "Fou", "Foo", "test"],
],
...
assert first_row["file_name"] == "business/test.xlsx"
```

Add `test_read_excel_chunks_uses_empty_file_name_without_source_name_column`:

```python
def test_read_excel_chunks_uses_empty_file_name_without_source_name_column(tmp_path):
    workbook_path = tmp_path / "physical.xlsx"
    _create_test_workbook(
        workbook_path,
        headers=["Key", "MsgStr", "fr"],
        rows=[["key_1", "Hello", "Bonjour"]],
    )
    schema = {
        "fixed_columns": {"business_key": "Key", "source": "MsgStr"},
        "translation_columns": ["fr"],
        "remark_columns": [],
    }

    chunks = list(read_excel_chunks(str(workbook_path), schema, chunk_size=2))

    assert chunks[0][0]["file_name"] == ""
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_bulk_seed.py::test_read_excel_chunks_basic tests/test_bulk_seed.py::test_read_excel_chunks_uses_empty_file_name_without_source_name_column
```

Expected: tests fail because bulk seed still uses `Path(workbook_path).name`.

- [ ] **Step 3: Implement bulk seed Source.Name parsing**

In `app/services/bulk/excel_reader.py`:

- Add `SOURCE_NAME_HEADER = "Source.Name"`.
- Add `file_name` to the column map only when that header exists.
- Pass the workbook physical name only to `BulkSeedError` context.
- In `_parse_row`, set `"file_name": normalize_non_content_value(cell("file_name"))`.

- [ ] **Step 4: Run focused tests to verify pass**

Run the same pytest command from Step 2. Expected: both selected tests pass.

### Task 4: Active Docs And Regression Verification

**Files:**
- Modify: `docs/system.md`
- Modify: `docs/workflows.md`

- [ ] **Step 1: Update active docs**

In `docs/system.md`:

- Change schema description so fixed columns are only `business_key` and `source`.
- Describe `file_name` as variant business metadata sourced from `Source.Name`.

In `docs/workflows.md`:

- Keep `file_name` under non-content normalization.
- Replace path-derived language with `Source.Name` mapping.
- State missing `Source.Name` is sparse and does not update existing values.
- State import transport paths remain `file_path`.
- State bootstrap does not fall back to workbook path.

- [ ] **Step 2: Run focused regression suites**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_project_service.py tests/test_workbook_intake.py tests/test_bulk_seed.py tests/test_branch_service.py tests/test_tdd_branch_cycle.py
```

Expected: all selected tests pass.

- [ ] **Step 3: Run docs validation**

Run:

```powershell
.\.venv\Scripts\python.exe scripts\validate_docs.py
```

Expected: docs validation exits with status 0.

- [ ] **Step 4: Review final diff**

Run:

```powershell
git diff --check
git diff --stat
```

Expected: no whitespace errors; diff is scoped to mapping, parser, bootstrap, bulk seed, tests, and docs.
