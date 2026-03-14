# Testing And Validation

This page is the source of truth for validation commands, test isolation, and docs verification expectations.

## Test Isolation

- `tests/conftest.py` overrides the DB, jobs, and demo paths for each pytest run using a temporary runtime root.
- `tests/e2e/product-app-empty.spec.js` also spawns an isolated runtime by setting the same environment variables before starting `uvicorn`.
- If a test or script depends on a writable runtime, prefer those env vars instead of hard-coding `data/` paths.

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

- backend or domain changes: run `python -m pytest -q`
- API or routing changes: run `tests/test_variant_api.py` and `tests/test_service_package_smoke.py`
- branch workflow changes: run `tests/test_branch_service.py` and `tests/test_io_flows.py`
- frontend `/app` changes: run `npm run build:app`, then E2E when user-visible flows changed
- docs-only changes: manually verify links, commands, file paths, route states, and cited test names against current code

## Docs Verification Checklist

- confirm every changed file path still exists
- confirm every referenced command exists in `package.json`, `pyproject.toml`, or the runtime docs
- confirm route states and route groups against `app/routers/`
- confirm cited tests exist under `tests/`
