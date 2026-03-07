# Overview

Momo TMS is a localization workflow prototype built around Excel import, project-defined schemas, scope-aware variants, branch comparison, fill, QA, promote, and job reports.

The current runtime is already project-scoped and variant-oriented. The old flat service modules are gone; the live backend is organized under `app/routers/` and `app/services/<domain>/`.

## What Is Live

- Multi-project runtime with project creation and schema storage
- Variant-oriented write model: `entries`, `variants`, `scope_bindings`, `retained_variants`
- Read APIs for branch summary, branch compare, translation queue, and master query
- Product frontend at `/app`
- Internal validation page at `/variant-workbench`
- Folder upload support for import, fill, and QA
- Project-scoped hotfix and variant-aware trash APIs
- Read-only inspection APIs for entry variants, retained variants, and orphan variants
- Job-based execution and report/artifact storage

## Core Concepts

- `Project`: top-level boundary for schema, entries, variants, imports, and jobs
- `Schema`: fixed columns plus project-defined translation and remark columns
- `Entry`: stable identity keyed by `business_key`
- `Variant`: mutable content node under one entry
- `Scope Binding`: selects which variant is active for one scope such as `rel/current` or `dev/2.3.1`
- `Read Models`: projections built from active bindings for overview, compare, queue, and master lookup

## Main User Flows

1. Create a project and define translation and remark columns.
2. Upload or import `.xlsx` files into an import batch.
3. Execute dev import into a `dev/<version>` scope.
4. Inspect branch summary, compare, translation queue, and master query.
5. Run fill, QA, and promote.
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
- `/app/imports`: import, dev import, fill, QA, promote, jobs, reports, and artifacts
- `/app/inspection`: retained/orphan lifecycle inspection and business-key variant lookup
- `/app/projects/new`: explicit project creation route
- `/workbench`: removed; `GET /workbench` returns `410 Gone`
- `/variant-workbench`: deprecated internal validation page
- `/docs`: OpenAPI

## Bootstrap Boundary

- `GET /api/projects/{project_id}/state` is the product bootstrap for `/app`.
- `GET /api/state` is compatibility-only bootstrap for `/variant-workbench` and remaining default-project validation flows.
- Compatibility bootstrap still includes `trash_count` and `samples`; product bootstrap does not.
- Project bootstrap contract lives in [../runtime/product-bootstrap.md](../runtime/product-bootstrap.md).

## Repo Map

- `app/`: FastAPI app, services, SQLite bootstrap, static assets
- `frontend/`: React + TypeScript source for `/app`
- `app/static/product-app/`: built frontend assets served by FastAPI
- `tests/`: backend and E2E coverage
- `docs/`: agent-oriented project context

## Current Boundaries

- Product behavior is project-scoped first.
- Compatibility endpoints still exist for default project `1`.
- Compatibility write routes for hotfix and trash are gone; only project-scoped replacements remain.
- The compatibility layer still exposes `/api/state`, `/api/strings`, `/api/dev-versions`, and similar default-project routes for validation surfaces.
- New work should prefer explicit domain modules over compatibility facades.
- `/workbench` is gone and intentionally not redirected.
- `/variant-workbench` remains available only as a deprecated internal regression page.
- Schema is fixed when a project is created; there is no schema-edit API.
- `/app` owns no-project empty state, project-switch reset behavior, imports/jobs cockpit, and read-only lifecycle inspection.
- Hotfix remains internal-only and is intentionally not exposed in `/app`.

## Next-Step Planning

- Use [../operations/backlog.md](../operations/backlog.md) as the working checklist.
- Treat that file as the current execution plan for post-refactor cleanup and product convergence.
