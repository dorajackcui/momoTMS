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

## Windows Sandbox Note

- in Codex or other workspace-sandboxed agents, `.\.venv\Scripts\python.exe` only runs without escalation when the venv is backed by a Python interpreter that is also inside the repo or another allowed execution root
- if `.venv\pyvenv.cfg` points to a user-profile install such as `C:\Users\...\AppData\Local\Programs\Python\Python311`, the Windows venv launcher will try to execute that external base interpreter and the sandbox will reject it with errors such as `Unable to create process using ...` or `Access denied`
- when that happens, do not keep retrying pytest commands or switch to ad hoc invocation tricks first; check `.venv\pyvenv.cfg` and fix the venv root cause once
- preferred fix: rebuild `.venv` from a repo-local Python copy so test commands stay inside the workspace boundary
- in workspace-sandboxed agents, the one-time bootstrap copy from `AppData` into the repo may itself require escalation because the source interpreter is outside the workspace; that is expected

Windows PowerShell:

```powershell
Get-Content -Encoding utf8 .venv\pyvenv.cfg
scripts\bootstrap_local_python.ps1 -PythonHome C:\Users\<you>\AppData\Local\Programs\Python\Python311
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

Expected result after the rebuild:

- `.venv\pyvenv.cfg` should point at `D:\...\momoTMS\.python-home\python.exe` or another repo-local path
- after that, the standard Windows pytest commands below should run without repeated escalation requests
- if pytest still needs escalation after the rebuild, treat that as a new problem and inspect the current `.venv\pyvenv.cfg` again

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

If this command fails with `Unable to create process using ...` on a path outside the repo, read `Windows Sandbox Note` above before retrying.

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

Focused branch-cycle TDD flow:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_tdd_branch_cycle.py
```

This test creates an isolated project with translation columns `en`, `fr`, and `es`, remark columns `Version` and `SpeakerName`, and pivot configuration `en -> fr/es`. It then bulk-seeds `rel/current` from a small synthetic 2.4 workbook, bootstraps `dev/2.5.3` from a synthetic 2.5 workbook while schema-mapped remarks are written for newly created variants, and applies a dev content mutation with that same 2.5 workbook to populate translations after bootstrap.

Use the local smoke runner when you want to exercise the expanded branch cycle against the large desktop workbooks without adding those files to the normal pytest suite. The runner seeds `rel/current`, bootstraps and content-updates two dev branches, then replaces `rel/current` from the second dev branch:

```powershell
.\.venv\Scripts\python.exe scripts\run_branch_cycle_smoke.py --reset --release-workbook <path-to-release.xlsx> --dev-workbook <path-to-first-dev.xlsx> --next-dev-workbook <path-to-second-dev.xlsx>
```

Use the query-plan helper to verify that bulk content mutation binding lookups use the entry/variant index before running large smoke:

```powershell
.\.venv\Scripts\python.exe scripts\check_content_mutation_query_plan.py
```

Pass workbook paths with `--release-workbook`, `--dev-workbook`, and optionally `--next-dev-workbook`, or set `MOMO_TMS_RELEASE_WORKBOOK` and `MOMO_TMS_DEV_WORKBOOK` for the first two paths. If neither is provided, the smoke runner looks for `data/branch_cycle_smoke_inputs/2.4diff3.xlsx` and `data/branch_cycle_smoke_inputs/2.5diff3.xlsx`. `--next-dev-workbook` defaults to `--dev-workbook`, and `--next-dev-version` defaults to `2.5.4`. It writes to the isolated runtime root `data/branch_cycle_smoke` unless `--runtime-root` is provided.

The smoke runner prints wall-clock checkpoints for project creation, release seed, each dev bootstrap workbook parse, each dev bootstrap, each content workbook parse, each content mutation, and final replace. It also prints service stage timings when summaries include `stages`. Because content mutation is the known long-running risk, each content mutation has live row progress and aborts after `--max-content-seconds` seconds by default. Use `--stop-after content-batch`, `--stop-after next-content-batch`, or `--stop-after replace-current-rel` depending on how far you want the local smoke to run, or set `--max-content-seconds 0` only when intentionally allowing the full mutation to run.

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
- branch-cycle TDD or smoke runner changes: run `tests/test_tdd_branch_cycle.py` and `tests/test_branch_cycle_smoke_runner.py`; run `scripts/run_branch_cycle_smoke.py --reset` only for local large-workbook smoke coverage
- frontend `/app` changes: run `npm run build:app`, then `npm run test:e2e` when user-visible flows changed
- docs-only changes: run `scripts/validate_docs.py`, then manually verify wording, ownership, and behavior claims the validator cannot prove
- test-harness changes: run the directly impacted suite plus any docs validation needed for changed test references or commands
- on Windows agent sessions, if pytest unexpectedly needs escalation, inspect `.venv\pyvenv.cfg` before retrying; a venv rooted in `AppData` is an environment problem, not a flaky test failure

## Final Summary Expectation

- report the commands that ran
- if anything was not run, say exactly what was not run and why
- do not treat docs validation as proof of behavior; keep manual verification claims explicit
