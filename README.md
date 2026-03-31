# Momo TMS

Momo TMS is a FastAPI + SQLite localization workflow prototype for project-defined Excel schemas, scope-aware variants, branch comparison, fill, QA, sync, and job reports.

## Quick Start

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

This repo does not use a separate frontend dev server in local development. Build the React app into `app/static/product-app`, then serve `/app` from FastAPI.

Build the product app and start the backend:

macOS or Linux:

```bash
npm run build:app
. .venv/bin/activate
uvicorn app.main:app --reload
```

Windows PowerShell:

```powershell
npm run build:app
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Useful URLs:

- Product app: `http://127.0.0.1:8000/app`
- New project: `http://127.0.0.1:8000/app/projects/new`
- OpenAPI: `http://127.0.0.1:8000/docs`

Windows troubleshooting:

- if `Activate.ps1` is blocked, do not activate the venv; run `.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload` directly
- if `.venv\Scripts\python.exe` points at an old machine path, delete `.venv` and recreate it on this machine
- if `py` or `python` is not available, install Python 3.11 first; if you already have a portable/local Python folder, `scripts/bootstrap_local_python.ps1 -PythonHome <path>` can copy it into the repo and rebuild `.venv`

If you want fresh demo data, call `POST /api/demo/reset`.

## Testing

See [docs/testing.md](docs/testing.md) for the full verification matrix, isolated runtime behavior, and docs checks.

Backend regression:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Frontend E2E:

```powershell
npm run test:e2e
```

`npm run test:e2e` uses repo-local browsers from `.playwright` and starts an isolated backend automatically unless `PLAYWRIGHT_BASE_URL` is set for attach-mode debugging.

## Basic Workflow

1. Create a project and define translation and remark columns.
2. Import `.xlsx` files into a project-scoped workflow.
3. Use `/app` to compare branches, inspect queues, run fill and QA, and promote dev content to release.

## Documentation

- Start here: [docs/README.md](docs/README.md)
- Runtime setup and reset: [docs/runtime.md](docs/runtime.md)
- Testing and verification: [docs/testing.md](docs/testing.md)
- System model and invariants: [docs/system.md](docs/system.md)
- Routes and payload contracts: [docs/contracts.md](docs/contracts.md)
- Workflow and Excel rules: [docs/workflows.md](docs/workflows.md)
- User-facing product guide: [docs/user-guide.md](docs/user-guide.md)
- Agent instructions: [AGENTS.md](AGENTS.md)
