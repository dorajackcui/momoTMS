# API Surface

This file summarizes the current HTTP surface. For exact schemas, use FastAPI OpenAPI at `/docs`.

## Route Policy

The runtime exposes two API styles:

- project-scoped routes: preferred for new work
- default-project compatibility routes: kept for project `1`

When both exist, prefer the project-scoped route.

## Pages

- `GET /app`
- `GET /app/{path:path}`
- `GET /workbench`
- `GET /variant-workbench`

## Project and Bootstrap

Preferred:

- `GET /api/projects`
- `POST /api/projects`
- `GET /api/projects/{project_id}/state`

Compatibility:

- `GET /api/state`
- `POST /api/demo/reset`
- `GET /api/strings`
- `GET /api/strings/{business_key}`

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

Compatibility:

- `/api/imports/...`
- `/api/jobs/...`

## Read Models

Preferred:

- `GET /api/projects/{project_id}/scopes/summary`
- `GET /api/projects/{project_id}/scopes/compare`
- `GET /api/projects/{project_id}/translation-queue`
- `GET /api/projects/{project_id}/master/entries/{business_key}`
- `GET /api/projects/{project_id}/master/search`

Compatibility:

- `/api/scopes/summary`
- `/api/scopes/compare`
- `/api/translation-queue`
- `/api/master/...`

Query conventions:

- scope refs use `rel/current` or `dev/<version>`
- compare supports `base`, `target`, `lang`, `search`, filters, `page`, and `page_size`
- queue supports `target`, `lang`, `search`, priority filters, `page`, and `page_size`

## Workflow Actions

Preferred:

- `POST /api/projects/{project_id}/dev-versions/import`
- `GET /api/projects/{project_id}/dev-versions`
- `GET /api/projects/{project_id}/dev-versions/{version}`
- `POST /api/projects/{project_id}/promote/preview`
- `POST /api/projects/{project_id}/promote/execute`
- `POST /api/projects/{project_id}/fill`
- `POST /api/projects/{project_id}/fill/upload-folder`
- `POST /api/projects/{project_id}/qa`
- `POST /api/projects/{project_id}/qa/upload-folder`

Compatibility or legacy-shaped:

- `POST /api/rel/hotfix/active`
- `POST /api/rel/hotfix/passive`
- `POST /api/trash/delete`
- `POST /api/trash/restore`
- default-project variants of the routes above

## Current Gaps

These capabilities are not part of the live API:

- schema editing after project creation
- dedicated variant-detail endpoints
- dedicated retained-variant endpoints
- Translation Memory endpoints
- permission or audit endpoints

## Source of Truth

- Router files under `app/routers/` define the live paths.
- `app/schemas.py` defines request and response models.
- `/docs` is the easiest way to inspect the current contract.
