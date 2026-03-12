# Overview

Momo TMS is a localization workflow prototype built around Excel import, project-defined schemas, scope-aware variants, branch comparison, fill, QA, scope sync to release, and job reports.

The current runtime is already project-scoped and variant-oriented. The old flat service modules are gone; the live backend is organized under `app/routers/` and `app/services/<domain>/`.

## What Is Live

- Multi-project runtime with project creation and schema storage
- Canonical-source write model: entry identity is `business_key`, variant identity is `business_key + source`, and scopes only bind active variants
- Schema version changes rebuild incompatible local DBs instead of applying old-data semantic migration
- Read APIs for branch summary, branch compare, translation queue, and master query under project-scoped `/branches` routes
- Product frontend at `/app`
- Folder upload support for import, fill, and QA
- Project-scoped branch mutation APIs plus variant-aware trash APIs
- Read-only inspection APIs for canonical entry variants and orphan variants
- Job-based execution and report/artifact storage

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

## Runtime Entry Points

- App bootstrap: `app/main.py`
- Database schema and connection helpers: `app/db.py`
- HTTP routers: `app/routers/`
- Project domain: `app/services/project/`
- Import domain: `app/services/imports/`
- Variant domain: `app/services/variant/`
- Read models: `app/services/read_models/`
- Workflow orchestration: `app/services/workflows/`
- Shared helpers and job storage: `app/services/shared/`
- Demo/sample seeding: `app/services/demo/`

## Main Runtime Surfaces

- `/app`: operator-facing React app
- `/app/imports`: import, branch mutation, fill, QA, sync, jobs, reports, and artifacts
- `/app/inspection`: canonical/orphan lifecycle inspection and business-key variant lookup
- `/app/projects/new`: explicit project creation route
- `/workbench`: removed; `GET /workbench` returns `410 Gone`
- `/variant-workbench`: removed; `GET /variant-workbench` returns `410 Gone`
- `/docs`: OpenAPI

## Bootstrap Boundary

- `GET /api/projects/{project_id}/state` is the product bootstrap for `/app`.
- Project bootstrap contract lives in [../runtime/product-bootstrap.md](../runtime/product-bootstrap.md).

## Repo Map

- `app/`: FastAPI app, services, SQLite bootstrap, static assets
- `frontend/`: React + TypeScript source for `/app`
- `app/static/product-app/`: built frontend assets served by FastAPI
- `tests/`: backend and E2E coverage
- `docs/`: agent-oriented project context

## Current Boundaries

- Product behavior is project-scoped first.
- New development must not add or extend old data semantic compatibility. If local data becomes incompatible after a model change, reset/reseed is preferred over adding migration or read-time fallback behavior unless migration is explicitly required by the task.
- Runtime APIs are project-scoped only.
- `retained` has been removed from the runtime entirely; inactive variants become `orphan`.
- New work should prefer branch/domain modules over storage-shaped helpers.
- `/workbench` and `/variant-workbench` both return `410 Gone`.
- Schema is fixed when a project is created; there is no schema-edit API.
- `/app` owns no-project empty state, project-switch reset behavior, imports/jobs cockpit, and read-only lifecycle inspection.
- rel/current direct mutation remains internal-only and is intentionally not exposed in `/app`.
