# Performance

This document captures the current scale assumptions and optimization posture.

## Expected Scale

The runtime is designed around batch workflows such as:

- `300+` workbooks in one bundle
- `100,000+` imported rows
- `6,000+` new entries or changes in one dev cycle

This is a batch-processing system, not an interactive row-by-row editor.

## Current Posture

SQLite is still the active storage engine and is acceptable for the current phase.

Current bottlenecks are more likely to come from:

- workbook I/O through `openpyxl`
- Python row loops
- repeated DB round-trips
- large in-memory compare/read-model operations

## Implemented Safeguards

The current code already includes:

- batched persistence of import rows
- preloading and bulk creation during dev import
- entry-local caching during dev import
- SQL counting for scope-size queries
- paginated compare and queue APIs
- repository-first scope projection for compare and translation queue
- repository-level active-binding search for master query
- stage timing in workflow/job summaries for import, dev import, promote, fill, and QA

## Hot Paths

Watch these modules when working on performance:

- `app/services/imports/service.py`
- `app/services/workflows/dev_versions.py`
- `app/services/workflows/fill.py`
- `app/services/workflows/qa.py`
- `app/services/read_models/service.py`

## Near-Term Guidance

- keep long-running workflows job-based
- avoid moving heavy work into synchronous request handlers
- avoid re-hydrating full scopes if page-sized slices are enough
- prefer batching and caching before considering a database migration

## Local Baseline

Measured on March 7, 2026 in a local isolated runtime using the demo bundle duplicated `40x`.

Bundle shape:

- import bundle: `40` `.xlsx` files, `240` scanned rows
- fill and QA bundle: `40` `.xlsx` files, `200` scanned rows

Observed timings:

- import directory: `106 ms`
  - `parse`: `99 ms`
  - `persist_import`: `1 ms`
- dev import to `dev/9.9.9`: `345 ms`
  - `bind_dev_scope`: `344 ms`
- fill export: `250 ms`
  - `fill_export`: `233 ms`
  - `artifact_write`: `15 ms`
- QA scan: `93 ms`
  - `qa_scan`: `93 ms`

These numbers are local baselines, not SLOs. Use them to catch regressions when compare logic, workbook parsing, or workflow orchestration changes.

## Non-Goals

- no move away from SQLite right now
- no Translation Memory performance work in this phase
- no inline editing optimization, because inline editing is not a product goal
