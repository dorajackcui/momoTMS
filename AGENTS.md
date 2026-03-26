# Momo TMS Agent Guide

Use this file as the repo-level default for Codex and other coding agents.

## Session Entry

Every session starts from this file.

- Read [docs/README.md](docs/README.md) for the active doc map, companion docs, and owner-doc routing.
- Read [docs/system.md](docs/system.md) for the shared project context, vocabulary, runtime boundaries, and invariants.
- Read [docs/testing.md](docs/testing.md) for verification strategy, test isolation, docs checks, and change-type guidance.
- Read exactly one behavior owner doc chosen from [docs/README.md](docs/README.md).
- Read [docs/runtime.md](docs/runtime.md) when the task touches setup, run, env, reset, or local runtime paths.
- Read [code_review.md](code_review.md) before finalizing a change.

## Scope Of This File

- `AGENTS.md` owns the session-entry flow, repo-wide guardrails, documentation workflow, and closeout rules.
- Active runtime facts live under `docs/`.
- Historical material lives under `archive/`.

## Documentation Sources Of Truth

- [docs/README.md](docs/README.md): active doc map and owner-doc routing
- [docs/system.md](docs/system.md): shared project context, mental model, and invariants
- [docs/testing.md](docs/testing.md): tests, validation commands, docs checks, and verification expectations
- [docs/runtime.md](docs/runtime.md): install, run, env overrides, reset behavior, and local runtime paths
- [docs/contracts.md](docs/contracts.md): page routes, API inventory, bootstrap contract, and error semantics
- [docs/workflows.md](docs/workflows.md): import, mutation, sync, trash, restore, fill, QA, and normalization rules
- [docs/user-guide.md](docs/user-guide.md): operator-facing product introduction, glossary, and common usage flow

## Windows PowerShell Encoding

- On Windows PowerShell, prefer explicit UTF-8 when reading or writing repo text files to avoid mojibake and misread content.
- Use `Get-Content -Encoding utf8` when reading text files from the repo unless you already know a different encoding is required.
- Use explicit UTF-8 for write commands such as `Set-Content -Encoding utf8` or `Out-File -Encoding utf8` when updating repo text files from PowerShell.
- If Windows PowerShell 5.1 still renders UTF-8 text incorrectly in the console, set `[Console]::OutputEncoding = [System.Text.Encoding]::UTF8` before inspecting file contents.

## Active Vs Archived Docs

- Treat files under `docs/` as active guidance for the current runtime.
- Treat files under `archive/` as preserved history only.
- When archive content conflicts with active docs or code, prefer current code and update the active docs.

## Repo Snapshot

- `app/`: FastAPI app, routers, services, DB bootstrap, and static assets
- `frontend/`: React + TypeScript product app for `/app`
- `tests/`: pytest and Playwright coverage
- `docs/`: active documentation set
- `archive/`: historical plans, reviews, and implemented history

## Non-Negotiable Runtime Guardrails

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

## Documentation Workflow

1. Start with the session-entry reading order above.
2. Choose the single behavior owner doc from [docs/README.md](docs/README.md).
3. Update that owner doc in the same change as the code or behavior update.
4. Update [docs/README.md](docs/README.md) only when the active doc map or routing changes.
5. Update `README.md` only when quick start, onboarding, or public entrypoints changed.
6. Use [docs/testing.md](docs/testing.md) to choose required verification. Run `scripts/validate_docs.py` when docs changed or when changing documented routes, commands, local links, repo-relative file paths, or test references.
7. Mention verification results in the final summary. If anything was not run, say exactly what was not run and why.

## Done Means

- Code and docs match the current runtime behavior.
- Relevant active docs are updated in the same change.
- The correct owner doc was updated instead of copying the same fact into multiple files.
- The right verification ran, or the final summary says exactly what was not run and why.
- No removed compatibility route or old-data semantic behavior was reintroduced accidentally.
