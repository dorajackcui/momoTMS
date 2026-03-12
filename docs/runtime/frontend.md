# Frontend

The repository serves one product surface.

## Product Surface

`/app` is the operator-facing frontend.

Current implementation:

- source: `frontend/`
- stack: React 19 + TypeScript + Vite
- entry: `frontend/src/App.tsx`
- build output: `app/static/product-app/`
- serving route: `GET /app` through `app/routers/pages.py`

Main product routes inside the SPA:

- `/app`
- `/app/overview`
- `/app/compare`
- `/app/queue`
- `/app/master`
- `/app/imports`
- `/app/inspection`
- `/app/projects/new`

Product boundary:

- `/app` is the only operator-facing surface.
- `/app` bootstraps from `GET /api/projects/{project_id}/state`.
- `/app` should not depend on default-project compatibility routes.
- Project schema is defined during `/app/projects/new` and is fixed after creation.
- `/app` owns the no-project empty state and project-switch reset behavior.

## Validation Surfaces

- `/workbench`: removed; `GET /workbench` returns `410 Gone`
- `/variant-workbench`: removed; `GET /variant-workbench` returns `410 Gone`

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
- jobs/report/artifact inspection
- canonical/orphan inspection and business-key variant lookup

Out of scope in the current product app:

- bulk inline translation editing
- schema editing after project creation
- release hotfix UI
- Translation Memory UI
- permission or audit management

## Frontend and Backend Contract

The product app depends on:

- project-scoped bootstrap data from `/api/projects/{project_id}/state`
- paginated compare and queue APIs
- import preview data with `available_headers`, `suggested_mapping`, and `missing_targets`
- job detail/report APIs
- canonical entry-variant and orphan inspection APIs
- project-scoped branch mutation/sync routes plus fill and QA

The product app stores selected project id locally, clears it when no projects exist, and refreshes branch state from project-scoped APIs only.

## Build and Run

Install backend and frontend dependencies, then run:

```bash
. .venv/bin/activate
uvicorn app.main:app --reload
```

Build the product app when frontend source changes:

```bash
npm run build:app
```

The root `package.json` owns the frontend scripts. There is no separate `frontend/package.json`.
