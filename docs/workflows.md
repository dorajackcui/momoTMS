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
- variant trash or restore workflows: `app/services/variant/workflows.py`
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
- header matching is schema-driven
- every configured translation column is required
- every configured remark column is required
- `file_name` is derived from workbook relative path, not from a sheet column
- upload preview is sheet-based and returns suggested mappings per sheet

Header preview and resolution are implemented by `ProjectService.preview_headers()` and `ProjectService.resolve_headers()`.

## Import Rules

- read only `.xlsx` files
- skip temporary files whose names start with `~$`
- each sheet uses row `1` as the header row
- rows missing normalized `business_key` are invalid
- rows missing normalized `source` are invalid
- import results are persisted row by row in `imports` and `import_rows`
- upload preview returns `available_headers`, `suggested_mapping`, and `missing_targets`

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

- if `source` is omitted, mutation requires an existing binding in the target scope and updates the currently bound variant in place
- if `source` is provided and matches the currently bound variant, mutation updates that bound variant in place
- if `source` is provided and differs, mutation resolves or creates the target same-source canonical variant and rebinds the scope when needed
- `dev` policy keeps rel-owned canonical content authoritative when same-source hits a rel-bound variant
- `dev` policy may create missing entries when `source` is present
- `rel` policy always starts from the currently bound rel variant and never creates a missing business key from scratch

## Scope Sync Rules

- previews and executes binding changes from one scope into another
- the live policy only supports `dev/<version> -> rel/current`
- sync rebinds active variants; it does not copy content or create variants
- execute runs in one DB transaction
- the `dev/<version> -> rel/current` policy still clears same-version-line dev bindings and marks those versions as promoted

## Trash And Restore Rules

- delete is project-scoped and takes `scope_ref` plus `business_keys[]`
- delete removes the active binding in the selected scope
- if the affected variant no longer has any active bindings, lifecycle refreshes it into `orphan` unless it is already trashed
- restore is project-scoped and takes `variant_ids[]`
- restore clears trashed state for the selected variants only; it does not rebind scopes automatically

## Fill Rules

- fill matches workbook rows by normalized `business_key + source`
- if either value becomes empty, the row is not a valid fill candidate
- runtime content still comes from active scope bindings, not from workbook rows alone
- fill writes translations back to workbook artifacts through a job

Implication:

- `business_key + source` is a fill-match key
- it is not the identity of an entry
- it is not the identity of a variant

## QA Rules

- QA is schema-driven and read-only
- it reads source and selected target language columns from workbook input
- it validates row-level source and target content
- it does not mutate runtime scope bindings
