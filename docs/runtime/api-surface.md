# API Surface

This file summarizes the current HTTP surface. For exact schemas, use FastAPI OpenAPI at `/docs`.

## Route Policy

The runtime is project-scoped and branch-centric.

## Pages

- `GET /app`
- `GET /app/{path:path}`
- `/app/inspection` is a product SPA route served through `GET /app/{path:path}`
- `GET /workbench` -> `410 Gone`
- `GET /variant-workbench` -> `410 Gone`

## Project and Bootstrap

- `GET /api/projects`
- `POST /api/projects`
- `GET /api/projects/{project_id}/state`
- `POST /api/demo/reset`

Bootstrap contract:

- `GET /api/projects/{project_id}/state` is the product bootstrap and returns `project`, `schema`, `release_summary`, `candidate_dev_branch`, `dev_branches`, `imports`, and `jobs`.
- `/app` should only call project-scoped APIs.

See also:

- [product-bootstrap.md](product-bootstrap.md)

## Imports and Jobs

- `POST /api/projects/{project_id}/imports/directory`
- `POST /api/projects/{project_id}/imports/upload-folder/preview`
- `POST /api/projects/{project_id}/imports/upload-folder`
- `GET /api/projects/{project_id}/imports`
- `GET /api/projects/{project_id}/imports/{import_batch_id}/report`
- `GET /api/projects/{project_id}/jobs`
- `GET /api/projects/{project_id}/jobs/{job_id}`
- `GET /api/projects/{project_id}/jobs/{job_id}/report`
- `GET /api/projects/{project_id}/jobs/{job_id}/artifact/{name}`

## Read Models

- `GET /api/projects/{project_id}/branches`
- `GET /api/projects/{project_id}/branches/compare`
- `GET /api/projects/{project_id}/branches/queue`
- `GET /api/projects/{project_id}/branches/master/entries/{business_key}`
- `GET /api/projects/{project_id}/branches/master/search`
- `GET /api/projects/{project_id}/entries/{business_key}/variants`
- `GET /api/projects/{project_id}/orphan-variants`

Query conventions:

- scope refs use `rel/current` or `dev/<version>`
- compare supports `base_scope_ref`, `target_scope_ref`, `lang`, `search`, filters, `page`, and `page_size`
- queue supports `target_scope_ref`, `lang`, `search`, priority filters, `page`, and `page_size`
- variant inspection is read-only and intended for debugging and operator support, not product writes
- `GET /api/projects/{project_id}/entries/{business_key}/variants` returns canonical variants grouped by source plus current bindings/orphan state
- `GET /api/projects/{project_id}/orphan-variants` returns reusable canonical variants with no active bindings
- there is no retained inspection endpoint

## Workflow Actions

- `POST /api/projects/{project_id}/branches/mutations`
- `GET /api/projects/{project_id}/branches/dev`
- `GET /api/projects/{project_id}/branches/dev/{version}`
- `POST /api/projects/{project_id}/branches/sync/preview`
- `POST /api/projects/{project_id}/branches/sync/execute`
- `POST /api/projects/{project_id}/variants/trash/delete`
- `POST /api/projects/{project_id}/variants/trash/restore`
- `POST /api/projects/{project_id}/fill`
- `POST /api/projects/{project_id}/fill/upload-folder`
- `POST /api/projects/{project_id}/qa`
- `POST /api/projects/{project_id}/qa/upload-folder`

Product policy:

- `branches/mutations` is the only branch write entrypoint
- `branches/sync/*` is the only branch-to-branch sync entrypoint
- `/app` still exposes dev import and promote as specialized UI flows built on the generic branch routes
- rel/current direct mutation remains API-only and internal-only

Trash contract:

- delete request: `scope_ref` plus `business_keys[]`
- restore request: `variant_ids[]`
- trash APIs stay under `/variants/...`; they are not part of branch mutation or sync writes
- delete removes the active binding in the selected scope and only trashes the affected variant when it no longer has active bindings
- variants that lose their last active binding without being trashed become `orphan`
- restore only clears the trashed state for the specified variants; it does not rebind scopes

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
