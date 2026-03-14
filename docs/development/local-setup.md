# Local Setup

This page is the source of truth for installing, running, and resetting the local runtime.

## Runtime Paths

Default local paths:

- database: `data/tms.db`
- jobs: `data/jobs`
- demo samples: `data/demo_samples`

Environment overrides:

- `MOMO_TMS_DB_PATH`: override the SQLite database path
- `MOMO_TMS_JOBS_DIR`: override the jobs, reports, and artifacts directory
- `MOMO_TMS_DEMO_ROOT`: override the generated demo sample directory

Source of truth:

- DB path and schema bootstrap: `app/db.py`
- jobs path: `app/services/shared/jobs.py`
- demo sample root and reset logic: `app/services/demo/service.py`

## Install

Backend:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
```

Frontend dependencies:

```bash
npm install
```

## Run

Build the product app after frontend changes:

```bash
npm run build:app
```

Start the backend:

```bash
. .venv/bin/activate
uvicorn app.main:app --reload
```

If the frontend build is missing, `GET /app` returns `503` until `app/static/product-app/index.html` exists.

Useful URLs:

- `/app`
- `/app/projects/new`
- `/app/inspection`
- `/docs`

## Demo Reset

- `POST /api/demo/reset` clears jobs, deletes the local DB, rebuilds the schema, regenerates demo sample files, reseeds the default demo project, and returns the product bootstrap for project `1`.
- Use it when demo data is missing or when you want to restore the default local sample project quickly.
- Prefer demo reset or isolated runtime paths over adding compatibility-only startup migration logic.
