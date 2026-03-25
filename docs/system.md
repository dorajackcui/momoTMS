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

## Related Design Workspace

- use [../design/README.md](../design/README.md) for design-process guidance, current-state review, and design-gap tracking
- the `design/` folder supplements architecture work; it does not override runtime facts in `docs/`
- when a design note becomes a stable runtime fact, update this file or the matching owner doc under `docs/`

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
- optional `translation_pivots` topology stored alongside the schema as a full `lang -> pivot_lang | null` map
- `file_name` is runtime metadata derived from workbook path, not a schema column

`Entry`

- stable business slot keyed by `(project_id, business_key)`
- stores no translations directly

`Variant`

- mutable content node under one entry
- current identity is the parent entry plus canonical `source`
- runtime keeps one canonical non-trashed same-source variant under an entry
- carries `file_name`, `source`, `translations`, `remarks`, and lifecycle timestamps
- may also carry per-child pivot sync checkpoints through `variant_translation_sync_state`; the checkpoint is variant-level, not branch-level

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

Default product reads use active variants only. Orphan and trashed variants are excluded from normal overview, compare, queue, master query, and QA flows. `fill` is the main exception: it matches against the project's full variant history, preferring non-trashed same-source variants and only falling back to trashed history when no live same-source candidate remains.

## Package Map

HTTP routers:

- `pages.py`: `/app` plus `/workbench` and `/variant-workbench` tombstones
- `projects_state.py`: project list or create, bootstrap, and demo reset
- `imports_jobs.py`: project-scoped import batch APIs, jobs, reports, and artifacts
- `scopes_read_models.py`: project-scoped branch summary, compare, queue, and master query
- `workflows.py`: project-scoped branch mutation, sync, trash, restore, fill, and QA
- `inspection.py`: read-only canonical variant and orphan inspection

Domain services:

- `app/services/project/`: project creation and schema loading live in `service.py`; `/app` bootstrap assembly lives in `bootstrap.py`
- `app/services/imports/`: import batch parsing and persistence
- `app/services/branch/`: scope refs and policy live with branch write or replace orchestration; `registry.py` owns dev branch metadata and release summary, `details.py` owns branch entry hydration, `replace.py` owns branch replace execution, and `mutations.py` coordinates branch-scoped writes
- `app/services/variant/`: pure variant-domain package only. `entries.py` owns entry access, `store.py` plus `repositories.py` own canonical same-source persistence, `catalog.py` owns variant content rules, `pivot.py` owns variant-level pivot checkpoint coordination, `bindings.py` owns raw binding commands and lookups, `state_coordinator.py` composes binding writes with orphan refresh, and `lifecycle.py` owns orphan or trash state transitions. Operator-facing inspection, hydration, and workflow orchestration are not part of this package.
- `app/services/read_models/`: the only operator-facing read side. `summary.py`, `compare.py`, `queue.py`, and `master.py` expose use-case-specific read services; `hydration.py` and `inspection.py` own row hydration and historical inspection reads; `queries.py` owns lightweight projection queries
- `app/services/workflows/`: job-backed application orchestration. `application.py` is the workflow façade for routers, `fill_queries.py` owns fill-specific candidate reads, and `trash_restore.py`, `fill.py`, and `qa.py` execute workflow behavior
- `app/services/shared/`: IO helpers, job storage, and utility helpers
- `app/services/demo/`: demo seeding and sample workbook generation

## Database Tables

Current schema version: `variant-v6`

Live tables:

- `projects`
- `project_schemas`
- `entries`
- `variants`
- `variant_translations`
- `variant_translation_sync_state`
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
2. branch and read-model query repositories load lightweight scope projections and branch summary rows
3. read-model services compute compare state and queue priority from those projections
4. only the current page is hydrated into full row payloads for compare or master-style detail

Bootstrap:

1. `/app` calls `ProjectBootstrapService`
2. the service validates the project once, then assembles project metadata, schema, lightweight release summary, active dev branch metadata, imports, and jobs directly from project-scoped state
3. candidate dev branch detail reuses the active branch metadata list and only hydrates branch entries for the candidate branch when one exists
