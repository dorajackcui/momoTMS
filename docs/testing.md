# Testing

## Purpose

- own automated verification commands, test isolation, docs checks, and change-type guidance

## Read This When

- you need to decide what to run for a task
- you are changing tests, validation scripts, or verification workflow
- you are editing docs, commands, routes, local links, or test references
- you need to understand isolated runtime expectations for pytest or Playwright

## Owns

- pytest and Playwright command matrix
- docs validator usage and coverage
- test isolation expectations
- change-type verification guidance
- verification evidence expectations

## Does Not Own

- app install or startup commands
- API inventory or workflow semantics
- user-facing product guidance

## Update When

- test commands, suite scope, isolation helpers, docs validator coverage, or verification expectations change

## Test Suite Map

Backend and service coverage:

- `tests/`: pytest suites for project, branch, workflow, IO, QA, pivot, and architecture behavior
- focused regression files include `tests/test_variant_api.py`, `tests/test_services_architecture.py`, `tests/test_branch_service.py`, and `tests/test_io_flows.py`

Frontend end-to-end coverage:

- `tests/e2e/`: Playwright specs and runtime helpers for the `/app` product surface
- `tests/e2e/support/server.js` owns the shared isolated backend launcher used by Playwright

Docs regression:

- `scripts/validate_docs.py` validates the active Markdown surface and documented repo references

## Test Isolation

- `tests/conftest.py` overrides DB, jobs, and demo paths for each pytest run using a temporary runtime root
- `tests/e2e/global-setup.js` starts an isolated Playwright runtime with the same env vars and tears it down after the suite
- `tests/e2e/product-app-empty.spec.js` uses the shared server helper to launch a dedicated empty runtime without depending on a manually started backend
- `scripts/playwright.js` keeps browsers under `.playwright`, starts an isolated backend automatically when needed, and fails fast when required local prerequisites are missing
- if a test or script depends on a writable runtime, prefer `MOMO_TMS_DB_PATH`, `MOMO_TMS_JOBS_DIR`, and `MOMO_TMS_DEMO_ROOT` over hard-coded `data/` paths

## Verification Commands

All commands assume the repo root is the current working directory.

Backend regression suite:

macOS or Linux:

```bash
.venv/bin/python -m pytest -q
```

Windows PowerShell:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

API and routing regression:

macOS or Linux:

```bash
.venv/bin/python -m pytest -q tests/test_variant_api.py tests/test_services_architecture.py
```

Windows PowerShell:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_variant_api.py tests/test_services_architecture.py
```

Branch workflow regression:

macOS or Linux:

```bash
.venv/bin/python -m pytest -q tests/test_branch_service.py tests/test_io_flows.py
```

Windows PowerShell:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_branch_service.py tests/test_io_flows.py
```

Frontend build prerequisite:

```bash
npm run build:app
```

Repo-local Playwright browser install:

```bash
npm run test:e2e:install
```

End-to-end:

Default repo-managed run:

```bash
npm run test:e2e
```

What `npm run test:e2e` does:

- uses repo-local browsers under `.playwright`
- starts an isolated backend automatically when `PLAYWRIGHT_BASE_URL` is not set
- fails fast with an actionable message when the frontend build or local `.venv` is missing

Attach Playwright to an already running backend only when you explicitly want that debugging mode.

macOS or Linux:

```bash
PLAYWRIGHT_BASE_URL=http://127.0.0.1:8000 npm run test:e2e
```

Windows PowerShell:

```powershell
$env:PLAYWRIGHT_BASE_URL = "http://127.0.0.1:8000"
npm run test:e2e
```

Docs regression:

macOS or Linux:

```bash
.venv/bin/python scripts/validate_docs.py
```

Windows PowerShell:

```powershell
.\.venv\Scripts\python.exe scripts\validate_docs.py
```

## Docs Validator Coverage

- scans repo-root Markdown plus all Markdown under `docs/`
- auto-checks local Markdown links, repo-relative file and directory references in code spans and fenced command examples, documented npm scripts, referenced test files, and the route inventory in `docs/contracts.md`
- does not prove wording, owner-doc selection, or behavior claims; manually verify those against current code and [docs/README.md](README.md)

## Change-Type Guidance

Use this section after selecting the owner doc from [docs/README.md](README.md).

- backend or domain changes: run `python -m pytest -q`
- API or routing changes: run `tests/test_variant_api.py` and `tests/test_services_architecture.py`
- branch workflow changes: run `tests/test_branch_service.py` and `tests/test_io_flows.py`
- frontend `/app` changes: run `npm run build:app`, then `npm run test:e2e` when user-visible flows changed
- docs-only changes: run `scripts/validate_docs.py`, then manually verify wording, ownership, and behavior claims the validator cannot prove
- test-harness changes: run the directly impacted suite plus any docs validation needed for changed test references or commands

## Final Summary Expectation

- report the commands that ran
- if anything was not run, say exactly what was not run and why
- do not treat docs validation as proof of behavior; keep manual verification claims explicit
