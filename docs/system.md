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
- runtime APIs are project-scoped, with branch-oriented workflows plus project-wide variant workspace reads
- `GET /api/projects/{project_id}/state` is the bootstrap contract for `/app`
- public branch writes go through `/branches/mutations` and `/branches/replace/*`
- branch delete (unbind) stays under `/variants/trash/delete`; project trash is at `/variants/trash`
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
- optional project-level pivot configuration stored alongside the schema as `pivot_language` plus `pivoted_languages`
- `file_name` is runtime metadata derived from workbook path, not a schema column

`Entry`

- stable business slot keyed by `(project_id, business_key)`
- stores no translations directly

`Variant`

- mutable content node under one entry
- current identity is the parent entry plus canonical `source`
- runtime keeps one canonical non-trashed same-source variant under an entry
- carries `file_name`, `source`, `translations`, `remarks`, and lifecycle timestamps
- also carries variant-level pivot review metadata: `pivot_status`, optional changed-owner branch ref, `pivot_changed_at`, `pivot_reviewed_at`, and `pivot_status_updated_at`

`Scope Binding`

- selects which variant is active for one entry in one scope
- one scope can bind only one variant per entry
- different scopes may bind different variants for the same entry

`Read Models`

- product-facing reads are organized as scope catalog reads, project-wide variant workspace reads, and history queries
- `master` is a read-only scope over all live non-trashed variants in the project; it is not a writable branch
- the variants workspace query returns one row per live non-trashed variant and can include both `active` and `orphan` lifecycle states

## Shared Mental Model

- `business_key` identifies the stable slot, not the content itself
- a single entry may have multiple variants because source text can evolve
- branch is the operator-facing selection layer: product URLs, branch pickers, and branch-first read or write routes should use branch terminology
- scope remains an internal selector term and read-model term where the system needs to talk about `master`, selector parsing, or shared read-model machinery
- `variant` remains the live content entity that branches bind and workflows inspect
- `pivot` remains variant-local workflow state for pivot-language review; it is not a branch or scope concept
- scopes decide which variant is active right now
- authority differences explain why `rel` and `dev` treat the same canonical variant differently

Current branches:

- `rel/current`
- `dev/<version>`

Authority rule of thumb:

- rel-owned same-source content stays authoritative when a dev scope hits the same canonical variant

Dev branch bootstrap metadata:

- `dev_versions` stores branch identity plus the lifecycle fields `bootstrap_state`, `bootstrapped_at`, `bootstrap_job_id`, and `bootstrap_import_batch_id`
- `bootstrap_state` is derived from `bootstrapped_at`: it is `not_bootstrapped` before the dedicated bootstrap workflow succeeds and `bootstrapped` after it completes

## Variant Lifecycle

Three states with strict definitions:

- `active`: referenced by at least one scope binding; participates in fill and read models
- `orphan`: no active binding but still live; participates in fill and read models via `BranchRef.orphan()` computed scope
- `trashed`: explicitly removed from the project via project trash; does not participate in fill, read models, same-source candidates, or entry timeline

State resolution:
1. `trashed_at` is not NULL → **trashed**
2. Has bindings → **active**
3. Otherwise → **orphan**

Allowed transitions:
- **Active → Orphan**: last real binding removed (via branch delete, replace, or any unbind operation)
- **Orphan → Active**: new binding created (via mutation same-source reuse, bootstrap same-source reuse)
- **Orphan → Trashed**: explicit project trash operation
- **Trashed is terminal**: no restore, no cleanup, no way back

`BranchRef.orphan()` is a readable computed scope. It is not a writable branch: mutations, bootstrap, and replace cannot target it. The scope-members query returns all variants with zero bindings and `trashed_at IS NULL`.

Branch delete is a pure unbind operation. The last binding removal produces orphan, not trash. Project trash is a separate explicit operation targeting orphan variants only.

## Package Map

HTTP routers:

- `pages.py`: `/app` plus `/workbench` and `/variant-workbench` tombstones
- `projects_state.py`: project list or create, bootstrap, and demo reset
- `imports_jobs.py`: project-scoped import batch APIs, jobs, reports, and artifacts
- `scopes_read_models.py`: project-scoped branch summary, scope catalog reads, same-source history candidates, and legacy master-scope lookup aliases
- `workflows.py`: project-scoped branch mutation, sync, trash, fill, and QA
- `inspection.py`: read-only project-wide variants workspace plus canonical variant and orphan inspection

Domain services:

- `app/services/project/`: project creation and schema loading live in `service.py`; `/app` bootstrap assembly lives in `bootstrap.py`
- `app/services/imports/`: import batch parsing and persistence
- `app/services/branch/`: scope refs and policy live with branch write or replace orchestration; `replace.py` owns branch replace execution, and `mutations.py` coordinates branch-scoped writes. Operator-facing branch metadata and detail reads live in `app/services/read_models/derived/branch_catalog.py`
- `app/services/variant/`: pure variant-domain package only. `entries.py` owns entry access, `store.py` plus `repositories.py` own canonical same-source persistence, `catalog.py` owns variant content rules, `pivot.py` owns variant-level pivot status coordination for pivot-language changes and reviews, `bindings.py` owns raw binding commands and lookups, `state_coordinator.py` composes binding writes with orphan refresh, and `lifecycle.py` owns orphan or trash state transitions. Operator-facing inspection, hydration, and workflow orchestration are not part of this package.
- `app/services/read_models/`: the only operator-facing read side. `selectors.py`, `types.py`, `repository.py`, and `hydrate.py` define shared selectors, row types, raw queries, and canonical assembly; `datasets/` owns the stable scope-members, live-variants, history, and entry-timeline datasets; `derived/` owns branch catalog, branch summary, plus replace, fill, and pivot preview views built on top of those datasets
- `app/services/workflows/`: job-backed application orchestration. `application.py` is the workflow façade for routers, while `trash.py`, `fill.py`, and `qa.py` execute workflow behavior by consuming the shared read-model datasets when they need project history or live variant reads
- `app/services/shared/`: IO helpers, job storage, and utility helpers
- `app/services/demo/`: demo seeding and sample workbook generation

## Database Tables

Current schema version: `variant-v11`

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

The `dev_versions` table stores dev-branch metadata plus bootstrap state:

- `bootstrapped_at`
- `bootstrap_job_id`
- `bootstrap_import_batch_id`

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
2. `app/services/read_models/repository.py` loads raw scope members, live variants, history candidates, entry timelines, and projection rows
3. `app/services/read_models/hydrate.py` is the single assembly path for variant content, bindings, lifecycle state, and pivot metadata
4. datasets and derived views build on top of that shared repository plus hydrator pair instead of re-defining their own query rules

Bootstrap:

1. `/app` calls `ProjectBootstrapService`
2. the service validates the project once, then assembles project metadata, schema, lightweight release summary, active dev branch metadata, imports, and jobs directly from project-scoped state
