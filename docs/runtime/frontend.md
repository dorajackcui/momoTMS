# Frontend

The repository currently serves three browser surfaces.

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
- `/app/projects/new`

## Validation Surfaces

- `/workbench`: legacy/compatibility validation UI
- `/variant-workbench`: variant-model validation UI

These pages are still useful for validation, but they are not the long-term product shell.

## Product Responsibilities

`/app` currently covers:

- project selection and creation
- branch overview
- branch compare
- translation queue
- master query
- import preview and guided header mapping
- dev import execution
- fill and QA execution
- promote preview and execution
- job/report inspection

Out of scope in the current product app:

- bulk inline translation editing
- schema editing after project creation
- Translation Memory UI
- permission or audit management

## Frontend and Backend Contract

The product app depends on:

- project-scoped bootstrap data from `/api/projects/{project_id}/state`
- paginated compare and queue APIs
- import preview data with `available_headers`, `suggested_mapping`, and `missing_targets`
- job detail/report APIs

The product app stores selected project id locally and refreshes branch state from the project-scoped APIs.

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
