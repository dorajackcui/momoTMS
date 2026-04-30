# Bulk Variant Seed — Design Spec

## Problem

Creating a new project with 200K variants through the existing frontend workbook import path is too slow. The current flow (Excel → import_rows → per-row bootstrap) generates ~2.8M individual SQL statements for 200K rows. This spec defines a high-performance bulk path for project initialization.

## Scope

- **In scope**: Scene 1 only — cold-start initialization of a new project that has zero variant data
- **Out of scope**: Dev branch creation from existing data (scene 2), daily operator workflows, UI entry points

## Constraints & Assumptions

- Project and schema already exist before the script runs
- The project contains zero variants (enforced at script entry)
- Input Excel is human-prechecked: business_key is unique, source is non-empty, no duplicate variants
- Target branch is configurable: `rel/current` or `dev/<version>`
- All created variants get `pivot_status = init`
- Single transaction: all-or-nothing write, no partial success
- Fail-fast on any validation error
- No job, report, preview, or import_rows artifacts produced
- Does not modify any existing code path — pure additive change

## Architecture

```
scripts/seed_variants.py            CLI entry point
        │
        ▼
app/services/bulk/writer.py         BulkVariantWriter (orchestration)
        │
        ├── app/services/bulk/excel_reader.py    chunk-based Excel reader + normalize
        │
        ├── Reused (read-only calls):
        │   ├── ProjectService.require_project()
        │   ├── ProjectService schema loading
        │   ├── BranchRegistryService.ensure_dev_branch()
        │   └── BranchRegistryService.mark_bootstrapped()
        │
        ├── Reused (write calls):
        │   └── EntryRepository.insert_many_ignore() + get_by_keys()
        │
        └── New bulk methods:
            ├── VariantCommandRepository.bulk_create()
            ├── VariantCommandRepository.bulk_write_translations()
            ├── VariantCommandRepository.bulk_write_remarks()
            └── BindingLookupService.bulk_bind() or new method on bindings.py
```

## CLI Interface

```bash
python scripts/seed_variants.py \
  --project-id 1 \
  --branch rel/current \
  --workbook path/to/data.xlsx \
  [--chunk-size 5000]
```

- `--project-id`: required, target project must exist with zero variant data
- `--branch`: required, `rel/current` or `dev/<version>`
- `--workbook`: Excel file path, headers must match project schema column mapping
- `--chunk-size`: optional, default 5000

Output: terminal statistics (entries created, variants created, bindings created, elapsed time).

## BulkVariantWriter Flow

```python
class BulkVariantWriter:
    def seed(self, project_id, branch_ref, workbook_path, chunk_size=5000):
        # 1. Entry guards
        require_project_exists(project_id)
        require_no_variants(project_id)
        if branch_ref.is_dev:
            ensure_dev_branch(branch_ref)

        # 2. Load schema → build header mapping
        schema = load_project_schema(project_id)

        # 3. Single transaction, chunked writes
        with get_conn() as conn:
            for chunk in read_excel_chunks(workbook_path, schema, chunk_size):
                write_chunk(chunk, project_id, branch_ref, schema, conn)

            # 4. If dev branch, mark bootstrapped
            if branch_ref.is_dev:
                mark_bootstrapped(branch_ref, conn=conn)
```

## Per-Chunk Write Sequence

For each chunk of N rows (default 5000):

```
1. INSERT OR IGNORE INTO entries              — executemany, N rows
2. SELECT entry_id, business_key WHERE IN()   — fetch entry_id mapping
3. INSERT INTO variants                       — executemany, N rows
4. INSERT INTO variant_translations           — executemany, N × len(translation_cols)
5. INSERT INTO variant_remarks                — executemany, N × len(remark_cols)
6. INSERT INTO scope_bindings                 — executemany, N rows
```

No per-row queries. No existence checks on variants (project is empty by precondition).

## Normalization & Validation

Reuses existing functions from `app/services/shared/io.py`:

- `normalize_non_content_value()` for business_key, source, file_name, remark columns
- `normalize_content_map()` for translation columns
- `is_blank_value()` for empty checks

Fail-fast validation during Excel reading:

- Header row must match schema column mapping (business_key_header, source_header, translation/remark column names)
- Each row must have non-blank business_key and source after normalization
- Any violation → immediate error with file name, sheet name, and row number

## Error Handling & Transaction

| Phase | Check | Failure behavior |
|-------|-------|------------------|
| Script entry | project exists, zero variants, branch valid | Error and exit, nothing written |
| Excel parsing | headers match schema, key/source non-blank | Error with row location, nothing written |
| Chunk write | executemany exception | Transaction rollback, error and exit |

Single transaction for the entire seed operation. On any failure, full rollback — no partial data.

Crash recovery: re-run the script. Entry guard `require_no_variants` will either pass (nothing was committed) or fail (telling the admin to reset the project first).

## Files Changed

**New files**:

- `app/services/bulk/__init__.py`
- `app/services/bulk/writer.py` — BulkVariantWriter
- `app/services/bulk/excel_reader.py` — chunked Excel reader with normalize
- `scripts/seed_variants.py` — CLI entry point

**Modified files**:

- `app/services/variant/repositories.py` — add `bulk_create`, `bulk_write_translations`, `bulk_write_remarks`
- `app/services/variant/bindings.py` — add `bulk_bind` to `BindingLookupService` or as standalone function

**Untouched**:

- `app/services/branch/bootstrap.py` — existing bootstrap path unchanged
- `app/services/workbooks/` — existing workbook workflow unchanged
- `app/routers/` — no new API routes
- Frontend — no changes

## Performance Expectation

| | Current workflow path | Bulk path |
|---|---|---|
| SQL statements | ~2.8M (per-row INSERT) | ~tens (executemany batches) |
| Intermediate IO | import_rows write + readback | None |
| Expected time (200K rows) | Minutes | Seconds |
