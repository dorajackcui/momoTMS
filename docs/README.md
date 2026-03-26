# Documentation Map

## Purpose

- provide the single index for the active documentation set
- define companion docs and owner-doc routing

## Read This When

- you need to decide what to read before starting a task
- you need to choose the single owner doc for behavior facts
- you need to separate behavior ownership from runtime or verification guidance

## Owns

- the active doc list
- companion-doc guidance
- task-to-doc routing

## Does Not Own

- runtime commands
- verification commands or docs checks
- contracts, invariants, or workflow rules

## Update When

- an active doc is added, removed, renamed, or re-scoped

## Session Baseline

- start from [../AGENTS.md](../AGENTS.md)
- read [system.md](system.md) for shared project context and invariants
- read [testing.md](testing.md) for validation commands, test isolation, and docs checks
- read [runtime.md](runtime.md) only when the task touches setup, run, env, reset, or local runtime paths

## Active Docs

- [runtime.md](runtime.md): install, run, env overrides, reset behavior, and local runtime paths
- [testing.md](testing.md): pytest, Playwright, docs validation, test isolation, and change-type verification guidance
- [system.md](system.md): terminology, model, boundaries, package map, and invariants
- [contracts.md](contracts.md): page routes, API routes, bootstrap, frontend contract, and errors
- [workflows.md](workflows.md): import, mutation, sync, trash, restore, fill, QA, Excel, and normalization rules
- [user-guide.md](user-guide.md): user-facing product introduction, branch and variant concepts, and common product operations

## Task Routing

Choose exactly one owner doc below for behavior facts. Pair it with [testing.md](testing.md) for verification, and add [runtime.md](runtime.md) only when you need setup or local runtime guidance.

- setup, run, env, reset, or local runtime paths: [runtime.md](runtime.md)
- backend architecture, domain model, lifecycle, or invariants: [system.md](system.md)
- API, router, bootstrap, SPA route, or error changes: [contracts.md](contracts.md)
- import, mutation, sync, trash, restore, fill, QA, or Excel rules: [workflows.md](workflows.md)
- user-facing introduction, product glossary, or operator guidance: [user-guide.md](user-guide.md)
- docs-only work: choose the owner doc above from the behavior you changed, then use [testing.md](testing.md) for docs checks

## Related

- agent workflow and closeout rules: [../AGENTS.md](../AGENTS.md)
