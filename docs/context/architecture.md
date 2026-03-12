# Architecture

This document maps the current package layout to runtime responsibilities.

## Backend Layers

The backend is a small layered FastAPI application:

1. SQLite data store in `app/db.py`
2. HTTP routers in `app/routers/`
3. Domain services in `app/services/<domain>/`
4. Repository and record types inside the variant domain
5. Static frontend serving through FastAPI

## Package Layout

### `app/routers/`

HTTP boundary only.

- `pages.py`: `/app` plus `/workbench` and `/variant-workbench` tombstones (`410`)
- `projects_state.py`: project bootstrap, project create, demo reset
- `imports_jobs.py`: project-scoped import batch APIs, upload preview, jobs, reports, artifacts
- `scopes_read_models.py`: project-scoped branch summary, compare, queue, master query
- `workflows.py`: project-scoped branch mutation/sync writes, fill, QA, trash/restore
- `inspection.py`: read-only canonical entry-variant inspection plus orphan inspection

### `app/services/branch/`

Branch semantics and policy source of truth.

- `models.py`: `ScopeType` and `ScopeRef`
- `policy.py`: scope-specific mutation and sync policy rules
- `mutations.py`: generic scope mutation execution for direct and import-batch inputs
- `sync.py`: generic scope-to-scope sync preview and execute
- `service.py`: dev branch metadata and branch-oriented read delegation

### `app/services/project/`

Project and schema services.

- list/create projects
- product bootstrap assembly in `state.py`
- load schema
- preview and resolve workbook headers
- validate translation language keys

### `app/services/imports/`

Import batch service.

- scan directories or uploaded files
- parse workbook rows with schema-driven header mapping
- persist `imports` and `import_rows`
- build preview payloads for guided mapping

### `app/services/variant/`

Core write model.

- `repositories.py`: SQL and hydration
- `services.py`: entry, canonical source-variant catalog, orphan lifecycle, and scope binding services
- `workflows.py`: project-scoped trash/delete and restore workflows
- `records.py`: typed record shapes
- `inspection.py`: project-scoped canonical variant and orphan inspection assembly

### `app/services/read_models/`

Projection services for product-facing reads.

- branch summary
- branch compare
- translation queue
- master query
- repository-first scope projection, then page-sized hydration

### `app/services/workflows/`

Thin job orchestration only.

- `fill.py`: fill artifact generation
- `qa.py`: QA scan/report
- `workbench.py`: job-oriented orchestration that delegates branch mutation/sync and variant lifecycle workflows

### `app/services/shared/`

Cross-cutting helpers.

- `io.py`: normalization helpers and fill matching
- `jobs.py`: job table, report files, artifacts
- `utils.py`: timestamps and utility helpers

### `app/services/demo/`

Demo data seeding and sample workbook generation.

## Database Tables

Current schema version: `variant-v5`.

Main tables:

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

Legacy snapshot/canonical tables are no longer part of the live model. Incompatible local DBs are rebuilt to the current schema instead of being migrated in place.

## Development Rule

- New development must not add or extend old data semantic compatibility behavior.
- If a model change invalidates existing local data, prefer reset/reseed over startup migration, read-time canonicalization, or dual-semantics fallback unless migration is explicitly required.
- Existing compatibility-only API surfaces are a separate concern from old data semantics and should not be used to justify new data migration debt.

## Data Flow

### Branch Mutation

1. Router receives directory path or uploaded folder.
2. `WorkflowService` creates a job and stages files when needed.
3. `ImportService` parses workbooks and writes `imports` plus `import_rows`.
4. `BranchMutationService` adapts direct or import-batch input into scope changes.
5. Entry, variant, and binding services resolve canonical same-source variants, apply scope policy, and update scope bindings.
6. Job report is written to disk and indexed in `jobs`.

### Read Models

1. Router parses scope refs and filters.
2. Repository helpers load lightweight scope projections and active-binding search results.
3. `ReadModelService` computes compare state, diff categories, and priority status from projection metadata.
4. Only the current page of business keys is hydrated into full row payloads.

### Fill / QA

1. Router accepts a directory or uploaded folder.
2. `WorkflowService` stages input and opens a job.
3. Workflow service reads workbook rows using schema-resolved columns.
4. Output report or artifact is written under the job directory.

### Bootstrap

1. Product routes use `ProjectStateService`.
2. `ProjectStateService` assembles the product bootstrap directly.

### Runtime Migration

1. `app/db.py` keeps schema version `variant-v5`.
2. Startup rebuilds the local schema when the stored version differs.
3. The live schema enforces one non-trashed `(entry_id, source)` row through a partial unique index.
4. Model changes should continue to prefer reset/reseed over old-data semantic migration.

## Architectural Rules

- Routers should stay thin.
- Business rules belong in domain or workflow services.
- SQL belongs in repositories, not routers.
- New code should import explicit submodules instead of relying on package re-exports.
- Runtime APIs are project-scoped and branch-oriented.
- Lifecycle inspection source of truth is `app/routers/inspection.py` plus `app/services/variant/inspection.py`.
