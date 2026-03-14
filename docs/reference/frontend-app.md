# Frontend App

The repository serves one operator-facing frontend.

## Product Surface

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

## Product Responsibilities

`/app` currently covers:

- project selection and creation
- no-project empty state
- project switching with project-scoped reset
- branch overview
- branch compare
- translation queue
- master query
- import preview and guided header mapping
- dev import execution through branch mutation
- fill and QA execution
- promote preview and execution through branch sync
- jobs, reports, and artifact inspection
- canonical and orphan inspection plus business-key variant lookup

## Frontend And Backend Contract

The product app depends on:

- project-scoped bootstrap data from `/api/projects/{project_id}/state`
- paginated compare and queue APIs
- import preview data with `available_headers`, `suggested_mapping`, and `missing_targets`
- job detail, report, and artifact APIs
- canonical entry-variant and orphan inspection APIs
- project-scoped branch mutation and sync routes plus fill and QA routes

The product app stores the selected project id locally, clears it when no projects exist, and refreshes branch state from project-scoped APIs only.

## Boundaries

- `/app` is the only operator-facing surface
- `/app` should not depend on removed compatibility routes
- project schema is defined during `/app/projects/new` and is fixed after creation
- `/app` owns the no-project empty state and project-switch reset behavior

Out of scope in the current product app:

- bulk inline translation editing
- schema editing after project creation
- release hotfix UI
- Translation Memory UI
- permission or audit management

## Related Docs

- bootstrap contract: [product-bootstrap.md](product-bootstrap.md)
- HTTP routes: [api.md](api.md)
- local setup and build: [../development/local-setup.md](../development/local-setup.md)
