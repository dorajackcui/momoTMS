# Momo TMS Docs

This directory is the documentation entrypoint for agents and implementers.

The docs are organized by how quickly you need context:

1. Read [context/overview.md](context/overview.md) for the product, runtime shape, and code entrypoints.
2. Read [context/architecture.md](context/architecture.md) for package boundaries, tables, and data flow.
3. Read only the specific runtime or rules document needed for your task.

## Structure

- [context/overview.md](context/overview.md): what the project is, what is live today, and where the important code lives
- [context/domain-model.md](context/domain-model.md): core entities, scope semantics, variant lifecycle, and workflow rules
- [context/architecture.md](context/architecture.md): backend layers, package layout, database tables, and service boundaries
- [prd/0001-canonical-source-variant-model.md](prd/0001-canonical-source-variant-model.md): implemented canonical-source variant model and migration/acceptance reference
- [runtime/api-surface.md](runtime/api-surface.md): current project-scoped HTTP routes plus branch mutation/sync API surface
- [runtime/product-bootstrap.md](runtime/product-bootstrap.md): `/app` bootstrap contract for `GET /api/projects/{project_id}/state`
- [runtime/frontend.md](runtime/frontend.md): `/app`, workbench pages, frontend source, and build/runtime expectations
- [rules/io-and-excel.md](rules/io-and-excel.md): normalization, import, fill, and QA rules
- [operations/performance.md](operations/performance.md): scale assumptions and current performance posture
- [operations/backlog.md](operations/backlog.md): delivery-status snapshot after the branch-centric refactor
- [adr/0001-product-surface-and-compatibility-policy.md](adr/0001-product-surface-and-compatibility-policy.md): why `/app` is the product shell and branch APIs are project-scoped

## Task Shortcuts

- Project setup or schema behavior:
  Read [context/overview.md](context/overview.md), then [context/domain-model.md](context/domain-model.md).
- Backend refactor in `app/services`:
  Read [context/architecture.md](context/architecture.md), then [context/domain-model.md](context/domain-model.md).
- API or router changes:
  Read [runtime/api-surface.md](runtime/api-surface.md), then the matching router under `app/routers/`.
- `/app` frontend work:
  Read [runtime/product-bootstrap.md](runtime/product-bootstrap.md), then [runtime/frontend.md](runtime/frontend.md), then `frontend/src/App.tsx`.
- Import, fill, QA, or Excel handling:
  Read [rules/io-and-excel.md](rules/io-and-excel.md), then `app/services/imports/` or `app/services/workflows/`.
- Delivery status or runtime status:
  Read [operations/backlog.md](operations/backlog.md).

## Reading Rules

- Prefer current code over docs when details conflict.
- Treat these docs as a description of the current runtime, not a future-spec backlog.
- New development must not add or extend old data semantic compatibility paths. If a model change invalidates existing local data, prefer reset/reseed over migration fallback unless a task explicitly requires migration work.
- Use OpenAPI at `/docs` for exact request and response schemas.
