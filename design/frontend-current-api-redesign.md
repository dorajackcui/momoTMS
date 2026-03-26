# Frontend Redesign For Current APIs

## Status

- this note is the earlier six-surface IA baseline
- the proposed merge of `Variants` into `Overview` is tracked separately in [overview-variant-workspace-redesign.md](overview-variant-workspace-redesign.md)
- if that proposal is accepted, the `Overview`, `Variants`, nav, and default-flow sections in this note should be treated as superseded
- the backend now ships `GET /api/projects/{project_id}/variants` for project-scoped `active + orphan` workspace rows, so any older gap analysis below should be read as historical context unless updated

## Purpose

- redesign the `/app` product UI around the current project-scoped APIs only
- stop carrying forward the current page split when it no longer matches the operator task flow
- define a cleaner information architecture without preserving old frontend compatibility

## Scope

- this note only covers frontend IA, page responsibilities, data sources, and interaction design
- it does not change backend contracts
- it does not introduce undo, audit, or new query endpoints

## Design Goals

- make the default experience project-first instead of page-first
- make the main surface a spreadsheet-like branch view rather than a set of disconnected tables
- group read, execution, and inspection tasks by operator intent
- expose current API boundaries honestly instead of faking missing backend capabilities

## Current API Reality

The current backend already supports:

- project list and project bootstrap
- a paginated project-scoped variants workspace query for `active + orphan` rows
- branch summary, branch compare, branch queue, and master lookup
- dev branch detail
- import preview, import apply, jobs, reports, and artifacts
- branch mutation, replace preview or execute, trash delete or restore, fill, and QA
- entry-level variant inspection and orphan variant listing

The current backend does **not** provide:

- one direct `rel/current` detail endpoint equivalent to `GET /branches/dev/{version}`
- one dedicated trashed-variant list endpoint
- one unified all-state search endpoint across active, orphan, and trashed variants
- undo or cancel semantics for executed jobs

These limits matter. The redesign should lean into branch-scoped active views, drill-down inspection, and job-backed actions instead of pretending we already have a global variant explorer API.

## Proposed Navigation

Replace the current nav with six top-level destinations:

- `Overview`
- `Intake`
- `Branch Ops`
- `Runs`
- `Variants`
- `Project`

This is intentionally less contract-shaped than the current `Compare`, `Queue`, `Master`, `Imports`, and `Inspection` split. The new layout is organized by operator jobs.

## Page Map

### 1. Overview

Primary goal:

- show a spreadsheet-like slice of project variants for one selected branch

Route:

- `/app/overview`

Primary APIs:

- `GET /api/projects/{project_id}/state`
- `GET /api/projects/{project_id}/branches?lang=...`
- `GET /api/projects/{project_id}/branches/dev/{version}`
- `GET /api/projects/{project_id}/entries/{business_key}/variants`

Secondary API:

- `GET /api/projects/{project_id}/branches/compare`

Core layout:

- top project bar: project switcher, language switcher, refresh
- filter bar: branch, search key, source text, lifecycle toggle, column preset
- main canvas: spreadsheet-like grid with frozen columns
- right drawer: selected row detail, bindings, translations, remarks, lifecycle

Grid columns:

- `business_key`
- `file_name`
- `source`
- active translation columns from schema
- remark columns from schema
- status summary
- branch badge

Branch filter behavior:

- default to `candidate_dev_branch` when present
- otherwise default to the first active dev branch
- `dev/*` branch selection uses `GET /branches/dev/{version}` as the main row source
- `rel/current` selection falls back to a summary mode because the current API does not expose a rel detail endpoint

`rel/current` summary mode:

- show branch-level counts from `GET /branches`
- show compare-derived row samples against the selected dev branch from `GET /branches/compare`
- keep the same spreadsheet shell, but label it clearly as `sampled active rows`, not a full rel export

Spreadsheet design:

- virtualized rows only; never render the full branch payload into plain DOM tables
- frozen first three columns
- horizontal scroll for translation and remark columns
- column visibility presets: `Core`, `Translation`, `Review`
- row click opens the right drawer and loads full variant history from `GET /entries/{business_key}/variants`

Why this page exists:

- operators need one place to scan a branch as if it were a workbook
- the current frontend starts from summaries and tools, but not from the actual data plane

### 2. Intake

Primary goal:

- handle project data intake from upload preview to import apply

Route:

- `/app/intake`

Primary APIs:

- `POST /api/projects/{project_id}/imports/upload-folder/preview`
- `POST /api/projects/{project_id}/imports/upload-folder`
- `GET /api/projects/{project_id}/imports`
- `GET /api/projects/{project_id}/imports/{import_batch_id}/report`

Core layout:

- left panel: recent import batches
- center panel: upload zone and mapping wizard state
- bottom panel: selected import report

Sections:

- `Upload`: folder picker and schema reminder
- `Mapping`: sheet-by-sheet field mapping summary and issue list
- `Apply`: confirm upload session into import batch
- `History`: recent batches with report preview

Design notes:

- this page should stop owning downstream branch execution
- after an import batch is created, the primary CTA is `Send to Branch Ops`

### 3. Branch Ops

Primary goal:

- centralize all branch-oriented read and write operations

Route:

- `/app/branches`

Primary APIs:

- `GET /api/projects/{project_id}/branches`
- `GET /api/projects/{project_id}/branches/compare`
- `GET /api/projects/{project_id}/branches/queue`
- `GET /api/projects/{project_id}/branches/master/entries/{business_key}`
- `GET /api/projects/{project_id}/branches/master/search`
- `POST /api/projects/{project_id}/branches/mutations`
- `POST /api/projects/{project_id}/branches/replace/preview`
- `POST /api/projects/{project_id}/branches/replace/execute`
- `POST /api/projects/{project_id}/variants/trash/delete`
- `POST /api/projects/{project_id}/variants/trash/restore`

Internal tabs:

- `Compare`
- `Queue`
- `Lookup`
- `Apply`
- `Replace`
- `Trash / Restore`

#### Compare tab

- keep the current compare table capability
- add sticky filter chips for branch pair, state, priority status, and diff category
- add row action `Inspect Variant History`

#### Queue tab

- keep queue as a focused worklist
- add clearer status segmentation: `needs translation`, `needs review`, `fillable`, `source mismatch`
- allow click-through from queue row to overview drawer and variant drawer

#### Lookup tab

- absorb the current master query page
- support key lookup and exact-source lookup in one compact panel
- results open in drawer rather than switching pages

#### Apply tab

- run direct mutation and import-batch mutation from one form
- branch selector first
- mode switch: `Import Batch` or `Direct Patch`
- direct patch uses a grid-like mini editor for a few selected keys, not a raw JSON editor

#### Replace tab

- dedicated preview-first workflow
- top area shows source branch, target branch, and preview CTA
- preview result uses a compact KPI row plus sampled report table
- execute CTA stays visually isolated and only appears after preview succeeds

#### Trash / Restore tab

- delete by branch plus business keys
- restore by inspected `variant_id`
- current APIs do not offer a global trash inbox, so restore entry starts from search or inspection results

### 4. Runs

Primary goal:

- unify all job-backed execution feedback in one place

Route:

- `/app/runs`

Primary APIs:

- `GET /api/projects/{project_id}/state`
- `GET /api/projects/{project_id}/jobs`
- `GET /api/projects/{project_id}/jobs/{job_id}`
- `GET /api/projects/{project_id}/jobs/{job_id}/report`
- `GET /api/projects/{project_id}/jobs/{job_id}/artifact/{name}`

Core layout:

- left rail: jobs grouped by status and job type
- center: selected job detail
- right rail: report preview and downloads

Design notes:

- remove jobs from the Intake page as a primary concept
- every page that kicks off a job should deep-link here after success
- job detail should always show input, summary, stages, report preview, and artifact download if available

### 5. Variants

Primary goal:

- provide read-heavy entry and variant inspection without mixing it into workflow pages

Route:

- `/app/variants`

Primary APIs:

- `GET /api/projects/{project_id}/entries/{business_key}/variants`
- `GET /api/projects/{project_id}/orphan-variants`
- `POST /api/projects/{project_id}/variants/trash/restore`

Core layout:

- left panel: orphan variants list
- top search: business key lookup
- center: timeline cards for all variants under one entry
- right drawer: bindings, translations, remarks, lifecycle timestamps

Design notes:

- this page replaces the current inspection/debug tone with a clearer `Variant Explorer`
- restore actions belong here because restore depends on known `variant_id`

### 6. Project

Primary goal:

- keep project bootstrap, schema, branch summary, and project creation in one settings-like page

Route:

- `/app/project`

Primary APIs:

- `GET /api/projects`
- `POST /api/projects`
- `GET /api/projects/{project_id}/state`

Core layout:

- top: project switcher
- left: schema and language config summary
- center: release summary, candidate dev branch, dev branch list
- bottom: create project form

Design notes:

- remove the standalone `New Project` nav item
- create-project is a mode inside the Project page and the empty state entrypoint

## Recommended Default Flow

The happy-path operator flow should become:

1. open `Overview` and pick a working branch
2. scan rows in spreadsheet mode
3. go to `Intake` to upload and create import batches
4. go to `Branch Ops` to apply import batch, compare, preview replace, or run branch actions
5. land in `Runs` to inspect long-running job outputs
6. use `Variants` only when a row needs history, orphan, or restore inspection

This is clearer than today because it separates:

- data scanning
- ingestion
- branch decisions
- async execution feedback
- deep inspection

## URL Strategy

Proposed stable routes:

- `/app/overview`
- `/app/intake`
- `/app/branches`
- `/app/runs`
- `/app/variants`
- `/app/project`

Suggested optional query params:

- `project`
- `lang`
- `branch`
- `tab`
- `job`
- `business_key`

This keeps state sharable without recreating the current page explosion.

## Component Strategy

Use a real virtualized data-grid implementation for `Overview` and the `Apply` tab mini-editor.

Requirements for the grid layer:

- row virtualization
- frozen columns
- keyboard navigation
- dynamic column definitions from schema
- custom cell renderers for state badges and lifecycle hints

Avoid building spreadsheet behavior from plain HTML tables.

## Known Gaps And Honest UI Constraints

- `Overview` cannot provide a true full-fidelity `rel/current` spreadsheet until the backend exposes a rel branch detail endpoint or a project-wide active variant query
- `Trash / Restore` cannot show a complete trash inbox with the current APIs
- `Runs` can inspect jobs but cannot cancel or undo them
- `Lookup` remains exact-match oriented because there is no fuzzy global variant search endpoint

These gaps should be called out in UI copy instead of hidden.

## Implementation Order

1. replace navigation shell and route map
2. build `Overview` as the new landing page
3. split `Imports & Jobs` into `Intake` and `Runs`
4. merge `Compare`, `Queue`, `Master`, and workflow actions into `Branch Ops`
5. rename and restyle `Inspection` into `Variants`
6. fold project creation into `Project`

## Why This Is Better Than The Current Frontend

- the current app mirrors backend route groups too closely
- the new design starts from operator tasks and current data shapes
- the main page becomes the data surface rather than a branch summary card wall
- async workflows get one dedicated place instead of being scattered through import-oriented UI
- inspection remains available without dominating the main operator path
