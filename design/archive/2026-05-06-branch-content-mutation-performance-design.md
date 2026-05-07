# Branch Content Mutation Performance Design

## Status

- drafted on 2026-05-06
- approved for design capture in discussion

## Purpose

Define the first performance pass for branch content mutation. The target path is
`workbook_batch + mutation_type = content`, especially the branch-cycle flow where
a dev branch is bootstrapped first and then populated from the same dev workbook.

## Problem Statement

The focused branch-cycle workflow has a known long-running risk in the dev content
mutation step. The workflow is:

1. bulk seed `rel/current` from a 2.4 workbook
2. bootstrap `dev/<version>` from a 2.5 workbook
3. apply a dev content mutation from that same 2.5 workbook

Bootstrap establishes branch range and creates bare dev-only variants for new
sources. Content mutation then fills translations and remarks without changing
branch range.

The current content mutation implementation is chunked at the workbook reader
level, but the apply path still behaves like a row-at-a-time system:

- per-row entry lookup
- per-row branch binding lookup
- per-row current variant hydration
- per-row binding list lookup for authority
- per-row full variant update through translation and remark delete/reinsert

This is too expensive for large workbooks such as 200000 input rows where about
10000 rows update 9 translation columns.

## Goals

- Optimize only content mutation in the first pass.
- Preserve the public route, input shape, report statuses, semantic fields, and
  transaction semantics.
- Keep content mutation range-stable: no bind, rebind, create, or branch range
  changes.
- Use project schema as the contract. Extra workbook columns are ignored.
- Treat mapped blank cells as explicit clears by writing `""`.
- Make content mutation apply finish within 60 seconds for the target large
  workbook shape, with 30 seconds as the stretch target.
- Keep the design compatible with a later shared bulk mutation resolver for
  range/import mutation.

## Non-Goals

- Do not redesign range mutation or import-batch mutation in this first pass.
- Do not change bootstrap semantics.
- Do not change workbook upload, parser, or public API contracts except for
  optional timing/progress observability.
- Do not add compatibility behavior for old databases beyond the normal current
  runtime reset or reseed boundary.

## Recommended Approach

Start with a dedicated content mutation bulk pipeline, but structure the code so
the resolve phase can later be reused by range mutation.

Rejected alternatives:

- Only add indexes and keep row-at-a-time mutation. This reduces some scans but
  still leaves too many Python and SQL round trips.
- Build a full shared bulk mutation engine immediately. That is the cleaner final
  shape, but it expands the first pass into range mutation, create, rebind,
  orphan, and authority interactions at the same time.

## Pipeline

### 1. Chunk Read

Read ok workbook rows in chunks. A chunk size of 1000 is safe; 5000 may be used
after measuring memory and query performance.

Rows remain ordered by `import_row_id`. If a workbook contains duplicate
business keys, later rows continue to apply after earlier rows, preserving the
current row-order semantics.

### 2. Bulk Resolve

For each chunk, resolve data in batches:

- `business_key -> entry_id`
- `entry_id -> current binding for the target branch`
- `variant_id -> current variant content`
- `variant_id -> all bound branch refs or highest authority`

Expected query families:

- entries by project plus business key
- target branch bindings for touched entries
- all bindings for touched entries or touched variant ids
- variants by current binding ids
- translations and remarks for touched variant ids

The resolver returns a row context that can be understood without reading the
write internals: missing entry, missing binding, source mismatch, current
variant, old content, and bound branch authority.

### 3. Classify

Classify each row in memory:

- missing entry or missing binding: `MISSING_IN_SCOPE`
- current variant source differs from workbook source: `SOURCE_MISMATCH`
- schema-mapped payload equals current content: `NOOP`
- content changes but actor branch lacks authority: `NOOP` with
  `content_filtered_by_authority = true`
- content changes and authority allows it: add to the update write-set and
  report `UPDATED_BOUND_VARIANT`

Authority is still required. It should be a batch-resolved in-memory decision,
not a per-row SQL lookup.

### 4. Sparse Write-Set

Only allowed changed rows enter the write-set.

Translation writes:

- one row per changed schema translation field
- mapped blank cells write `""`
- unmapped schema columns are omitted and preserve existing values
- workbook columns outside project schema are ignored before this stage

Remark writes follow the same rules.

Variant metadata writes:

- update `file_name` and `updated_at` when the effective content changes
- source must stay unchanged in content mutation; source mismatch is a report row,
  not a write

Use batched upsert for translation and remark rows instead of deleting and
rewriting every field for each variant.

### 5. Pivot Refresh

Content mutation can change pivot state when the project pivot-language value
changes.

The bulk path should compare old and new pivot-language values during
classification. For allowed rows where the value changes:

- set `pivot_status = changed`
- set changed-owner branch metadata to the actor branch
- update `pivot_changed_at` and `pivot_status_updated_at`

No-op rows, non-pivot-language changes, and authority-filtered rows must not
change pivot state.

### 6. Report And Summary

Keep current row statuses and semantic fields:

- `UPDATED_BOUND_VARIANT`
- `NOOP`
- `MISSING_IN_SCOPE`
- `SOURCE_MISMATCH`
- `mutation_class`
- `binding_effect`
- `content_effect`
- `variant_resolution`
- `row_outcome`

For small tests, returning `report_rows` in memory is acceptable. For the large
smoke path, the implementation should support streaming or chunk-buffered report
writing so 200000 report rows do not stay in memory.

## Index Requirements

Add an index for entry-oriented binding reads:

```sql
CREATE INDEX idx_scope_bindings_entry_variant
ON scope_bindings(entry_id, variant_id);
```

This supports:

- chunk-level binding hydration by entry
- authority lookup for variants under touched entries
- future lifecycle/orphan refresh improvements

After implementation, check query plans for target branch binding resolution. If
the primary key `(scope_type, scope_value, entry_id)` does not cover the desired
read shape well enough, consider:

```sql
CREATE INDEX idx_scope_bindings_entry_scope
ON scope_bindings(entry_id, scope_type, scope_value);
```

Only add the second index if measurement shows it is needed.

## Error Handling

- The mutation request remains one database transaction.
- Unhandled errors roll back the whole mutation.
- Missing rows, source mismatches, no-ops, and filtered rows are row-level
  outcomes and do not fail the request.
- Schema-unrecognized workbook columns are ignored.
- Mapped blank schema cells clear existing values.
- Content mutation must never create entries, create variants, or alter scope
  bindings.

## Performance Targets

Target workload:

- 200000 workbook rows
- about 10000 rows with content changes
- 9 translation columns, about 90000 translation cell writes

Acceptance:

- large smoke content mutation must not exceed the default 300 second guard
- content mutation apply <= 60 seconds is the first pass target
- content mutation apply <= 30 seconds is the stretch target

Workbook parsing and import-row persistence are measured separately and are not
the main target of this design.

## Verification

Fast TDD acceptance:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_tdd_branch_cycle.py
```

Large local smoke:

```powershell
.\.venv\Scripts\python.exe scripts\run_branch_cycle_smoke.py --reset
```

Branch workflow regression:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_branch_service.py tests/test_io_flows.py
```

Docs validation when docs or documented commands change:

```powershell
.\.venv\Scripts\python.exe scripts\validate_docs.py
```

## Follow-Up

After content mutation is stable, extract the bulk resolve layer for range and
import-batch mutation. The likely next targets are bulk bind/rebind/create
write-sets, set-based orphan refresh, and shared streaming report handling.
