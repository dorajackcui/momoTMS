# Momo TMS Agent Guide

Use this file as the repo-level default for Codex and other coding agents.

## Start Here

- Read [docs/README.md](docs/README.md) for the active documentation map and owner-doc routing.
- Read [docs/runtime.md](docs/runtime.md) for validation commands and docs checks.
- Read the single owner doc matched by the task routing below.
- Read [code_review.md](code_review.md) before finalizing a change.

## Scope Of This File

- `AGENTS.md` owns agent workflow, doc routing, closeout rules, and non-negotiable guardrails.
- Active runtime facts live in the six files under `docs/`.
- Historical material lives under `archive/`.

## Windows PowerShell Encoding

- On Windows PowerShell, prefer explicit UTF-8 when reading or writing repo text files to avoid mojibake and misread content.
- Use `Get-Content -Encoding utf8` when reading text files from the repo unless you already know a different encoding is required.
- Use explicit UTF-8 for write commands such as `Set-Content -Encoding utf8` or `Out-File -Encoding utf8` when updating repo text files from PowerShell.
- If Windows PowerShell 5.1 still renders UTF-8 text incorrectly in the console, set `[Console]::OutputEncoding = [System.Text.Encoding]::UTF8` before inspecting file contents.

## Active Vs Archived Docs

- Treat files under `docs/` as active guidance for the current runtime.
- Treat files under `archive/` as preserved history only.
- When archive content conflicts with active docs or code, prefer current code and update the active docs.

## Repo Map

- `app/`: FastAPI app, routers, services, DB bootstrap, static assets
- `frontend/`: React + TypeScript source for `/app`
- `docs/`: active human-facing documentation
- `archive/`: legacy plans, reviews, and implemented historical material
- `tests/`: backend and Playwright coverage

## Runtime Guardrails

- `/app` is the only operator-facing product surface.
- `GET /workbench` and `GET /variant-workbench` must stay `410 Gone`.
- Public APIs stay project-scoped under `/api/projects/{project_id}/...`.
- Branch writes go through `/branches/mutations` and `/branches/replace/*`.
- Trash and restore stay under `/variants/trash/*`.
- Project schema is fixed after project creation. Do not add schema-edit behavior unless the task explicitly requires it.
- The live write model is canonical-source based: one entry per `business_key`, one non-trashed same-source variant under an entry, and scope bindings choose the active variant.
- `retained` is gone. Inactive variants are only `orphan` or `trashed`.
- Default to the best current-runtime design. Do not preserve legacy design, legacy routes, legacy UX flows, or old-data semantics unless the task explicitly requires migration or compatibility work.
- Old local databases are not a design-compatibility target by default. Prefer reset or reseed over adding compatibility shims, fallback branches, or dual-model behavior unless migration work is explicitly required.

## Active Docs

- [docs/README.md](docs/README.md): index only; use it to choose the owner doc quickly.
- [docs/runtime.md](docs/runtime.md): install, run, env overrides, reset behavior, validation commands, and docs checks.
- [docs/system.md](docs/system.md): terminology, core model, runtime boundaries, package responsibilities, DB tables, and system-level invariants.
- [docs/contracts.md](docs/contracts.md): page routes, API inventory, bootstrap contract, frontend or backend contract, and error semantics.
- [docs/workflows.md](docs/workflows.md): import, mutation, sync, trash, restore, fill, QA, Excel, and normalization rules.
- [docs/user-guide.md](docs/user-guide.md): user-facing project introduction, branch and variant concepts, and common product operations.

## Task Routing

Choose one owner doc below for behavior facts. Use [docs/runtime.md](docs/runtime.md) separately for validation commands and docs checks.

- setup, run, env, reset, validation, or local runtime paths: owner doc is [docs/runtime.md](docs/runtime.md)
- backend architecture, domain model, package boundaries, lifecycle rules, or DB shape: owner doc is [docs/system.md](docs/system.md); validation still comes from [docs/runtime.md](docs/runtime.md)
- API, router, bootstrap, SPA route, page contract, or error behavior changes: owner doc is [docs/contracts.md](docs/contracts.md); validation still comes from [docs/runtime.md](docs/runtime.md)
- import, mutation, sync, trash, restore, fill, QA, Excel, or normalization changes: owner doc is [docs/workflows.md](docs/workflows.md); validation still comes from [docs/runtime.md](docs/runtime.md)
- user-facing introduction, product glossary, or operator guidance changes: owner doc is [docs/user-guide.md](docs/user-guide.md); validation still comes from [docs/runtime.md](docs/runtime.md)
- docs-only work: read [docs/README.md](docs/README.md), choose the owner doc above, update that doc instead of copying the same fact elsewhere, and use [docs/runtime.md](docs/runtime.md) for docs checks

## Documentation Loop

1. Identify the single owner doc for the task.
2. Update the owner doc in the same change as the code or behavior update.
3. Update [docs/README.md](docs/README.md) only when the active doc map or routing changes.
4. Update `README.md` only when quick start, onboarding, or public entrypoints changed.
5. Run `.venv/bin/python scripts/validate_docs.py` when docs changed or when changing documented routes, commands, local links, repo-relative file paths, or test references. Use [docs/runtime.md](docs/runtime.md) for the exact automated coverage and required manual follow-through.
6. Mention the docs validator result in the final summary. If it was not run, say exactly why.

## Done Means

- Code and docs match the current runtime behavior.
- Relevant active docs are updated in the same change.
- The owner doc was updated instead of copying the same fact into multiple files.
- The right validation ran, or the final summary says exactly what was not run and why.
- No removed compatibility route or old data semantic behavior was reintroduced accidentally.
