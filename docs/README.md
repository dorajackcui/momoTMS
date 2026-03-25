# Documentation Map

## Purpose

- provide the single index for the active documentation set

## Read This When

- you need to choose the owner doc before reading or editing docs
- you need to separate behavior ownership from validation guidance

## Owns

- the active doc list
- task-to-doc routing

## Does Not Own

- runtime commands
- contracts, invariants, or workflow rules

## Update When

- an active doc is added, removed, renamed, or re-scoped

## Active Docs

- [runtime.md](runtime.md): install, run, env, reset, validation, and docs checks
- [system.md](system.md): terminology, model, boundaries, package map, and invariants
- [contracts.md](contracts.md): page routes, API routes, bootstrap, frontend contract, and errors
- [workflows.md](workflows.md): import, mutation, sync, trash, restore, fill, QA, Excel, and normalization rules
- [user-guide.md](user-guide.md): user-facing project introduction, branch and variant concepts, and common product operations

## Task Routing

Choose exactly one owner doc below for behavior facts. Use [runtime.md](runtime.md) separately for validation commands and docs checks.

- setup, run, env, reset, or validation work: [runtime.md](runtime.md)
- backend architecture, domain model, lifecycle, or invariants: [system.md](system.md) for behavior facts; use [runtime.md](runtime.md) for validation commands and docs checks
- API, router, bootstrap, SPA route, or error changes: [contracts.md](contracts.md) for behavior facts; use [runtime.md](runtime.md) for validation commands and docs checks
- import, mutation, sync, trash, restore, fill, QA, or Excel rules: [workflows.md](workflows.md) for behavior facts; use [runtime.md](runtime.md) for validation commands and docs checks
- user-facing introduction, product glossary, or operator guidance: [user-guide.md](user-guide.md) for behavior facts; use [runtime.md](runtime.md) for validation commands and docs checks
- docs-only work: choose the owner doc above from the behavior you changed, then use [runtime.md](runtime.md) for docs checks

## Related

- agent workflow: [../AGENTS.md](../AGENTS.md)
