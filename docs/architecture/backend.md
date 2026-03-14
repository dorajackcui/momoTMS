# Backend Architecture

This document maps the current package layout to runtime responsibilities.

## Layers

1. SQLite storage in `app/db.py`
2. HTTP routers in `app/routers/`
3. Domain services in `app/services/<domain>/`
4. Repository and record helpers inside the variant and read-model domains
5. Static frontend serving through FastAPI

## Package Layout

### `app/routers/`

HTTP boundary only.

- `pages.py`: `/app` plus `/workbench` and `/variant-workbench` tombstones
- `projects_state.py`: project list/create, product bootstrap, and demo reset
- `imports_jobs.py`: project-scoped import batch APIs, upload preview, jobs, reports, and artifacts
- `scopes_read_models.py`: project-scoped branch summary, compare, queue, and master query
- `workflows.py`: project-scoped branch mutation, sync, fill, QA, trash, and restore
- `inspection.py`: read-only canonical entry-variant inspection plus orphan inspection

### `app/services/branch/`

Branch semantics and policy source of truth.

- `models.py`: `ScopeType` and `ScopeRef`
- `policy.py`: scope-specific mutation and sync policy rules
- `mutations.py`: generic scope mutation execution for direct and import-batch inputs
- `sync.py`: generic scope-to-scope sync preview and execute
- `service.py`: dev branch metadata plus branch-oriented read delegation

### `app/services/project/`

Project and schema services.

- list and create projects
- assemble product bootstrap in `state.py`
- load schema and validate translation language keys
- preview and resolve workbook headers

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
- `workflows.py`: project-scoped trash, delete, and restore workflows
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
- `qa.py`: QA scan and report
- `workbench.py`: job-oriented orchestration that delegates branch mutation, sync, and variant lifecycle workflows

### `app/services/shared/`

Cross-cutting helpers.

- `io.py`: normalization helpers and fill matching
- `jobs.py`: job table, report files, and artifacts
- `utils.py`: timestamps and shared utility helpers

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

Legacy snapshot and canonical tables are not part of the live model. Incompatible local DBs are rebuilt to the current schema instead of being migrated in place.

## Data Flow

### Branch Mutation

1. Router receives a directory path or uploaded folder.
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

### Fill And QA

1. Router accepts a directory or uploaded folder.
2. `WorkflowService` stages input and opens a job.
3. Workflow services read workbook rows using schema-resolved columns.
4. Output reports or artifacts are written under the job directory.

### Bootstrap

1. Product routes call `ProjectStateService`.
2. `ProjectStateService` assembles the `/app` bootstrap directly.

## Architectural Rules

- Routers stay thin.
- Business rules belong in domain or workflow services.
- SQL belongs in repositories, not routers.
- New code should import explicit submodules instead of relying on package re-exports.
- Runtime APIs stay project-scoped and branch-oriented.
- Prefer reset or reseed over adding new old-data semantic compatibility behavior unless migration work is explicitly required.
