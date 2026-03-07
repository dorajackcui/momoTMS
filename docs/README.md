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
- [runtime/api-surface.md](runtime/api-surface.md): current HTTP routes and compatibility-route policy
- [runtime/frontend.md](runtime/frontend.md): `/app`, workbench pages, frontend source, and build/runtime expectations
- [rules/io-and-excel.md](rules/io-and-excel.md): normalization, import, fill, and QA rules
- [operations/performance.md](operations/performance.md): scale assumptions and current performance posture

## Task Shortcuts

- Project setup or schema behavior:
  Read [context/overview.md](context/overview.md), then [context/domain-model.md](context/domain-model.md).
- Backend refactor in `app/services`:
  Read [context/architecture.md](context/architecture.md), then [context/domain-model.md](context/domain-model.md).
- API or router changes:
  Read [runtime/api-surface.md](runtime/api-surface.md), then the matching router under `app/routers/`.
- `/app` frontend work:
  Read [runtime/frontend.md](runtime/frontend.md), then `frontend/src/App.tsx`.
- Import, fill, QA, or Excel handling:
  Read [rules/io-and-excel.md](rules/io-and-excel.md), then `app/services/imports/` or `app/services/workflows/`.

## Reading Rules

- Prefer current code over docs when details conflict.
- Treat these docs as a description of the current runtime, not a future-spec backlog.
- Use OpenAPI at `/docs` for exact request and response schemas.
