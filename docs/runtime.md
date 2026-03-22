# Runtime

## Purpose

- own install, run, env override, reset, validation, and local runtime guidance

## Read This When

- you need to boot the app locally
- you are changing runtime paths, reset behavior, or validation commands
- you need to know which checks to run for a task
- you selected another owner doc and still need the right validation commands or docs checks

## Owns

- install steps
- build and run commands
- runtime paths and env overrides
- demo reset behavior
- validation commands and docs validation
- test isolation expectations

## Does Not Own

- domain model or lifecycle semantics
- HTTP route inventory or payload shape
- import, mutation, fill, QA, or Excel rules

## Update When

- setup commands, env vars, runtime paths, reset behavior, or validation commands change

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

- `POST /api/demo/reset` clears jobs, deletes the local DB, rebuilds the schema, regenerates demo sample files, reseeds the default demo project, and returns the product bootstrap for project `1`
- prefer demo reset or isolated runtime paths over adding compatibility-only startup migration logic
- old local databases are not preserved for design compatibility by default; when local data no longer matches the current runtime model, reset or reseed instead of adding fallback behavior unless migration work is explicitly required

## Test Isolation

- `tests/conftest.py` overrides DB, jobs, and demo paths for each pytest run using a temporary runtime root
- `tests/e2e/product-app-empty.spec.js` also spawns an isolated runtime by setting the same env vars before starting `uvicorn`
- if a test or script depends on a writable runtime, prefer those env vars instead of hard-coding `data/` paths

## Validation Commands

All commands assume the repo root is the current working directory.

Backend regression suite:

```bash
. .venv/bin/activate
python -m pytest -q
```

API and routing regression:

```bash
. .venv/bin/activate
python -m pytest -q tests/test_variant_api.py tests/test_service_package_smoke.py
```

Branch workflow regression:

```bash
. .venv/bin/activate
python -m pytest -q tests/test_branch_service.py tests/test_io_flows.py
```

Frontend build:

```bash
npm run build:app
```

Docs regression:

```bash
.venv/bin/python scripts/validate_docs.py
```

Docs validator coverage:

- scans repo-root Markdown plus all Markdown under `docs/`, `design/`, and `archive/`
- auto-checks local Markdown links, repo-relative file and directory references in code spans and fenced command examples, documented npm scripts, referenced test files, and the route inventory in `docs/contracts.md`
- does not prove wording, owner-doc selection, or behavior claims; manually verify those against current code and [docs/README.md](README.md)

End-to-end:

```bash
. .venv/bin/activate
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

In another terminal:

```bash
PLAYWRIGHT_BROWSERS_PATH=.playwright npm run test:e2e
```

## Change-Type Guidance

Use this section after selecting the owner doc from [docs/README.md](README.md); the other owner docs do not repeat validation commands.

- backend or domain changes: run `python -m pytest -q`
- API or routing changes: run `tests/test_variant_api.py` and `tests/test_service_package_smoke.py`
- branch workflow changes: run `tests/test_branch_service.py` and `tests/test_io_flows.py`
- frontend `/app` changes: run `npm run build:app`, then E2E when user-visible flows changed
- docs-only changes: run `.venv/bin/python scripts/validate_docs.py` to catch local links, repo paths, npm scripts, test refs, and active contract routes, then manually verify wording, ownership, and behavior claims the validator cannot prove
