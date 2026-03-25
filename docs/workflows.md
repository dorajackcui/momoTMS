# Workflows

## Purpose

- own the stable rules for import, mutation, sync, trash, restore, fill, QA, and Excel or normalization behavior

## Read This When

- you are changing workbook parsing, branch writes, sync behavior, deletion or restore flows, fill, QA, or IO helpers
- you need the workflow semantics behind the public routes

## Owns

- normalization helpers and field policy
- schema-driven workbook rules
- import rules
- branch mutation and sync semantics
- trash and restore semantics
- fill and QA behavior

## Does Not Own

- package map or global runtime boundaries
- API inventory or payload schemas
- install, run, reset, or test commands

## Update When

- Excel processing, normalization, workflow semantics, or job-facing workflow behavior change

## Primary Code Locations

- normalization helpers: `app/services/shared/io.py`
- import parsing and persistence: `app/services/imports/service.py`
- branch mutation and sync policy: `app/services/branch/`
- variant trash or restore workflows: `app/services/workflows/trash_restore.py`
- fill and QA orchestration: `app/services/workflows/`

## Normalization Rules

Implemented in `app/services/shared/io.py`.

`safe_to_str(value, strip=True)`

- `None` becomes `""`
- non-string values are converted with `str(value)`
- `strip=True` trims leading and trailing whitespace
- `strip=False` preserves surrounding whitespace

`is_blank_value(value)`

- blank is true only when `value is None` or a string whose trimmed value is empty
- blank is false for values like `0`, `0.0`, and `float("nan")`

Field normalization policy:

- non-content fields use trimmed normalization
- translation content preserves surrounding whitespace

Non-content fields:

- `business_key`
- `source`
- `file_name`
- remark columns

Content fields:

- all project translation columns

## Project Template Rules

- project schema defines the fixed columns `business_key` and `source`
- translation columns and remark columns are project-defined
- project creation may also define `translation_pivots`; when omitted, every translation column defaults to `null` pivot
- `translation_pivots` is validated against the project translation columns, stored as a full map, and stays fixed after project creation
- header matching is schema-driven
- import mapping always requires `business_key` and `source`
- translation and remark mappings may be omitted for import; omitted fields are treated as "keep existing value"
- `file_name` is derived from workbook relative path, not from a sheet column
- upload preview is sheet-based and returns suggested mappings per sheet

Header preview and resolution are implemented by `ProjectService.preview_headers()` and `ProjectService.resolve_headers()`.

## Import Rules

- read only `.xlsx` files
- skip temporary files whose names start with `~$`
- each sheet uses row `1` as the header row
- upload preview stages incoming files into an upload session and returns `upload_session_id`
- confirm import reuses `upload_session_id` plus optional `column_mapping_json`; it does not upload the same workbook bundle twice
- rows missing normalized `business_key` are invalid
- rows missing normalized `source` are invalid
- import parsing uses `openpyxl.load_workbook(..., read_only=True, data_only=True)` and iterates workbook rows sequentially
- import persistence writes `import_rows` in chunks instead of building one giant in-memory batch
- persisted import row payloads are sparse patches: only mapped translation and remark fields are stored
- an omitted translation or remark field means "leave the current value unchanged"; an explicitly provided blank cell still clears that field to `""`
- import results are persisted row by row in `imports` and `import_rows`
- upload preview returns `available_headers`, `suggested_mapping`, and `missing_targets`
- import jobs are async: preview uploads once, confirm starts a job, and clients poll job status separately

## Scope Mutation Rules

Branch writes are capability-based rather than having separate scenario-specific route families.

Input modes:

- `direct`: one or more business-key patches applied to a target scope
- `import_batch`: one persisted import batch applied to a target scope

Current policy:

- `direct + rel/current` replaces the old rel hotfix behavior
- `direct + dev/<version>` supports single-row or batch dev patching
- `import_batch + dev/<version>` replaces the old dev import behavior
- `import_batch + rel/current` is invalid

Mutation rules:

- each mutation request executes in one DB transaction
- unhandled errors roll back the whole request rather than committing per-row partial progress
- if `source` is omitted, mutation requires an existing binding in the target scope and updates the currently bound variant in place
- if `source` is provided and matches the currently bound variant, mutation updates that bound variant in place
- if `source` is provided and differs, mutation resolves or creates the target same-source canonical variant and rebinds the scope when needed
- `dev` policy keeps rel-owned canonical content authoritative when same-source hits a rel-bound variant
- `dev` policy may create missing entries when `source` is present
- `rel` policy always starts from the currently bound rel variant and never creates a missing business key from scratch
- `import_batch` applies persisted sparse patches using the same merge rules as direct mutation: only provided translations and remarks overwrite existing content
- `import_batch + dev/<version>` runs as a job and streams report rows into job storage instead of returning the full apply result inline
- `import_batch + rel/current` remains invalid
- import-batch apply reads persisted `import_rows` in chunks, batches entry or variant or binding hydration, and refreshes orphan state once per touched entry set instead of once per row

## Scope Sync Rules

- previews and executes binding changes from one branch into another
- the live policy only supports `dev/<version> -> rel/current`
- replace rebinds active variants; it does not copy content or create variants
- execute runs in one DB transaction
- the `dev/<version> -> rel/current` policy still clears same-version-series dev bindings and marks those versions as promoted

## Trash And Restore Rules

- delete is project-scoped and takes `branch_ref` plus `business_keys[]`
- delete executes in one DB transaction per request
- delete removes the active binding in the selected branch
- if the affected variant no longer has any active bindings, delete moves that variant into `trashed`
- if other branches still bind the same variant, delete only removes the selected branch binding
- restore is project-scoped and takes `variant_ids[]`
- restore executes in one DB transaction per request
- restore clears trashed state for the selected variants only; it does not rebind scopes automatically
- restore may fail with `SOURCE_CONFLICT` when the same entry already has another live same-source variant
- business-result rows such as `MISSING`, `NOT_BOUND_IN_SCOPE`, `NOT_TRASHED`, and `SOURCE_CONFLICT` stay request-local report statuses; only unhandled errors roll back the whole request

## Fill Rules

- fill matches workbook rows by normalized `business_key + source`
- if either value becomes empty, the row is not a valid fill candidate
- fill candidate lookup is project-scoped and reads all recorded variants for that project, including `active`, `orphan`, and `trashed`
- when the same `business_key + source` has both non-trashed and trashed candidates, fill always prefers the non-trashed candidate
- when only trashed same-source history remains, fill uses the candidate with the newest `updated_at`
- `SRC_MISMATCH` means the `business_key` exists in the project but no variant in project history matches the workbook `source`
- `MISSING_KEY_IN_PROJECT` means the `business_key` does not exist anywhere in the project history
- fill report rows record `match_variant_id` and `match_variant_state` (`active`, `orphan`, or `trashed`) instead of a branch label
- fill still requires the workbook to include the selected target language column; import-only sparse mapping rules do not apply to fill
- when the selected fill language has a configured pivot parent, fill also reports `pivot_lang` and `pivot_sync_status`
- `pivot_sync_status` is derived from variant-level checkpoint state, not from workbook freshness or branch selection
- unmatched rows keep `pivot_sync_status = null`; matched rows use one of `PIVOT_IN_SYNC`, `PIVOT_OUT_OF_SYNC`, `MISSING_CHILD`, or `MISSING_PARENT`
- fill writes translations back to workbook artifacts through a job

Implication:

- `business_key + source` is a fill-match key
- it is not the identity of an entry
- it is not the identity of a variant

## QA Rules

- QA is schema-driven and read-only
- it reads source and selected target language columns from workbook input
- QA still requires the workbook to include the selected target language column; import-only sparse mapping rules do not apply to QA
- it validates row-level source and target content
- it does not mutate runtime scope bindings
