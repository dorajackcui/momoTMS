# API Reference

This file summarizes the current HTTP surface. For exact schemas, use FastAPI OpenAPI at `/docs`.

## Route Policy

- the runtime is project-scoped and branch-centric
- `/app` should only call project-scoped APIs
- `GET /workbench` and `GET /variant-workbench` stay removed and return `410 Gone`

## Pages

- `GET /app`
- `GET /app/{path:path}`
- `/app/inspection` is a product SPA route served through `GET /app/{path:path}`
- `GET /workbench` -> `410 Gone`
- `GET /variant-workbench` -> `410 Gone`

## Projects And Bootstrap

- `GET /api/projects`
- `POST /api/projects`
- `GET /api/projects/{project_id}/state`
- `POST /api/demo/reset`

Bootstrap contract:

- `GET /api/projects/{project_id}/state` is the product bootstrap and returns `project`, `schema`, `release_summary`, `candidate_dev_branch`, `dev_branches`, `imports`, and `jobs`
- `/app` should bootstrap and refresh from project-scoped APIs only

See also:

- [product-bootstrap.md](product-bootstrap.md)

## Imports And Jobs

- `POST /api/projects/{project_id}/imports/directory`
- `POST /api/projects/{project_id}/imports/upload-folder/preview`
- `POST /api/projects/{project_id}/imports/upload-folder`
- `GET /api/projects/{project_id}/imports`
- `GET /api/projects/{project_id}/imports/{import_batch_id}/report`
- `GET /api/projects/{project_id}/jobs`
- `GET /api/projects/{project_id}/jobs/{job_id}`
- `GET /api/projects/{project_id}/jobs/{job_id}/report`
- `GET /api/projects/{project_id}/jobs/{job_id}/artifact/{name}`

## Branch Read Models

- `GET /api/projects/{project_id}/branches`
- `GET /api/projects/{project_id}/branches/compare`
- `GET /api/projects/{project_id}/branches/queue`
- `GET /api/projects/{project_id}/branches/master/entries/{business_key}`
- `GET /api/projects/{project_id}/branches/master/search`

Query conventions:

- scope refs use `rel/current` or `dev/<version>`
- compare supports `base_scope_ref`, `target_scope_ref`, `lang`, `search`, filters, `page`, and `page_size`
- queue supports `target_scope_ref`, `lang`, `search`, priority filters, `page`, and `page_size`

## Inspection Reads

- `GET /api/projects/{project_id}/entries/{business_key}/variants`
- `GET /api/projects/{project_id}/orphan-variants`

Inspection policy:

- inspection endpoints are read-only and intended for debugging and operator support, not product writes
- `entries/{business_key}/variants` returns canonical variants for one business key plus current bindings and lifecycle state
- `orphan-variants` returns reusable canonical variants with no active bindings
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

Workflow policy:

- `branches/mutations` is the only branch write entrypoint
- `branches/sync/*` is the only branch-to-branch sync entrypoint
- `/app` exposes dev import and promote as specialized UI flows built on the generic branch routes
- `rel/current` direct mutation remains API-only and internal-only

Trash contract:

- delete request: `scope_ref` plus `business_keys[]`
- restore request: `variant_ids[]`
- delete removes the active binding in the selected scope and only trashes the affected variant when it no longer has active bindings
- variants that lose their last active binding without being trashed become `orphan`
- restore only clears the trashed state for the specified variants; it does not rebind scopes

## Error Semantics

- invalid scope refs and invalid business parameters return `400`
- missing resources, missing artifacts, and cross-project access to imports, jobs, reports, and artifacts return `404`
- request-body validation errors return `422`

## Not In Scope

These capabilities are not part of the live API:

- schema editing after project creation
- Translation Memory endpoints
- permission or audit endpoints

## Source Of Truth

- router files under `app/routers/` define the live paths
- `app/schemas.py` defines request and response models
- `/docs` is the easiest way to inspect the current contract
- [../development/local-setup.md](../development/local-setup.md) and [../development/testing-and-validation.md](../development/testing-and-validation.md) define local run and verification commands
