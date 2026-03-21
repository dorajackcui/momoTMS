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

- Start here: [docs/README.md](docs/README.md)
- Runtime and validation: [docs/runtime.md](docs/runtime.md)
- System model and invariants: [docs/system.md](docs/system.md)
- Routes and payload contracts: [docs/contracts.md](docs/contracts.md)
- Workflow and Excel rules: [docs/workflows.md](docs/workflows.md)
- User-facing product guide: [docs/user-guide.md](docs/user-guide.md)
- Agent instructions: [AGENTS.md](AGENTS.md)
- Archived legacy material: [archive/README.md](archive/README.md)
