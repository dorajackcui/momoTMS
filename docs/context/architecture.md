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

- `pages.py`: `/app`, removed `/workbench` tombstone (`410`), `/variant-workbench`
- `projects_state.py`: project bootstrap, project create, demo reset, compatibility string endpoints
- `imports_jobs.py`: import batch APIs, upload preview, jobs, reports, artifacts
- `scopes_read_models.py`: branch summary, compare, queue, master query
- `workflows.py`: dev import, hotfix, promote, fill, QA, trash/restore
- `inspection.py`: read-only entry-variant, retained-variant, and orphan-variant inspection

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
- `services.py`: entry, variant catalog, lifecycle, and scope binding services
- `records.py`: typed record shapes
- `inspection.py`: project-scoped lifecycle inspection assembly
- `compatibility.py`: old string-shaped compatibility layer
- `facade.py`: compatibility facade that wires split services together

### `app/services/read_models/`

Projection services for product-facing reads.

- branch summary
- branch compare
- translation queue
- master query
- repository-first scope projection, then page-sized hydration

### `app/services/workflows/`

Workflow services and orchestration.

- `dev_versions.py`: dev-version metadata and dev import
- `rel.py`: release summary and hotfix
- `promote.py`: promote preview and execution
- `fill.py`: fill artifact generation
- `qa.py`: QA scan/report
- `trash.py`: scope-aware delete and variant-aware restore
- `workbench.py`: compatibility bootstrap plus job-oriented orchestration used by routers

### `app/services/shared/`

Cross-cutting helpers.

- `io.py`: normalization helpers and fill matching
- `jobs.py`: job table, report files, artifacts
- `utils.py`: timestamps and utility helpers

### `app/services/demo/`

Demo data seeding and sample workbook generation.

## Database Tables

Current schema version: `variant-v3`.

Main tables:

- `projects`
- `project_schemas`
- `entries`
- `variants`
- `variant_translations`
- `variant_remarks`
- `scope_bindings`
- `retained_variants`
- `dev_versions`
- `imports`
- `import_rows`
- `jobs`

Legacy snapshot/canonical tables are dropped during schema rebuild and are no longer part of the live model.

## Data Flow

### Import to Dev Scope

1. Router receives directory path or uploaded folder.
2. `WorkbenchService` creates a job and stages files when needed.
3. `ImportService` parses workbooks and writes `imports` plus `import_rows`.
4. `DevVersionService` consumes the import batch.
5. Entry, variant, and binding services create/update variants and scope bindings.
6. Job report is written to disk and indexed in `jobs`.

### Read Models

1. Router parses scope refs and filters.
2. Repository helpers load lightweight scope projections and active-binding search results.
3. `ReadModelService` computes compare state, diff categories, and priority status from projection metadata.
4. Only the current page of business keys is hydrated into full row payloads.

### Fill / QA

1. Router accepts a directory or uploaded folder.
2. `WorkbenchService` stages input and opens a job.
3. Workflow service reads workbook rows using schema-resolved columns.
4. Output report or artifact is written under the job directory.

### Bootstrap

1. Product routes use `ProjectStateService`.
2. Compatibility state for `/variant-workbench` and frozen default-project flows stays in `WorkbenchService`.
3. Compatibility bootstrap includes demo samples and trash count; product bootstrap does not.

## Architectural Rules

- Routers should stay thin.
- Business rules belong in domain or workflow services.
- SQL belongs in repositories, not routers.
- New code should import explicit submodules instead of relying on package re-exports.
- Prefer project-scoped APIs and services over default-project compatibility routes.
- Lifecycle inspection source of truth is `app/routers/inspection.py` plus `app/services/variant/inspection.py`.
