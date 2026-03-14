# Momo TMS Agent Guide

Use this file as the repo-level default for Codex and other coding agents.

## Start Here

- Read [docs/README.md](docs/README.md) for the active documentation map.
- Read [docs/development/local-setup.md](docs/development/local-setup.md) before changing setup, runtime paths, or reset behavior.
- Read [docs/development/testing-and-validation.md](docs/development/testing-and-validation.md) before changing tests, commands, or docs that mention validation.
- Read [code_review.md](code_review.md) before finalizing a change.

## Active Vs Archived Docs

- Treat files under `docs/` as active guidance for the current runtime.
- Treat files under `archive/` as preserved history only.
- When archive content conflicts with active docs or code, prefer current code and update the active docs.

## Repo Map

- `app/`: FastAPI app, routers, services, DB bootstrap, static assets
- `frontend/`: React + TypeScript source for `/app`
- `docs/`: active human-facing documentation
- `archive/`: legacy plans, reviews, and implemented historical material
- `tests/`: backend and Playwright coverage

## Core Commands

- install backend: `python -m pip install -e '.[dev]'`
- install frontend deps: `npm install`
- run backend: `uvicorn app.main:app --reload`
- build frontend: `npm run build:app`
- backend regression: `python -m pytest -q`
- API regression: `python -m pytest -q tests/test_variant_api.py tests/test_service_package_smoke.py`
- branch workflow regression: `python -m pytest -q tests/test_branch_service.py tests/test_io_flows.py`
- frontend E2E: `PLAYWRIGHT_BROWSERS_PATH=.playwright npm run test:e2e`

## Runtime Rules

- `/app` is the only operator-facing product surface.
- `GET /workbench` and `GET /variant-workbench` must stay `410 Gone`.
- Public APIs stay project-scoped under `/api/projects/{project_id}/...`.
- Branch writes go through `/branches/mutations` and `/branches/sync/*`.
- Trash and restore stay under `/variants/trash/*`.
- Project schema is fixed after project creation. Do not add schema-edit behavior unless the task explicitly requires it.
- The live write model is canonical-source based: one entry per `business_key`, one non-trashed same-source variant under an entry, and scope bindings choose the active variant.
- `retained` is gone. Inactive variants are only `orphan` or `trashed`.
- Prefer reset or reseed over adding new old-data semantic compatibility or dual-model fallback unless the task explicitly requires migration work.

## Task Routing

- backend or domain changes: read [docs/architecture/backend.md](docs/architecture/backend.md) and [docs/architecture/domain-model.md](docs/architecture/domain-model.md)
- API or router changes: read [docs/reference/api.md](docs/reference/api.md) and the matching file under `app/routers/`
- frontend `/app` changes: read [docs/reference/frontend-app.md](docs/reference/frontend-app.md), [docs/reference/product-bootstrap.md](docs/reference/product-bootstrap.md), and `frontend/src/App.tsx`
- import, fill, QA, or Excel workflow changes: read [docs/data-formats/excel-format.md](docs/data-formats/excel-format.md)
- docs-only changes: update the narrowest source-of-truth doc and verify links, commands, paths, routes, and test names against current code

## Done Means

- Code and docs match the current runtime behavior.
- Relevant active docs are updated in the same change.
- The right validation ran, or the final summary says exactly what was not run and why.
- No removed compatibility route or old data semantic behavior was reintroduced accidentally.
