# Runtime

## Purpose

- own install, run, env override, reset, and local runtime guidance

## Read This When

- you need to boot the app locally
- you are changing runtime paths, env vars, startup behavior, or demo reset behavior
- you need the canonical local runtime locations

## Owns

- install steps
- build and run commands
- runtime paths and env overrides
- demo reset behavior
- local runtime notes for `/app`

## Does Not Own

- automated verification commands or docs checks
- domain model or lifecycle semantics
- HTTP route inventory or payload shape
- import, mutation, fill, QA, or Excel rules

## Update When

- setup commands, env vars, runtime paths, startup behavior, or reset behavior change

## Runtime Paths

Default local paths:

- database: `data/tms.db`
- jobs: `data/jobs`
- demo samples: `data/demo_samples`

Environment overrides:

- `MOMO_TMS_DB_PATH`: override the SQLite database path
- `MOMO_TMS_JOBS_DIR`: override the jobs, reports, and artifacts directory
- `MOMO_TMS_DEMO_ROOT`: override the generated demo sample directory

Primary code locations:

- DB path and schema bootstrap: `app/db.py`
- jobs path: `app/services/shared/jobs.py`
- demo sample root and reset logic: `app/services/demo/service.py`

## Install

Backend:

macOS or Linux:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
```

Windows PowerShell:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e '.[dev]'
```

Frontend dependencies:

```bash
npm install
```

Repo-local Playwright browsers:

```bash
npm run test:e2e:install
```

## Run

Build the product app after frontend changes:

```bash
npm run build:app
```

Start the backend:

macOS or Linux:

```bash
. .venv/bin/activate
uvicorn app.main:app --reload
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload
```

If the frontend build is missing, `GET /app` returns `503` until `app/static/product-app/index.html` exists.

Useful URLs:

- `/app`
- `/app/projects/new`
- `/app/inspection`
- `/docs`

## Demo Reset

- `POST /api/demo/reset` clears jobs, deletes the local DB, rebuilds the schema, regenerates demo sample files, reseeds the default demo project, and returns the product bootstrap for project `1`
- prefer demo reset or isolated runtime paths over adding compatibility-only startup migration logic
- old local databases are not preserved for design compatibility by default; when local data no longer matches the current runtime model, reset or reseed instead of adding fallback behavior unless migration work is explicitly required
