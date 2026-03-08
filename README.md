# Momo TMS

Momo TMS is a FastAPI + SQLite localization workflow prototype built around project-defined Excel schemas, scope-aware variants, import batches, fill, QA, promote, and job reports.

This `README` is only the top-level entrypoint. For actual project context, start at [docs/README.md](docs/README.md).

## Start Here

- Docs index: [docs/README.md](docs/README.md)
- App bootstrap: [`app/main.py`](/Users/zhiyangcui/Documents/Momo_TMS/app/main.py)
- Database schema/bootstrap: [`app/db.py`](/Users/zhiyangcui/Documents/Momo_TMS/app/db.py)
- Routers: [`app/routers`](/Users/zhiyangcui/Documents/Momo_TMS/app/routers)
- Services: [`app/services`](/Users/zhiyangcui/Documents/Momo_TMS/app/services)
- Frontend source: [`frontend`](/Users/zhiyangcui/Documents/Momo_TMS/frontend)

## Quick Start

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
uvicorn app.main:app --reload
```

Runtime surfaces:

- Product app: `http://127.0.0.1:8000/app`
- Imports and jobs: `http://127.0.0.1:8000/app/imports`
- Inspection: `http://127.0.0.1:8000/app/inspection`
- New project: `http://127.0.0.1:8000/app/projects/new`
- Variant workbench: `http://127.0.0.1:8000/variant-workbench` (deprecated internal regression page)
- OpenAPI: `http://127.0.0.1:8000/docs`

If demo data is missing, call `POST /api/demo/reset`.

## Frontend Build

```bash
npm run build:app
```

The frontend source lives in `frontend/`, but scripts are defined in the repository root `package.json`.

## Test

Backend:

```bash
. .venv/bin/activate
python -m pytest -q
```

E2E:

```bash
. .venv/bin/activate
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

In another terminal:

```bash
PLAYWRIGHT_BROWSERS_PATH=.playwright npm run test:e2e
```

## Repo Structure

- `app/`: FastAPI app, routers, services, schemas, static assets
- `frontend/`: React + TypeScript source for `/app`
- `docs/`: agent-oriented project context
- `tests/`: backend and E2E tests

## Current Runtime Notes

- `/app` is the only operator-facing product surface.
- New work should prefer project-scoped APIs such as `/api/projects/{project_id}/...`.
- Default-project compatibility routes still exist for project `1` and stay frozen.
- `/variant-workbench` is a deprecated internal validation page.
- `GET /workbench` returns `410 Gone`.
- The live write model is `entries + variants + scope_bindings` with canonical `business_key + source` variants.
- `retained` has been removed completely; inactive variants are modeled only as `orphan` or `trashed`.
- Project schema is defined at project creation time and is not editable afterward.
