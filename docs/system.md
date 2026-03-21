# System

## Purpose

- own the runtime mental model, architecture boundaries, package map, and system-level invariants

## Read This When

- you are changing backend structure, domain rules, lifecycle semantics, or runtime boundaries
- you need the shared vocabulary for entries, variants, scopes, and bindings

## Owns

- product and API boundaries
- core terminology and mental model
- package responsibilities
- database table inventory
- scope, lifecycle, and canonical-source invariants

## Does Not Own

- HTTP route inventory or payload schemas
- local setup or validation commands
- detailed workflow rules for import, mutation, sync, fill, QA, or Excel handling

## Update When

- package responsibilities, boundaries, tables, lifecycle rules, or canonical-source semantics change

## Runtime Boundaries

- `/app` is the only operator-facing product surface
- `GET /workbench` and `GET /variant-workbench` stay removed and return `410 Gone`
- runtime APIs are project-scoped and branch-oriented
- `GET /api/projects/{project_id}/state` is the bootstrap contract for `/app`
- public branch writes go through `/branches/mutations` and `/branches/replace/*`
- trash and restore stay under `/variants/trash/*`
- project schema is fixed after project creation; there is no schema-edit API
- `rel/current` direct mutation remains API-only and internal-only
- `retained` has been removed entirely; inactive variants are only `orphan` or `trashed`
- default to the best current-runtime design instead of preserving legacy routes, legacy UX flows, or old-data semantics
- old local databases are not a design-compatibility target by default; prefer reset or reseed over adding compatibility shims or dual-model fallback unless migration work is explicit

## Core Model

`Project`

- top-level boundary for schema, entries, variants, imports, and jobs

`Schema`

- fixed columns: `business_key`, `source`
- project-defined translation columns and remark columns
- `file_name` is runtime metadata derived from workbook path, not a schema column

`Entry`

- stable business slot keyed by `(project_id, business_key)`
- stores no translations directly

`Variant`

- mutable content node under one entry
- current identity is the parent entry plus canonical `source`
- runtime keeps one canonical non-trashed same-source variant under an entry
- carries `file_name`, `source`, `translations`, `remarks`, and lifecycle timestamps

`Scope Binding`

- selects which variant is active for one entry in one scope
- one scope can bind only one variant per entry
- different scopes may bind different variants for the same entry

`Read Models`

- product-facing projections built from active bindings
- branch summary, branch compare, translation queue, and master query are projection-based rather than table-shaped

## Shared Mental Model

- `business_key` identifies the stable slot, not the content itself
- a single entry may have multiple variants because source text can evolve
- scopes decide which variant is active right now
- authority differences explain why `rel` and `dev` treat the same canonical variant differently

Current branches:

- `rel/current`
- `dev/<version>`

Authority rule of thumb:

- rel-owned same-source content stays authoritative when a dev scope hits the same canonical variant

## Variant Lifecycle

Live states:

- `active`: referenced by at least one scope binding
- `orphan`: no active binding but still reusable for future same-source hits
- `trashed`: explicitly deleted from normal runtime usage

Default product reads use active variants only. Orphan and trashed variants are excluded from normal overview, compare, queue, master query, fill, and QA flows.

## Package Map

HTTP routers:

- `pages.py`: `/app` plus `/workbench` and `/variant-workbench` tombstones
- `projects_state.py`: project list or create, bootstrap, and demo reset
- `imports_jobs.py`: project-scoped import batch APIs, jobs, reports, and artifacts
- `scopes_read_models.py`: project-scoped branch summary, compare, queue, and master query
- `workflows.py`: project-scoped branch mutation, sync, trash, restore, fill, and QA
- `inspection.py`: read-only canonical variant and orphan inspection

Domain services:

- `app/services/project/`: project creation, schema loading, bootstrap assembly, and workbook header resolution
- `app/services/imports/`: import batch parsing and persistence
- `app/services/branch/`: scope refs, mutation policy, sync policy, and dev branch metadata
- `app/services/variant/`: repositories, canonical variant catalog, bindings, lifecycle workflows, and inspection assembly
- `app/services/read_models/`: projection services for branch summary, compare, queue, and master query
- `app/services/workflows/`: job orchestration for mutation, sync, fill, and QA
- `app/services/shared/`: IO helpers, job storage, and utility helpers
- `app/services/demo/`: demo seeding and sample workbook generation

## Database Tables

Current schema version: `variant-v5`

Live tables:

- `projects`
- `project_schemas`
- `entries`
- `variants`
- `variant_translations`
- `variant_remarks`
- `scope_bindings`
- `dev_versions`
- `imports`
- `import_rows`
- `jobs`

Legacy snapshot and canonical tables are not part of the live model. Old local DBs are not kept design-compatible by default; incompatible runtimes are rebuilt or reseeded to the current schema instead of being migrated in place unless migration work is explicitly part of the task.

## System Data Flow

Branch mutation:

1. router accepts direct patches or import-batch input
2. workflow service opens a job and stages files when needed
3. branch services resolve scope policy and canonical same-source variants
4. binding and lifecycle services update active scope bindings
5. job reports and artifacts are stored under the jobs runtime

Read models:

1. routers parse scope refs and filters
2. repository helpers load lightweight scope projections
3. read-model services compute compare state and queue priority
4. only the current page is hydrated into full row payloads

Bootstrap:

1. `/app` calls `ProjectStateService`
2. the service assembles the product bootstrap directly from project-scoped state
