# Documentation Map

This directory is the active, human-facing reference layer for the current runtime.

Repo-level agent instructions live in [../AGENTS.md](../AGENTS.md). Historical material lives in [../archive/README.md](../archive/README.md).

## Start Here

- Local setup: [development/local-setup.md](development/local-setup.md)
- Testing and validation: [development/testing-and-validation.md](development/testing-and-validation.md)
- Terminology explainer: [concepts/terminology.md](concepts/terminology.md)
- System overview: [architecture/system-overview.md](architecture/system-overview.md)
- API reference: [reference/api.md](reference/api.md)

## Active Docs

### Concepts

- [concepts/terminology.md](concepts/terminology.md): human-oriented model explainer for entries, variants, scopes, orphan state, and authority

### Architecture

- [architecture/system-overview.md](architecture/system-overview.md): product surfaces, core flows, runtime entrypoints, and current boundaries
- [architecture/backend.md](architecture/backend.md): package layout, database tables, service responsibilities, and data flow
- [architecture/domain-model.md](architecture/domain-model.md): project, schema, variant lifecycle, scope rules, and workflow semantics

### Development

- [development/local-setup.md](development/local-setup.md): install, run, runtime paths, env overrides, and demo reset
- [development/testing-and-validation.md](development/testing-and-validation.md): test isolation, validation commands, and docs verification rules

### Reference

- [reference/api.md](reference/api.md): current HTTP surface and route policy
- [reference/frontend-app.md](reference/frontend-app.md): `/app` responsibilities, SPA routes, and frontend/backend contract
- [reference/product-bootstrap.md](reference/product-bootstrap.md): `GET /api/projects/{project_id}/state` contract

### Data Formats

- [data-formats/excel-format.md](data-formats/excel-format.md): normalization, schema-driven header mapping, import, fill, and QA rules

### Operations And Decisions

- [operations/performance.md](operations/performance.md): scale assumptions and current performance posture
- [decisions/adr-0001-product-surface-and-compatibility-policy.md](decisions/adr-0001-product-surface-and-compatibility-policy.md): why `/app` is the only product shell and why APIs are project-scoped

## Task Shortcuts

- New to the repo: start with [concepts/terminology.md](concepts/terminology.md), then [architecture/system-overview.md](architecture/system-overview.md)
- Backend refactor in `app/services/`: read [architecture/backend.md](architecture/backend.md), then [architecture/domain-model.md](architecture/domain-model.md)
- API or router changes: read [reference/api.md](reference/api.md), then the matching router under `app/routers/`
- Frontend `/app` work: read [reference/frontend-app.md](reference/frontend-app.md), then [reference/product-bootstrap.md](reference/product-bootstrap.md), then `frontend/src/App.tsx`
- Runtime setup or validation work: read [development/local-setup.md](development/local-setup.md) and [development/testing-and-validation.md](development/testing-and-validation.md)
- Import, fill, QA, or Excel handling: read [data-formats/excel-format.md](data-formats/excel-format.md)

## Reading Rules

- Prefer current code over docs when details conflict.
- Keep active runtime facts under `docs/`, not in `archive/`.
- Keep route inventories in [reference/api.md](reference/api.md), commands in `development/`, and agent instructions in [../AGENTS.md](../AGENTS.md).
