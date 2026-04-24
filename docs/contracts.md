# Contracts

## Purpose

- own the product-facing page routes, API inventory, bootstrap contract, frontend or backend contract, and error semantics

## Read This When

- you are changing routers, request or response shapes, SPA routes, or `/app` data dependencies
- you need the current project-scoped HTTP surface

## Owns

- page and SPA route inventory
- HTTP route inventory
- bootstrap contract for `/app`
- frontend or backend contract expectations
- request-level error semantics

## Does Not Own

- package responsibilities or domain invariants
- local setup or validation commands
- detailed workflow semantics beyond the published contract

## Update When

- page routes, API routes, payload fields, product bootstrap, or error behavior change

## Product Surface

Operator-facing product surface:

- source: `frontend/`
- stack: React 19 + TypeScript + Vite + React Router + TanStack Query + React Data Grid
- providers entry: `frontend/src/App.tsx`
- router entry: `frontend/src/app/router.tsx`
- build output: `app/static/product-app/`
- serving route: `GET /app` through `app/routers/pages.py`

Current SPA routes:

| Route | Page | Purpose |
|-------|------|---------|
| `/app` | HubPage | Project list, create project |
| `/app/workspace` | WorkspacePage | Project-wide variant grid, Excel-like browser |
| `/app/release` | ReleasePage | rel/current browse, edit, trash |
| `/app/dev` | DevPage | Dev branch list, create, detail, replace |
| `/app/runs` | RunsPage | Job history, fill, QA, export |

## Route Policy

- the runtime is project-scoped, with branch-first operator reads plus branch-centric workflow writes
- scope routes accept only `master` and `orphan`; branch-ref scope aliases have been removed
- `/app` should call project-scoped APIs only
- `GET /workbench` and `GET /variant-workbench` stay removed and return `410 Gone`
- `/app` may use inspection APIs for read-only debugging, but it should not depend on removed compatibility routes

## Bootstrap Contract

Route:

- `GET /api/projects/{project_id}/state`

Response includes:

- `project`
- `schema`
- `release_summary`
- `dev_branches`
- `imports`
- `jobs`
- each item in `dev_branches` exposes bootstrap metadata for dev rows: `bootstrap_state`, `bootstrapped_at`, `bootstrap_job_id`, and `bootstrap_import_batch_id`
- the same bootstrap metadata appears in the `/state` payload because the payload is assembled from the branch summary and detail models

Usage rules:

- `/app` should bootstrap and refresh project shell state from project-scoped APIs only
- frontend code should treat this payload as project shell state, not as a page-by-page compatibility blob
- detailed page data should come from dedicated project-scoped queries such as the variants workspace query, scope rows, scope lookup, same-source history candidates, imports, jobs, and entry-variant inspection routes
- project schema is fixed after project creation; bootstrap describes the current schema but does not imply schema-edit support
- schema includes `pivot_language` plus `pivoted_languages`
- when `lang` is in `pivoted_languages`, its pivot parent is the project `pivot_language`; all other languages are treated as `null` pivot

Branch bootstrap:

- `POST /api/projects/{project_id}/branches/bootstrap`
- request body accepts `branch_ref` and `import_batch_id`
- the route returns async `JobDetail`
- report rows use the bootstrap row statuses `BOUND_EXISTING_VARIANT`, `CREATED_AND_BOUND_VARIANT`, `INVALID_ROW`, and `DUPLICATE_KEY_IN_BOOTSTRAP`
- job summaries include `processed_count`, `bound_existing_variant_count`, `created_and_bound_variant_count`, `invalid_row_count`, `duplicate_key_count`, `created_entry_count`, `created_variant_count`, `bootstrap_state`, `bootstrapped_at`, `bootstrap_job_id`, and `bootstrap_import_batch_id`

Preview family:

- preview endpoints use a shared envelope with `preview_kind`, `workflow_kind`, `request_echo`, `summary`, and `rows`
- the preview family distinguishes `input_precheck` from `effect_forecast`
- current branch workflow previews use `preview_kind = effect_forecast`
- current import upload preview remains the `input_precheck` style workflow
- workflow previews are read-only: they must not create jobs, write bindings or variants, or mutate branch bootstrap metadata
- effect-forecast rows keep payloads summary-first and row-minimal, and may add shared semantic fields such as `binding_effect`, `variant_resolution`, and `row_outcome`

## Request And Report Shapes

`POST /api/projects`

- request body accepts `name`, `translation_columns`, `remark_columns`, optional `pivot_language`, and optional `pivoted_languages`
- `pivot_language` must be one of `translation_columns`
- `pivoted_languages` must be a subset of `translation_columns`, cannot include `pivot_language`, and require `pivot_language` to be set
- response remains `ProjectSummary`; schema details still come from bootstrap

Branch bootstrap jobs:

- `POST /api/projects/{project_id}/branches/bootstrap` accepts `branch_ref` plus `import_batch_id`
- the request is asynchronous and returns `JobDetail`
- bootstrap rows are sparse branch-establishment input: `business_key` and `source` are required, while optional translations and remarks are only used when a new variant is created
- reuse-hit rows bind the existing same-source variant and ignore uploaded content, so the report status is `BOUND_EXISTING_VARIANT`
- missing or invalid rows are reported as `INVALID_ROW`
- repeated keys within the same bootstrap batch are reported as `DUPLICATE_KEY_IN_BOOTSTRAP`
- the job summary includes the bootstrap counters plus the branch metadata fields copied from `dev_versions`

Branch bootstrap preview:

- `POST /api/projects/{project_id}/branches/bootstrap/preview` accepts `branch_ref` plus `import_batch_id`
- the route is read-only and returns the shared preview envelope instead of `JobDetail`
- the route requires an existing `dev/<version>` branch row and leaves `bootstrap_state = not_bootstrapped` unchanged
- preview rows use the bootstrap statuses `BOUND_EXISTING_VARIANT`, `CREATED_AND_BOUND_VARIANT`, `INVALID_ROW`, and `DUPLICATE_KEY_IN_BOOTSTRAP`
- bootstrap preview rows add `binding_effect`, `variant_resolution`, and `row_outcome`
- bootstrap preview summaries add `binding_effect_counts`, `variant_resolution_counts`, and `row_outcome_counts`

Fill jobs:

- fill requests still use `source_dir`, `lang`, and optional `output_name`
- fill does not add `branch_ref` for pivot V1
- fill report rows expose only fill-match data such as `match_variant_id` and `match_variant_state`; pivot metadata is no longer included

Variants workspace query:

- `GET /api/projects/{project_id}/variants` accepts `state`, repeated `branch_ref`, `search_business_key`, `search_source`, optional `pivot_status`, optional `pivot_changed_by_branch_ref`, `page`, and optional `page_size`
- `state` supports `active`, `orphan`, and `all`; V1 `all` means `active + orphan` only and still excludes `trashed`
- branch filtering matches variants that currently bind at least one requested branch; orphan rows therefore do not match a branch filter
- `pivot_status` supports `init`, `changed`, and `reviewed`
- `pivot_changed_by_branch_ref` uses the same `rel/current` or `dev/x.y.z` ref format as the rest of the API
- row payloads include `variant_id`, `entry_id`, `business_key`, `file_name`, `source`, hydrated translations or remarks, `bindings`, `state`, `orphaned_at`, `pivot_status`, `pivot_changed_by_branch_ref`, `pivot_changed_at`, `pivot_reviewed_at`, `created_at`, and `updated_at`

Branch-first catalog reads:

- `GET /api/projects/{project_id}/branches/{branch_ref:path}/rows` accepts `search_business_key`, `search_source`, `page`, and optional `page_size`
- `branch_ref` supports `rel/current` and `dev/x.y.z`
- this is the canonical operator-facing rows route for branch-scoped reads
- branch row payloads reuse the variants workspace row shape so callers can inspect content, bindings, lifecycle state, and pivot metadata consistently across branch views

Branch-first lookup:

- `GET /api/projects/{project_id}/branches/{branch_ref:path}/lookup` accepts exactly one of `business_key` or `source`
- this is the canonical operator-facing lookup route for branch-scoped reads
- lookup stays branch-aware: the same key or source may resolve differently in `rel/current` and `dev/x.y.z`

Scope catalog reads:

- `GET /api/projects/{project_id}/scopes/{scope_ref:path}/rows` accepts `search_business_key`, `search_source`, `page`, and optional `page_size`
- `scope_ref` accepts only `master` and `orphan`
- `master` means the project-wide live variant scope: `active + orphan`, excluding `trashed`
- `orphan` means all variants with zero bindings and not trashed
- scope row payloads reuse the variants workspace row shape and return `BranchRowsResponse`

Scope lookup:

- `GET /api/projects/{project_id}/scopes/{scope_ref:path}/lookup` accepts exactly one of `business_key` or `source`
- `scope_ref` accepts only `master` and `orphan`
- lookup returns `BranchLookupResponse`
- lookup stays scope-aware: the same key or source may resolve differently in `master` and `orphan`

Same-source history candidates:

- `GET /api/projects/{project_id}/history/same-source-candidates` accepts exact `business_key` plus exact `source`
- the response returns project history candidates ordered by reuse preference: live before trashed, then newest `updated_at`
- candidate rows include `active`, `orphan`, or `trashed` state plus hydrated translations, remarks, bindings, and pivot metadata

Pivot review jobs:

- `POST /api/projects/{project_id}/variants/pivot/review` accepts `branch_ref` plus `variant_ids[]`
- the action returns synchronous `JobDetail` with report rows in the standard workflow shape
- row statuses are `REVIEWED`, `NOT_CHANGED`, `NOT_VISIBLE_IN_SCOPE`, `FORBIDDEN_BY_AUTHORITY`, or `MISSING`
- successful reviews move the variant from `changed` to `reviewed`, clear `pivot_changed_by_branch_ref`, and record `pivot_reviewed_at`

Branch replace preview:

- `POST /api/projects/{project_id}/branches/replace/preview` accepts `source_branch_ref` and `target_branch_ref`
- preview returns the shared effect-forecast envelope with `preview_kind = effect_forecast` and `workflow_kind = branch_replace`
- the live public pair is `dev/<version> -> rel/current`
- replace is a pure target-binding rewrite: execute clears the target branch bindings, then binds the source branch's active range into that target
- preview describes only target-branch effects; the source branch and unrelated branches stay unchanged
- preview summary includes `final_target_entry_count`, `added_to_target_count`, `kept_in_target_count`, `rebind_target_count`, and `removed_from_target_count`
- preview rows use binding-change statuses: `ADD_TO_TARGET`, `KEEP_IN_TARGET`, `REBIND_TARGET`, and `REMOVE_FROM_TARGET`
- replace preview rows may also add `binding_effect`, `variant_resolution`, and `row_outcome` when those generic fields have a clear meaning for the row
- `REBIND_TARGET` means the target branch already has that `business_key`, but it is currently bound to a different variant than the source branch, so execute will switch the target binding without copying content

Branch replace execute:

- `POST /api/projects/{project_id}/branches/replace/execute` accepts the same `source_branch_ref` and `target_branch_ref` request body as preview
- the job summary includes `final_target_entry_count`, `added_to_target_count`, `kept_in_target_count`, `rebind_target_count`, and `removed_from_target_count`
- execute only changes target-branch bindings; it does not modify source-branch bindings or unrelated branches

Import upload and job detail:

- `POST /api/projects/{project_id}/imports/upload-folder/preview` accepts multipart workbook uploads and returns `upload_session_id`, project `schema`, and sheet preview data
- import preview still returns `available_headers`, `suggested_mapping`, and `missing_targets`, but `missing_targets` only tracks required business fields such as `business_key` and `source`
- `POST /api/projects/{project_id}/imports/upload-folder` now accepts JSON with `upload_session_id` and optional `column_mapping_json`; it does not re-upload the workbook payload
- long-running import actions return `JobDetail` immediately with a running job and require polling `GET /api/projects/{project_id}/jobs/{job_id}`
- `GET /api/projects/{project_id}/jobs/{job_id}` returns a report preview only; callers should use the workflow-specific full report route when they need all rows
- import jobs publish the full persisted row report through `GET /api/projects/{project_id}/imports/{import_batch_id}/report`

Workbook workflow input:

- `POST /api/projects/{project_id}/workbooks/intake/preview` accepts multipart workbook uploads plus workflow context and returns lightweight precheck data
- `POST /api/projects/{project_id}/workbooks/intake/execute` accepts `upload_session_id`, `workflow_kind`, optional `branch_ref`, and optional `mutation_type`, then starts one async job that parses the workbook and applies the workflow
- product write flows no longer expose Direct or Import batch as input methods
- branch content mutation and branch range mutation both require configured key and source workbook headers
- branch trash and project trash require only the configured key workbook header

Branch mutation reporting:

- `POST /api/projects/{project_id}/branches/mutations/preview` is the read-only mutation preview route
- the current runtime mutation preview returns the shared effect-forecast envelope for `direct` input
- mutation preview rows may report `UPDATED_BOUND_VARIANT`, `BOUND_EXISTING_VARIANT`, `CREATED_AND_BOUND_VARIANT`, `MISSING_IN_SCOPE`, or `INVALID_ROW`
- mutation preview summaries are summary-first and add `binding_effect_counts`, `variant_resolution_counts`, and `row_outcome_counts`
- `POST /api/projects/{project_id}/branches/mutations` remains the same route for both `direct` and `import_batch` mutation inputs
- `direct` and `import_batch` remain accepted runtime input kinds, but they are legacy input shapes or transports rather than the top-level Phase 4 semantic model
- `POST /api/projects/{project_id}/branches/mutations` may return mutation report rows with `content_filtered_by_authority = true` when a requested `translations` or `remarks` edit is dropped after authority evaluation on the resolved target variant
- branch mutation summaries may include `content_filtered_by_authority_count`
- row `status` still describes the applied bind or update effect; the authority-filtered flag explains whether requested content edits were omitted
- mutation report rows now also add `mutation_class`, `binding_effect`, `variant_resolution`, `content_effect`, and `row_outcome`
- `mutation_class` reports the canonical Phase 4 semantic class as `range` or `content`
- `binding_effect` reports `none`, `bind`, or `rebind`
- `variant_resolution` reports `stay_current`, `reuse_existing`, or `create_new`
- `content_effect` reports `none`, `create`, `update`, or `filtered`
- `row_outcome` reports `applied`, `noop`, or `missing`
- branch mutation summaries now also add grouped semantic counters under `mutation_class_counts`, `binding_effect_counts`, `variant_resolution_counts`, `content_effect_counts`, and `row_outcome_counts`
- `mutation_class_counts` groups rows as `range_count` and `content_count`
- `binding_effect_counts` groups rows as `none_count`, `bind_count`, and `rebind_count`
- `variant_resolution_counts` groups rows as `stay_current_count`, `reuse_existing_count`, and `create_new_count`
- `content_effect_counts` groups rows as `none_count`, `create_count`, `update_count`, and `filtered_count`
- `row_outcome_counts` groups rows as `applied_count`, `noop_count`, and `missing_count`

## Frontend And Backend Contract

The product app depends on:

- project list plus project-scoped bootstrap data from `GET /api/projects` and `GET /api/projects/{project_id}/state`
- the project-scoped variants workspace query for `Workspace` and orphan browsing
- canonical branch rows and branch lookup for branch-oriented reads; scope routes for master and orphan reads
- import preview data with `upload_session_id`, `available_headers`, `suggested_mapping`, and `missing_targets`
- import-batch list and report APIs
- job list, detail, report, and artifact APIs
- canonical entry-variant and orphan inspection APIs
- project-scoped branch mutation and sync routes plus fill and QA routes

The product app uses URL state as the primary workspace contract for `project`, `lang`, `branch`, `tab`, `job`, and `business_key`. It may store the selected project id locally only as a fallback when the URL does not provide one, clears that fallback when no projects exist, and refreshes page state from project-scoped APIs only.

`/app/workspace` may intentionally omit `branch` to represent the project-wide variants workspace. Selecting `All branches` on Workspace clears the canonical `branch` URL param instead of forcing a fallback branch value.

Invalid or stale `project`, `lang`, or `branch` URL params are normalized to the nearest valid project-scoped workspace context before branch-scoped page queries run. The Apply page keeps its write target branch as local form state instead of treating it as the canonical URL branch.

Import UI contract:

- import preview uploads the workbook set once, stores the returned `upload_session_id`, and reuses that session id for confirm
- import mapping requires `business_key` and `source`
- translation and remark mappings are optional; unmapped fields stay unchanged during import apply

## HTTP Routes

Pages:

- `GET /app`
- `GET /app/{path:path}`
- `GET /workbench`
- `GET /variant-workbench`

Projects and bootstrap:

- `GET /api/projects`
- `POST /api/projects`
- `GET /api/projects/{project_id}/state`
- `POST /api/demo/reset`

Imports and jobs:

- `POST /api/projects/{project_id}/imports/directory`
- `POST /api/projects/{project_id}/imports/upload-folder/preview`
- `POST /api/projects/{project_id}/imports/upload-folder`
- `GET /api/projects/{project_id}/imports`
- `GET /api/projects/{project_id}/imports/{import_batch_id}/report`
- `GET /api/projects/{project_id}/jobs`
- `GET /api/projects/{project_id}/jobs/{job_id}`
- `GET /api/projects/{project_id}/jobs/{job_id}/report`
- `GET /api/projects/{project_id}/jobs/{job_id}/artifact/{name}`

Branch read models:

- `GET /api/projects/{project_id}/branches`
- `GET /api/projects/{project_id}/branches/{branch_ref:path}/rows`
- `GET /api/projects/{project_id}/branches/{branch_ref:path}/lookup`
- `GET /api/projects/{project_id}/scopes/{scope_ref:path}/rows`
- `GET /api/projects/{project_id}/scopes/{scope_ref:path}/lookup`
- `GET /api/projects/{project_id}/history/same-source-candidates`

Inspection reads:

- `GET /api/projects/{project_id}/variants`
- `GET /api/projects/{project_id}/entries/{business_key}/variants`
- `GET /api/projects/{project_id}/orphan-variants`

Workflow actions:

- `POST /api/projects/{project_id}/branches/bootstrap/preview`
- `POST /api/projects/{project_id}/branches/mutations`
- `POST /api/projects/{project_id}/branches/mutations/preview`
- `POST /api/projects/{project_id}/branches/bootstrap`
- `GET /api/projects/{project_id}/branches/dev`
- `GET /api/projects/{project_id}/branches/dev/{version}`
- `POST /api/projects/{project_id}/branches/replace/preview`
- `POST /api/projects/{project_id}/branches/replace/execute`
- `POST /api/projects/{project_id}/variants/trash`
- `POST /api/projects/{project_id}/variants/trash/delete`
- `POST /api/projects/{project_id}/variants/pivot/review`
- `POST /api/projects/{project_id}/variants/pivot/review/preview`
- `POST /api/projects/{project_id}/fill`
- `POST /api/projects/{project_id}/fill/upload-folder`
- `POST /api/projects/{project_id}/qa`
- `POST /api/projects/{project_id}/qa/upload-folder`
- `POST /api/projects/{project_id}/workbooks/intake/preview`
- `POST /api/projects/{project_id}/workbooks/intake/execute`

Long-running action contract:

- `POST /api/projects/{project_id}/imports/directory` starts an async job and returns `JobDetail`
- `POST /api/projects/{project_id}/imports/upload-folder` starts an async job and returns `JobDetail`
- `POST /api/projects/{project_id}/branches/bootstrap` starts an async job and returns `JobDetail`
- `POST /api/projects/{project_id}/branches/mutations` returns an async `JobDetail` when `input.kind == "import_batch"`; direct mutations remain request-scoped
- `POST /api/projects/{project_id}/workbooks/intake/execute` starts an async job and returns `JobDetail`

## Error Semantics

- invalid branch refs and invalid business parameters return `400`
- missing resources, missing artifacts, and cross-project access to imports, jobs, reports, and artifacts return `404`
- request-body validation errors return `422`

## Not In Scope

These capabilities are not part of the live public contract:

- schema editing after project creation
- Translation Memory endpoints
- permission or audit endpoints

## Source Of Truth

- router files under `app/routers/` define the live paths
- `app/schemas.py` defines request and response models
- `/docs` is the easiest way to inspect the current contract
