# Workflows

## Purpose

- own the stable rules for import, mutation, sync, branch delete, project trash, fill, QA, and Excel or normalization behavior

## Read This When

- you are changing workbook parsing, branch writes, sync behavior, branch delete, project trash, fill, QA, or IO helpers
- you need the workflow semantics behind the public routes

## Owns

- normalization helpers and field policy
- schema-driven workbook rules
- import rules
- branch mutation and sync semantics
- branch delete (unbind) and project trash semantics
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
- variant trash workflows: `app/services/workflows/trash.py`
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
- project creation may also define a single `pivot_language` plus `pivoted_languages`; when omitted, every translation column defaults to `null` pivot
- `pivot_language` must be one of the project translation columns, `pivoted_languages` must be a subset of the translation columns, and the pivot configuration stays fixed after project creation
- project creation accepts optional `business_key_header` and `source_header` to configure the workbook column names that map to internal `business_key` and `source` fields
- when not provided, `business_key_header` defaults to `"Key"` and `source_header` defaults to `"MsgStr"`
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

## Preview Rules

- preview is a first-class operator contract and the preview family distinguishes `input_precheck` from `effect_forecast`
- `input_precheck` is for intake validation and mapping readiness before a workflow is accepted
- `effect_forecast` is for summary-first, read-only preview of workflow-visible outcomes
- current branch workflow previews use `effect_forecast`; import upload preview remains an `input_precheck`
- read-only preview means no job creation, no binding or variant writes, and no bootstrap-state mutation
- preview rows stay minimal so large batches remain tractable; summaries carry the main operator signal first
- shared effect-forecast vocabulary includes `binding_effect`, `variant_resolution`, and `row_outcome`
- `variant_resolution` answers whether a row would `stay_current`, `reuse_existing`, or `create_new`

## Workbook Write Workflow Rules

- create branch, branch mutation, branch trash, and project trash use workflow-specific workbook uploads
- upload precheck is lightweight and validates files, sheets, headers, and sampled row issues
- execute starts one async job that persists workbook rows and applies the target workflow
- content mutation requires configured key + source and only updates the currently bound branch variant
- content mutation never binds, rebinds, creates variants, or changes branch range
- range mutation requires configured key + source and may bind, rebind, or create variants according to branch policy
- trash workflows require configured key only

## Branch Bootstrap Rules

- branch bootstrap is a dedicated async workflow for establishing the initial working range of `dev/<version>`
- bootstrap preview is the read-only preview family entrypoint for this workflow
- bootstrap preview reads persisted import rows in chunks but never creates entries, variants, bindings, or bootstrap metadata
- bootstrap preview requires an existing non-bootstrapped `dev/<version>` branch row
- bootstrap accepts a persisted import batch whose rows must provide normalized `business_key` and `source`; optional `file_name`, translation columns, and remark columns may be present in the uploaded file but are parsed and not used by bootstrap — content columns are always ignored regardless of whether the row creates a new variant or binds an existing one
- bootstrap reads persisted `import_rows` in chunks, primes entry and variant caches per chunk, and refreshes orphan state after the touched entries in that chunk instead of doing a single giant in-memory apply
- rows that match an existing same-source canonical variant under the entry are reported as `BOUND_EXISTING_VARIANT`; uploaded translation or remark content is ignored for those reuse hits because bootstrap only needs to bind the already-existing variant
- rows that have no same-source canonical variant create a new bare variant (source only, no translations or remarks), bind it to the dev branch, and report `CREATED_AND_BOUND_VARIANT`; content for these new variants must be populated via the mutation workflow after bootstrap completes
- rows missing normalized `business_key` or `source`, or rows that come from a non-`ok` import row status, are reported as `INVALID_ROW`
- repeated `business_key` values inside the same bootstrap batch are reported as `DUPLICATE_KEY_IN_BOOTSTRAP`
- bootstrap effect-forecast rows classify reuse hits as `binding_effect = bind`, `variant_resolution = reuse_existing`, `row_outcome = applied`
- bootstrap effect-forecast rows classify new-source or new-entry work as `binding_effect = bind`, `variant_resolution = create_new`, `row_outcome = applied`
- bootstrap preview treats invalid and duplicate rows as `row_outcome = invalid`
- bootstrap is rejected once the dev branch has already been marked `bootstrapped`
- bootstrap summaries report `processed_count`, `bound_existing_variant_count`, `created_and_bound_variant_count`, `invalid_row_count`, `duplicate_key_count`, `created_entry_count`, `created_variant_count`, and the branch bootstrap metadata copied from `dev_versions`

## Scope Mutation Rules

Branch writes are capability-based rather than having separate scenario-specific route families.

Phase 4 defines one canonical semantic model for branch mutation work. The top-level mutation classes are:

- `range mutation`
- `content mutation`

Current runtime inputs such as `direct` and `import_batch` remain accepted legacy input shapes and transports into the Phase 4 mutation contract. They are not the top-level semantic model.

- `workbook_batch`: one workbook-parsed batch applied to a target scope; the product UI uses this path exclusively

Accepted runtime inputs:

- `direct`: one or more business-key patches applied to a target scope
- `import_batch`: one persisted import batch applied to a target scope
- `workbook_batch`: workbook-parsed batch with workflow context; routed to content or range mutation based on `mutation_type`

Current policy:

- `direct + rel/current` replaces the old rel hotfix behavior
- `direct + dev/<version>` supports single-row or batch dev patching
- `import_batch + dev/<version>` replaces the old dev import behavior
- `import_batch + rel/current` is invalid

Mutation rules:

- each mutation request executes in one DB transaction
- unhandled errors roll back the whole request rather than committing per-row partial progress
- `range mutation` changes the branch's effective coverage range by adding a missing branch key or selecting a different same-entry variant identity for an existing key
- `content mutation` changes only content on the branch-visible current target and keeps branch range unchanged
- if `source` is omitted, mutation is treated as `content mutation`, requires an existing binding in the target scope, and updates the currently bound variant in place
- if `source` is provided and matches the currently bound variant, mutation is still `content mutation` and updates that bound variant in place
- if `source` is provided and differs, mutation is `range mutation` and resolves or creates the target same-source canonical variant before rebinding when needed
- `dev` policy keeps rel-owned canonical content authoritative when same-source hits a rel-bound variant
- lower-authority content-change attempts no longer hard-fail by default during branch mutation
- after target variant resolution, unauthorized `translations + remarks` edits are filtered while otherwise legal bind or rebind work still proceeds
- mutation report row `status` still describes the applied bind or update effect; `content_filtered_by_authority = true` explains when a requested content edit was dropped after authority evaluation
- mutation summaries include `content_filtered_by_authority_count`
- mutation report rows may include `content_filtered_by_authority = true` when the requested content edit was dropped
- pure rebind can still succeed when no content change is needed, because binding an already-matching same-source variant is distinct from mutating that variant's content
- `dev` policy may create missing entries when `source` is present
- `rel` policy always starts from the currently bound rel variant and never creates a missing business key from scratch
- `import_batch` applies persisted sparse patches using the same merge rules as direct mutation: only provided translations and remarks overwrite existing content
- `import_batch + dev/<version>` runs as a job and streams report rows into job storage instead of returning the full apply result inline
- `import_batch + rel/current` remains invalid
- import-batch apply reads persisted `import_rows` in chunks, batches entry or variant or binding hydration, and refreshes orphan state once per touched entry set instead of once per row
- content mutation must never implicitly change branch range
- a missing-target content mutation reports `MISSING_IN_SCOPE` plus `row_outcome = missing` instead of silently degrading into range mutation
- mutation preview is the read-only preview family entrypoint for branch mutation work
- the current runtime mutation preview is an `effect_forecast` for `direct` input and keeps execute semantics unchanged
- mutation report rows add semantic fields: `mutation_class`, `binding_effect`, `content_effect`, and `row_outcome`
- `mutation_class` normalizes the top-level semantic intent as `range` or `content`
- `binding_effect` reports `none`, `bind`, or `rebind`
- `variant_resolution` reports `stay_current`, `reuse_existing`, or `create_new`
- `content_effect` reports `none`, `create`, `update`, or `filtered`
- `row_outcome` reports `applied`, `noop`, or `missing`
- mutation summaries add grouped semantic counters under `mutation_class_counts`, `binding_effect_counts`, `variant_resolution_counts`, `content_effect_counts`, and `row_outcome_counts`
- `mutation_class_counts` groups rows as `range_count` and `content_count`
- `binding_effect_counts` groups rows as `none_count`, `bind_count`, and `rebind_count`
- `variant_resolution_counts` groups rows as `stay_current_count`, `reuse_existing_count`, and `create_new_count`
- `content_effect_counts` groups rows as `none_count`, `create_count`, `update_count`, and `filtered_count`
- `row_outcome_counts` groups rows as `applied_count`, `noop_count`, and `missing_count`
- legacy status wording remains authoritative for compatibility reporting, and `content_filtered_by_authority` remains the compatibility flag for filtered content edits
- new variants always start with `pivot_status = init`
- when a mutation changes the normalized value of the project `pivot_language`, the touched variant becomes `pivot_status = changed`, records the actor branch as owner, and updates `pivot_changed_at`
- `NOOP` mutations and non-pivot-language changes do not alter pivot status
- normal mutation paths never auto-clear `changed` back to `reviewed`

## Pivot Review Rules

- manual pivot review is project-scoped and takes `branch_ref` plus `variant_ids[]`
- review only succeeds when the variant exists in the project, is currently `changed`, is visible in the actor branch scope, and the actor branch authority is greater than or equal to the changed-owner branch
- success performs `changed -> reviewed`, clears the changed-owner branch metadata, writes `pivot_reviewed_at`, and refreshes `pivot_status_updated_at`
- review rows report one of `REVIEWED`, `NOT_CHANGED`, `NOT_VISIBLE_IN_SCOPE`, `FORBIDDEN_BY_AUTHORITY`, or `MISSING`
- review uses the standard job-backed workflow response shape even though execution is request-scoped

## Scope Sync Rules

- previews and executes binding changes from one branch into another
- the live policy only supports `dev/<version> -> rel/current`
- replace is a pure target-binding rewrite: clear the target branch's active bindings, then bind every active source-branch variant into that target branch
- replace only changes target-branch bindings; the source branch and unrelated branches stay unchanged
- replace rebinds active variants; it does not copy content or create variants
- replace preview is an `effect_forecast` and reports binding-change semantics instead of content-diff semantics
- replace preview is read-only preview and keeps rows minimal while surfacing the shared semantic block when it has a clear meaning
- preview rows may report `ADD_TO_TARGET`, `KEEP_IN_TARGET`, `REBIND_TARGET`, or `REMOVE_FROM_TARGET`
- `REBIND_TARGET` means the target branch already has the same `business_key` but is bound to a different variant than the source branch, so execute will switch the binding to the source branch's variant
- execute runs in one DB transaction
- replace summary fields are `final_target_entry_count`, `added_to_target_count`, `kept_in_target_count`, `rebind_target_count`, and `removed_from_target_count`

## Branch Delete (Unbind) Rules

- branch delete is branch-scoped and takes `branch_ref` plus `business_keys[]`
- branch delete executes in one DB transaction per request
- branch delete removes the active binding in the selected branch
- if the affected variant no longer has any active bindings, it becomes orphan (not trashed)
- if other branches still bind the same variant, branch delete only removes the selected branch binding
- no authority check; an operator can always unbind entries from their own branch
- report statuses: `ORPHANED_VARIANT`, `REMOVED_BINDING`, `NOT_BOUND_IN_SCOPE`, `MISSING`
- summary fields: `orphaned_variant_count`, `removed_binding_count`, `not_bound_count`, `missing_count`

## Project Trash Rules

- project trash is project-scoped and takes `business_keys[]`
- project trash executes in one DB transaction per request
- project trash sets `trashed_at` on orphan variants only (zero bindings)
- active variants (with bindings) are reported as `NOT_ORPHAN` and skipped
- trashed is terminal: no restore, no cleanup, no way back
- no authority check; project trash is a project-level admin action
- report statuses: `TRASHED`, `NOT_ORPHAN`, `NO_ORPHAN_FOUND`, `MISSING`
- summary fields: `trashed_count`, `not_orphan_count`, `no_orphan_found_count`, `missing_count`

## Fill Rules

- fill matches workbook rows by normalized `business_key + source`
- if either value becomes empty, the row is not a valid fill candidate
- fill candidate lookup is project-scoped and reads all live (non-trashed) variants for that project, including `active` and `orphan` states
- trashed variants are completely excluded from fill candidate lookup
- `SRC_MISMATCH` means the `business_key` exists in the project but no variant in project history matches the workbook `source`
- `MISSING_KEY_IN_PROJECT` means the `business_key` does not exist anywhere in the project history
- fill report rows record `match_variant_id` and `match_variant_state` (`active` or `orphan`) instead of a branch label
- fill still requires the workbook to include the selected target language column; import-only sparse mapping rules do not apply to fill
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
