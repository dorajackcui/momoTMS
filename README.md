# Momo TMS

Momo TMS is a FastAPI + SQLite localization workflow prototype for project-defined Excel schemas, scope-aware variants, branch comparison, fill, QA, sync, and job reports.

## Quick Start

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

Build the product app and start the backend:

```bash
npm run build:app
. .venv/bin/activate
uvicorn app.main:app --reload
```

Useful URLs:

- Product app: `http://127.0.0.1:8000/app`
- New project: `http://127.0.0.1:8000/app/projects/new`
- OpenAPI: `http://127.0.0.1:8000/docs`

If you want fresh demo data, call `POST /api/demo/reset`.

## Basic Workflow

1. Create a project and define translation and remark columns.
2. Import `.xlsx` files into a project-scoped workflow.
3. Use `/app` to compare branches, inspect queues, run fill and QA, and promote dev content to release.

## Documentation

- Human-facing docs index: [docs/README.md](docs/README.md)
- Local setup: [docs/development/local-setup.md](docs/development/local-setup.md)
- Testing and validation: [docs/development/testing-and-validation.md](docs/development/testing-and-validation.md)
- Terminology explainer: [docs/concepts/terminology.md](docs/concepts/terminology.md)
- API reference: [docs/reference/api.md](docs/reference/api.md)
- Agent instructions: [AGENTS.md](AGENTS.md)
- Archived legacy material: [archive/README.md](archive/README.md)

## Current Runtime Boundaries

- `/app` is the only operator-facing product surface.
- `GET /workbench` and `GET /variant-workbench` both return `410 Gone`.
- Public APIs are project-scoped under `/api/projects/{project_id}/...`.
- The live write model is canonical-source based: one entry per `business_key`, one non-trashed same-source variant under an entry, and scope bindings choose the active variant.
- `retained` is gone; inactive variants are only `orphan` or `trashed`.
