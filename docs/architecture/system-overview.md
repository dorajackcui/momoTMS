# System Overview

Momo TMS is a localization workflow prototype built around Excel import, project-defined schemas, scope-aware variants, branch comparison, fill, QA, scope sync to release, and job reports.

## What Is Live

- Multi-project runtime with project creation and schema storage
- Canonical-source write model: entry identity is `business_key`, variant identity is `business_key + source`, and scopes bind the active variant
- Schema version changes rebuild incompatible local DBs instead of applying old-data semantic migration
- Project-scoped branch summary, compare, translation queue, and master query APIs
- Product frontend at `/app`
- Folder upload support for import, fill, and QA
- Project-scoped branch mutation APIs plus variant-aware trash APIs
- Read-only inspection APIs for canonical entry variants and orphan variants
- Job-based execution plus report and artifact storage

## Core Concepts

- `Project`: top-level boundary for schema, entries, variants, imports, and jobs
- `Schema`: fixed columns plus project-defined translation and remark columns
- `Entry`: stable identity keyed by `business_key`
- `Variant`: canonical source-content node under one entry
- `Scope Binding`: selects which variant is active for one scope such as `rel/current` or `dev/2.3.1`
- `Read Models`: projections built from active bindings for overview, compare, queue, and master lookup

## Main User Flows

1. Create a project and define translation and remark columns.
2. Upload or import `.xlsx` files into an import batch.
3. Execute a branch mutation into a `dev/<version>` scope.
4. Inspect branch summary, compare, translation queue, and master query.
5. Run fill, QA, and scope sync into release.
6. Inspect jobs, reports, and artifacts.

## Runtime Surfaces

- `/app`: operator-facing React app
- `/app/imports`: import, branch mutation, fill, QA, sync, jobs, reports, and artifacts
- `/app/inspection`: canonical and orphan inspection plus business-key variant lookup
- `/app/projects/new`: project creation route
- `/docs`: OpenAPI
- `GET /workbench`: `410 Gone`
- `GET /variant-workbench`: `410 Gone`

## Runtime Entry Points

- app bootstrap: `app/main.py`
- database bootstrap: `app/db.py`
- HTTP routers: `app/routers/`
- project domain: `app/services/project/`
- import domain: `app/services/imports/`
- branch domain: `app/services/branch/`
- variant domain: `app/services/variant/`
- read models: `app/services/read_models/`
- workflow orchestration: `app/services/workflows/`
- shared helpers and job storage: `app/services/shared/`
- demo reset and sample data: `app/services/demo/`

## Current Boundaries

- `/app` is the only operator-facing product surface.
- Runtime APIs are project-scoped only.
- `GET /api/projects/{project_id}/state` is the bootstrap contract for `/app`.
- New development must not add or extend old-data semantic compatibility behavior.
- `retained` has been removed from the runtime entirely; inactive variants are only `orphan` or `trashed`.
- Project schema is fixed when a project is created; there is no schema-edit API.
- `rel/current` direct mutation remains internal-only and is intentionally not exposed in `/app`.
