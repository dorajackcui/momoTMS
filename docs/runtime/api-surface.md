# API Surface

This file summarizes the current HTTP surface. For exact schemas, use FastAPI OpenAPI at `/docs`.

## Route Policy

The runtime exposes two API styles:

- project-scoped routes: preferred for new work
- default-project compatibility routes: frozen for project `1`

When both exist, prefer the project-scoped route.

## Pages

- `GET /app`
- `GET /app/{path:path}`
- `/app/inspection` is a product SPA route served through `GET /app/{path:path}`
- `GET /workbench` -> `410 Gone`
- `GET /variant-workbench` (deprecated internal validation page)

## Project and Bootstrap

Preferred:

- `GET /api/projects`
- `POST /api/projects`
- `GET /api/projects/{project_id}/state`

Compatibility-only:

- `GET /api/state`
- `POST /api/demo/reset`
- `GET /api/strings`
- `GET /api/strings/{business_key}`

Bootstrap contract:

- `GET /api/projects/{project_id}/state` is the product bootstrap and returns `project`, `schema`, `rel_summary`, `candidate_dev_version`, `dev_versions`, `imports`, and `jobs`.
- `GET /api/state` is the compatibility bootstrap for `/variant-workbench` and frozen default-project validation flows and additionally returns `trash_count` and `samples`.
- `/app` should not call compatibility bootstrap or compatibility string routes.

See also:

- [product-bootstrap.md](product-bootstrap.md)

## Imports and Jobs

Preferred:

- `POST /api/projects/{project_id}/imports/directory`
- `POST /api/projects/{project_id}/imports/upload-folder/preview`
- `POST /api/projects/{project_id}/imports/upload-folder`
- `GET /api/projects/{project_id}/imports`
- `GET /api/projects/{project_id}/imports/{import_batch_id}/report`
- `GET /api/projects/{project_id}/jobs`
- `GET /api/projects/{project_id}/jobs/{job_id}`
- `GET /api/projects/{project_id}/jobs/{job_id}/report`
- `GET /api/projects/{project_id}/jobs/{job_id}/artifact/{name}`

Compatibility-only:

- `/api/imports/...`
- `/api/jobs/...`

## Read Models

Preferred:

- `GET /api/projects/{project_id}/scopes/summary`
- `GET /api/projects/{project_id}/scopes/compare`
- `GET /api/projects/{project_id}/translation-queue`
- `GET /api/projects/{project_id}/master/entries/{business_key}`
- `GET /api/projects/{project_id}/master/search`
- `GET /api/projects/{project_id}/entries/{business_key}/variants`
- `GET /api/projects/{project_id}/orphan-variants`

Compatibility-only:

- `/api/scopes/summary`
- `/api/scopes/compare`
- `/api/translation-queue`
- `/api/master/...`

Query conventions:

- scope refs use `rel/current` or `dev/<version>`
- compare supports `base`, `target`, `lang`, `search`, filters, `page`, and `page_size`
- queue supports `target`, `lang`, `search`, priority filters, `page`, and `page_size`
- variant inspection is read-only and intended for debugging and operator support, not product writes
- `GET /api/projects/{project_id}/entries/{business_key}/variants` returns canonical variants grouped by source plus current bindings/orphan state
- `GET /api/projects/{project_id}/orphan-variants` returns reusable canonical variants with no active bindings
- there is no retained inspection endpoint

## Workflow Actions

Preferred:

- `POST /api/projects/{project_id}/dev-versions/import`
- `GET /api/projects/{project_id}/dev-versions`
- `GET /api/projects/{project_id}/dev-versions/{version}`
- `POST /api/projects/{project_id}/scopes/rel/current/hotfix/active`
- `POST /api/projects/{project_id}/scopes/rel/current/hotfix/passive`
- `POST /api/projects/{project_id}/promote/preview`
- `POST /api/projects/{project_id}/promote/execute`
- `POST /api/projects/{project_id}/variants/trash/delete`
- `POST /api/projects/{project_id}/variants/trash/restore`
- `POST /api/projects/{project_id}/fill`
- `POST /api/projects/{project_id}/fill/upload-folder`
- `POST /api/projects/{project_id}/qa`
- `POST /api/projects/{project_id}/qa/upload-folder`

Compatibility-only:

- default-project variants of the routes above

Product policy:

- hotfix remains API-only and internal-only
- `/app` does not expose a hotfix workflow

No longer part of the live API:

- `POST /api/rel/hotfix/active`
- `POST /api/rel/hotfix/passive`
- `POST /api/trash/delete`
- `POST /api/trash/restore`

Trash contract:

- delete request: `scope_ref` plus `business_keys[]`
- restore request: `variant_ids[]`
- delete removes the active binding in the selected scope and only trashes the affected variant when it no longer has active bindings
- variants that lose their last active binding without being trashed become `orphan`
- restore only clears the trashed state for the specified variants; it does not rebind scopes

Compatibility Route Audit

Keep temporarily:

- `/api/state`
- `/api/demo/reset`
- `/api/strings`
- `/api/strings/{business_key}`
- `/api/imports/directory`
- `/api/imports/upload-folder`
- `/api/imports/upload-folder/preview`
- `/api/imports`
- `/api/imports/{import_batch_id}/report`
- `/api/jobs`
- `/api/jobs/{job_id}`
- `/api/jobs/{job_id}/report`
- `/api/jobs/{job_id}/artifact/{name}`
- `/api/dev-versions`
- `/api/dev-versions/{version}`
- `/api/dev-versions/import`
- `/api/scopes/summary`
- `/api/scopes/compare`
- `/api/translation-queue`
- `/api/master/entries/{business_key}`
- `/api/master/search`
- `/api/promote/preview`
- `/api/promote/execute`
- `/api/fill`
- `/api/fill/upload-folder`
- `/api/qa`
- `/api/qa/upload-folder`

Replace now:

- `/api/rel/hotfix/active`
- `/api/rel/hotfix/passive`
- `/api/trash/delete`
- `/api/trash/restore`

Delete after compatibility-page migration:

- all compatibility-only routes listed under "Keep temporarily"

## Error Semantics

- invalid scope refs and invalid business parameters return `400`
- missing resources, missing artifacts, and cross-project access to imports/jobs/reports/artifacts return `404`
- request-body validation errors continue to return `422`

## Current Gaps

These capabilities are not part of the live API:

- schema editing after project creation
- Translation Memory endpoints
- permission or audit endpoints

## Source of Truth

- Router files under `app/routers/` define the live paths.
- `app/schemas.py` defines request and response models.
- `app/routers/inspection.py` plus `app/services/variant/inspection.py` define lifecycle inspection reads.
- `/docs` is the easiest way to inspect the current contract.
