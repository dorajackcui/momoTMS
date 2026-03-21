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
- stack: React 19 + TypeScript + Vite
- entry: `frontend/src/App.tsx`
- build output: `app/static/product-app/`
- serving route: `GET /app` through `app/routers/pages.py`

Current SPA routes:

- `/app`
- `/app/overview`
- `/app/compare`
- `/app/queue`
- `/app/master`
- `/app/imports`
- `/app/inspection`
- `/app/projects/new`

## Route Policy

- the runtime is project-scoped and branch-centric
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

- `/app` should bootstrap and refresh from project-scoped APIs only
- frontend code should treat this payload as product state, not as a compatibility-shaped state blob
- project schema is fixed after project creation; bootstrap describes the current schema but does not imply schema-edit support

## Frontend And Backend Contract

The product app depends on:

- project-scoped bootstrap data from `GET /api/projects/{project_id}/state`
- paginated compare and queue APIs
- import preview data with `available_headers`, `suggested_mapping`, and `missing_targets`
- job detail, report, and artifact APIs
- canonical entry-variant and orphan inspection APIs
- project-scoped branch mutation and sync routes plus fill and QA routes

The product app stores the selected project id locally, clears it when no projects exist, and refreshes branch state from project-scoped APIs only.

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
- `POST /api/projects/{project_id}/fill`
- `POST /api/projects/{project_id}/fill/upload-folder`
- `POST /api/projects/{project_id}/qa`
- `POST /api/projects/{project_id}/qa/upload-folder`

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
