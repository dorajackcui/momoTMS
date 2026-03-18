# Performance

This document captures a historical performance snapshot that is no longer part of the active hot path for agents.

## Expected Scale

The runtime is designed around batch workflows such as:

- `300+` workbooks in one bundle
- `100,000+` imported rows
- `6,000+` new entries or changes in one dev cycle

This is a batch-processing system, not an interactive row-by-row editor.

## Historical Posture

SQLite was the active storage engine in this phase and remained acceptable for the current product shape.

At the time, likely bottlenecks were:

- workbook I/O through `openpyxl`
- Python row loops
- repeated DB round-trips
- large in-memory compare and read-model operations

## Implemented Safeguards At The Time

- batched persistence of import rows
- preloading and bulk creation during import-batch mutations
- entry-local caching during import-batch mutations
- SQL counting for scope-size queries
- paginated compare and queue APIs
- repository-first scope projection for compare and translation queue
- repository-level active-binding search for master query
- stage timing in workflow and job summaries for import, branch mutation, scope sync, fill, and QA

## Local Baseline

Measured on March 7, 2026 in a local isolated runtime using the demo bundle duplicated `40x`.

Bundle shape:

- import bundle: `40` `.xlsx` files, `240` scanned rows
- fill and QA bundle: `40` `.xlsx` files, `200` scanned rows

Observed timings:

- import directory: `106 ms`
  - `parse`: `99 ms`
  - `persist_import`: `1 ms`
- import-batch mutation to `dev/9.9.9`: `345 ms`
  - `apply_scope_mutation`: `344 ms`
- fill export: `250 ms`
  - `fill_export`: `233 ms`
  - `artifact_write`: `15 ms`
- QA scan: `93 ms`
  - `qa_scan`: `93 ms`

These numbers were local baselines, not SLOs.
