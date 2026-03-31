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

- `/app`
- `/app/overview`
- `/app/intake`
- `/app/branches`
- `/app/runs`
- `/app/variants`
- `/app/project`

## Route Policy

- the runtime is project-scoped, with branch-centric workflow reads plus a project-wide variants workspace query
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
- `candidate_dev_branch`
- `dev_branches`
- `imports`
- `jobs`

Usage rules:

- `/app` should bootstrap and refresh project shell state from project-scoped APIs only
- frontend code should treat this payload as project shell state, not as a page-by-page compatibility blob
- detailed page data should come from dedicated project-scoped queries such as the variants workspace query, branch detail, compare, queue, imports, jobs, and entry-variant inspection routes
- project schema is fixed after project creation; bootstrap describes the current schema but does not imply schema-edit support
- schema includes `pivot_language` plus `pivoted_languages`
- when `lang` is in `pivoted_languages`, its pivot parent is the project `pivot_language`; all other languages are treated as `null` pivot

## Request And Report Shapes

`POST /api/projects`

- request body accepts `name`, `translation_columns`, `remark_columns`, optional `pivot_language`, and optional `pivoted_languages`
- `pivot_language` must be one of `translation_columns`
- `pivoted_languages` must be a subset of `translation_columns`, cannot include `pivot_language`, and require `pivot_language` to be set
- response remains `ProjectSummary`; schema details still come from bootstrap

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

Pivot review jobs:

- `POST /api/projects/{project_id}/variants/pivot/review` accepts `branch_ref` plus `variant_ids[]`
- the action returns synchronous `JobDetail` with report rows in the standard workflow shape
- row statuses are `REVIEWED`, `NOT_CHANGED`, `NOT_VISIBLE_IN_SCOPE`, `FORBIDDEN_BY_AUTHORITY`, or `MISSING`
- successful reviews move the variant from `changed` to `reviewed`, clear `pivot_changed_by_branch_ref`, and record `pivot_reviewed_at`

Import upload and job detail:

- `POST /api/projects/{project_id}/imports/upload-folder/preview` accepts multipart workbook uploads and returns `upload_session_id`, project `schema`, and sheet preview data
- import preview still returns `available_headers`, `suggested_mapping`, and `missing_targets`, but `missing_targets` only tracks required business fields such as `business_key` and `source`
- `POST /api/projects/{project_id}/imports/upload-folder` now accepts JSON with `upload_session_id` and optional `column_mapping_json`; it does not re-upload the workbook payload
- long-running import actions return `JobDetail` immediately with a running job and require polling `GET /api/projects/{project_id}/jobs/{job_id}`
- `GET /api/projects/{project_id}/jobs/{job_id}` returns a report preview only; callers should use the workflow-specific full report route when they need all rows
- import jobs publish the full persisted row report through `GET /api/projects/{project_id}/imports/{import_batch_id}/report`

## Frontend And Backend Contract

The product app depends on:

- project list plus project-scoped bootstrap data from `GET /api/projects` and `GET /api/projects/{project_id}/state`
- the project-scoped variants workspace query for `Overview` and orphan browsing
- branch summary plus branch detail, compare, and queue APIs for branch-oriented operations
- paginated compare and queue APIs for branch operations and release-summary sampling
- import preview data with `upload_session_id`, `available_headers`, `suggested_mapping`, and `missing_targets`
- import-batch list and report APIs
- job list, detail, report, and artifact APIs
- canonical entry-variant and orphan inspection APIs
- project-scoped branch mutation and sync routes plus fill and QA routes

The product app uses URL state as the primary workspace contract for `project`, `lang`, `branch`, `tab`, `job`, and `business_key`. It may store the selected project id locally only as a fallback when the URL does not provide one, clears that fallback when no projects exist, and refreshes page state from project-scoped APIs only.

`/app/overview` may intentionally omit `branch` to represent the project-wide variants workspace. Selecting `All branches` on Overview clears the canonical `branch` URL param instead of forcing a fallback branch value.

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
- `GET /api/projects/{project_id}/branches/compare`
- `GET /api/projects/{project_id}/branches/queue`
- `GET /api/projects/{project_id}/branches/master/entries/{business_key}`
- `GET /api/projects/{project_id}/branches/master/search`

Inspection reads:

- `GET /api/projects/{project_id}/variants`
- `GET /api/projects/{project_id}/entries/{business_key}/variants`
- `GET /api/projects/{project_id}/orphan-variants`

Workflow actions:

- `POST /api/projects/{project_id}/branches/mutations`
- `GET /api/projects/{project_id}/branches/dev`
- `GET /api/projects/{project_id}/branches/dev/{version}`
- `POST /api/projects/{project_id}/branches/replace/preview`
- `POST /api/projects/{project_id}/branches/replace/execute`
- `POST /api/projects/{project_id}/variants/trash/delete`
- `POST /api/projects/{project_id}/variants/trash/restore`
- `POST /api/projects/{project_id}/variants/pivot/review`
- `POST /api/projects/{project_id}/fill`
- `POST /api/projects/{project_id}/fill/upload-folder`
- `POST /api/projects/{project_id}/qa`
- `POST /api/projects/{project_id}/qa/upload-folder`

Long-running action contract:

- `POST /api/projects/{project_id}/imports/directory` starts an async job and returns `JobDetail`
- `POST /api/projects/{project_id}/imports/upload-folder` starts an async job and returns `JobDetail`
- `POST /api/projects/{project_id}/branches/mutations` returns an async `JobDetail` when `input.kind == "import_batch"`; direct mutations remain request-scoped

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
