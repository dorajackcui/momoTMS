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

## Non-Goals

- no move away from SQLite right now
- no Translation Memory performance work in this phase
- no inline editing optimization, because inline editing is not a product goal
