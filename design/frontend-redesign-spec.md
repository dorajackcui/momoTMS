# Frontend Redesign Spec

## Purpose

Full redesign of the Momo TMS operator frontend, grounded in the stable backend model established through Phases 1–9. The existing frontend was built incrementally alongside backend infra work; this redesign aligns the UI to the final domain model and the three core operator workflows.

## Core Operator Workflows

1. **Workspace browsing** — Excel-like grid for daily variant inspection, filterable by branch, lifecycle, key, source
2. **Branch lifecycle** — create dev branch (bootstrap) → fill/export for translation → import translated content → apply mutations → replace to release
3. **Fill / Export** — fill empty workbooks with existing translations, or export branch/project data directly

## Navigation Model

Two-level navigation:

- **Project Hub** (top level): project list, create, select
- **Project interior** (top tab bar): Workspace | Release | Dev | Runs

```
┌───────────────────────────────────────────────────────────┐
│ [← Hub] ProjectName ⓘ    Workspace │ Release │ Dev │ Runs │
├───────────────────────────────────────────────────────────┤
│  Full-width content area                                  │
└───────────────────────────────────────────────────────────┘
```

Top tabs instead of sidebar — maximizes horizontal space for grids.

Clicking logo or [← Hub] returns to Project Hub.

Project schema info (translation columns, pivot config) accessible via ⓘ icon popover next to project name.

## Project Hub

Entry point for the application. Visible when no project is selected.

### Content

- Project card list: each card shows project name, translation columns, remark columns, pivot language (if any), dev branch count
- [+ Create Project] button

### Create Project Form

- Project name
- Translation columns (language list)
- Remark columns (field list)
- Pivot language (optional) + pivoted languages
- Schema is fixed after creation — no edit capability

### API

- `GET /projects` — list projects
- `POST /projects` — create project

## Workspace Page

Daily inspection surface. Pure Excel-like grid, read-only.

### Layout

```
┌─────────────────────────────────────────────────────────────┐
│ State: [▼ Active]    ☑ Translations  ☐ Remarks  ☐ Pivot    │
├──────────────┬────────┬──────────┬────────┬─────┬───────────┤
│ business_key▼│ file  ▼│ source  ▼│ zh-Hans▼│ en ▼│ branch  ▼│
├──────────────┼────────┼──────────┼────────┼─────┼───────────┤
│ ...          │ ...    │ ...      │ ...    │ ... │ rel/c +1  │
├──────────────┴────────┴──────────┴────────┴─────┴───────────┤
│ 1,234 rows  │  Page 1 of 13  │  [◀ Prev] [Next ▶]          │
└─────────────────────────────────────────────────────────────┘
```

### Columns

Fixed columns (always visible):

| Column | Width | Description |
|--------|-------|-------------|
| business_key | 220px | Entry identifier |
| file_name | 160px | Source file reference |
| source | 260px | Source text |

Dynamic columns (controlled by column group toggles):

| Toggle | Columns added |
|--------|--------------|
| ☑ Translations (default on) | One column per language from schema.translation_columns |
| ☐ Remarks | One column per field from schema.remark_columns |
| ☐ Pivot | pivot_status column |

Trailing columns (always visible):

| Column | Description |
|--------|-------------|
| branch | Highest-authority branch binding, with +N if multiple (e.g. `rel/c +2`) |
| state | `active` / `orphan` |

### Column-Level Filtering (Excel-style)

Every column header has a built-in filter control:

- Text columns (key, file_name, source, translations): click header → expand text input, substring match
- Enum columns (branch, state, pivot_status): click header → expand dropdown selection
- Active filters show a visual indicator on the header
- Multiple column filters combine with AND logic

### Behavior

- Read-only — no write operations from Workspace
- Server-side pagination — 100 rows/page
- Column sorting — at least on business_key, source
- URL-driven — all filter state reflected in URL search params
- No drawer, no modal — all information lives in grid columns

### State Filter

State filter (Active / Orphan / All) is a toolbar-level control, not a column filter, because it changes the fundamental dataset view.

### API

- `GET /projects/{id}/variants` — with state, branch_ref, search, page params
- `GET /projects/{id}/state` — schema (column definitions), dev branches (populate branch filter)

## Release Page

Operations on `rel/current`. Release is the stable baseline — limited write operations.

### Layout

```
┌─────────────────────────────────────────────────────────────┐
│ [Tab: Browse]  [Tab: Edit]  [Tab: Trash]                    │
├─────────────────────────────────────────────────────────────┤
│  (tab content — full space for grid/forms)                  │
└─────────────────────────────────────────────────────────────┘
```

### Browse Tab

Same Excel-like grid as Workspace, scoped to rel/current entries.

- Column-level filtering (same pattern as Workspace)
- Column group toggles (Translations / Remarks / Pivot)
- Server-side pagination
- Read-only

API: `GET /branches/rel%2Fcurrent/rows`

### Edit Tab

Mutation operations on rel/current content.

```
┌─────────────────────────────────────────────────────────────┐
│ Mutation type:  ● Content (edit translations/remarks)       │
│                                                             │
│ Input method:   ○ Import batch    ● Direct                  │
│                                                             │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ (edit area — changes based on selections above)         │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ [Preview]  →  (preview result table)  →  [Execute]          │
└─────────────────────────────────────────────────────────────┘
```

- Release Edit only offers Content mutation (no Range — entries enter release via dev Replace)
- Input method: import batch or direct row editing
- Preview shows content_effect, row_outcome per row
- Authority filtering clearly marked in preview if applicable

API: `POST /branches/mutations/preview`, `POST /branches/mutations` (kind: direct or import_batch, branch_ref: rel/current)

### Trash Tab

Two separate operations:

1. **Unbind from release**: input business_keys list → remove bindings from rel/current (variant becomes orphan if no other bindings)
2. **Project trash**: target orphan variants → permanent trash (irreversible)

Each operation has its own preview → execute flow. Project trash shows a strong warning about irreversibility.

API: `POST /variants/trash/delete` (unbind), `POST /variants/trash` (project trash)

## Dev Page

Full dev branch lifecycle. The most complex page — two-layer structure.

### Layer 1: Branch List (default view)

```
┌─────────────────────────────────────────────────────────────┐
│ [+ Create Branch]                       [Import Batches ▶]  │
├──────────┬─────────────┬──────────┬─────────────────────────┤
│ Branch   │ Status      │ Entries  │ Actions                 │
├──────────┼─────────────┼──────────┼─────────────────────────┤
│ dev/2.2.3│ bootstrapped│ 1,204    │ [Open]                  │
│ dev/2.2.2│ bootstrapped│ 1,180    │ [Open]                  │
│ dev/2.2.1│ bootstrapped│ 1,150    │ [Open]                  │
└──────────┴─────────────┴──────────┴─────────────────────────┘
```

- All dev branches listed by version descending
- Each row: branch name, bootstrap status, entry count
- [+ Create Branch] → enters Create Branch flow
- [Import Batches] → import batch history
- [Open] → enters Layer 2: Branch Detail

### Create Branch Flow

Stepped flow within the page:

```
Step 1: Upload        Step 2: Preview       Step 3: Done
────●──────────────────────○──────────────────────○────
```

**Step 1: Upload & Configure**

- Enter version number (e.g. `2.2.3`, system prepends `dev/`)
- Upload workbook folder (key + source table)
- Column mapping confirmation (business_key, source, optional translations/remarks)
- [Next: Preview]

**Step 2: Preview**

- Call `POST /imports/upload-folder/preview` to confirm mapping
- Confirm → create import batch
- Call `POST /branches/bootstrap/preview` to show:
  - Rows that will bind existing variants (BOUND_EXISTING_VARIANT)
  - Rows that will create new variants (CREATED_AND_BOUND_VARIANT)
  - Invalid rows, duplicate keys
- [Execute Bootstrap]

**Step 3: Done**

- Bootstrap job completes → show result summary
- **[Export for Translation]** button — triggers fill: matches key+source from the same workbook against project-wide existing translations, exports filled workbook ZIP
- Fill job completes → download link
- **[Go to Branch]** — enters Branch Detail

API: `POST /imports/upload-folder/preview`, `POST /imports/upload-folder`, `POST /branches/bootstrap/preview`, `POST /branches/bootstrap`, `POST /fill/upload-folder`

### Layer 2: Branch Detail

Entered via [Open] from branch list or [Go to Branch] after creation.

```
┌─────────────────────────────────────────────────────────────┐
│ [← Back to list]   dev/2.2.3                                │
├─────────────────────────────────────────────────────────────┤
│ [Tab: Browse]  [Tab: Edit]  [Tab: Replace]  [Tab: Trash]    │
├─────────────────────────────────────────────────────────────┤
│  (tab content)                                              │
└─────────────────────────────────────────────────────────────┘
```

**Browse Tab**

Same Excel-like grid, scoped to this dev branch. Column-level filtering, column group toggles, pagination. Read-only.

API: `GET /branches/dev%2F{version}/rows`

**Edit Tab**

Mutation operations on this dev branch.

```
┌─────────────────────────────────────────────────────────────┐
│ Mutation type:  ○ Range (add/remove entries)                │
│                 ● Content (edit translations/remarks)        │
│                                                             │
│ Input method:   ○ Import batch    ● Direct                  │
│                                                             │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ (edit area — changes based on selections above)         │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ [Preview]  →  (preview result table)  →  [Execute]          │
└─────────────────────────────────────────────────────────────┘
```

- Both Range and Content mutation types available
- Input method: import batch or direct
- Preview shows mutation_class, binding_effect, content_effect, row_outcome per row
- Authority filtering clearly marked (content_filtered_by_authority)

API: `POST /branches/mutations/preview`, `POST /branches/mutations`

**Replace Tab**

Sync this dev branch to rel/current.

- Preview: binding-change semantics per entry (ADD_TO_TARGET, KEEP_IN_TARGET, REBIND_TARGET, REMOVE_FROM_TARGET)
- [Execute Replace] → confirm → run
- Source branch stays unchanged; only target (rel/current) is rewritten

API: `POST /branches/replace/preview`, `POST /branches/replace/execute`

**Trash Tab**

Unbind entries from this dev branch.

- Input business_keys → preview → execute
- Variant becomes orphan if no other bindings remain

API: `POST /variants/trash/delete` (branch_ref: dev/{version})

### Import Batches View

Accessed via [Import Batches] from branch list.

- All import batches: ID, created time, row count, status
- Click to view batch report (first N rows preview + issue stats)
- Each batch shows whether it has been consumed by a bootstrap
- [← Back to list] returns to branch list

API: `GET /imports`, `GET /imports/{id}/report`

## Runs Page

Unified async job tracking plus independent Fill, QA, and Export triggers.

### Layout

```
┌─────────────────────────────────────────────────────────────┐
│ [Tab: Jobs]  [Tab: Fill]  [Tab: QA]  [Tab: Export]          │
├─────────────────────────────────────────────────────────────┤
│  (tab content)                                              │
└─────────────────────────────────────────────────────────────┘
```

### Jobs Tab

All async jobs in reverse chronological order.

- Each row: job ID, type, status (running/success/failed), created time
- Running jobs poll at 1s interval
- Click job → expand detail: execution stages, summary counters, report preview (first N rows)
- Artifact download links (ZIP, report CSV)
- Job types: bootstrap, mutation, replace, trash, fill, QA, export, pivot_review

API: `GET /jobs`, `GET /jobs/{id}`, `GET /jobs/{id}/report`, `GET /jobs/{id}/artifact/{name}`

### Fill Tab

Independent fill trigger (not tied to branch creation).

- Upload workbook folder (key + source + empty translation columns)
- Select target language (lang)
- Execute → match all project non-trashed variants → fill translations → export ZIP
- Job submitted → auto-switch to Jobs tab to track progress

API: `POST /fill/upload-folder`

### QA Tab

Quality assurance scan.

- Upload workbook folder
- Select target language (lang)
- Execute → validate source and target content → generate issue report
- Job submitted → auto-switch to Jobs tab

API: `POST /qa/upload-folder`

### Export Tab

Direct variant export.

- Select export scope:
  - **Branch**: dropdown (rel/current / dev/X.Y.Z / orphan) → export all entries from that branch
  - **Project**: export all non-trashed variants project-wide
- Select languages to include (multi-select or all)
- Execute → generate workbook ZIP
- Job submitted → auto-switch to Jobs tab

API: new endpoint needed — `POST /export` or similar (backend does not currently have a dedicated export endpoint; this is a new capability)

## Technical Notes

### Shared Grid Component

Workspace, Release Browse, and Dev Branch Browse all use the same grid pattern:

- Excel-style column-level filtering
- Column group toggles (Translations / Remarks / Pivot)
- Server-side pagination (100 rows/page)
- Column sorting
- URL-driven filter state

This should be a shared component with scope/branch as a parameter.

### Shared Edit Component

Release Edit and Dev Branch Edit share the same structure:

- Mutation type selector (Release: Content only; Dev: Range + Content)
- Input method selector (Import batch / Direct)
- Edit area
- Preview → Execute flow

This should be a shared component with branch_ref and allowed mutation types as parameters.

### URL State Management

All filter state, tab selection, and navigation state reflected in URL search params. Supports bookmarking and browser back/forward.

### Tech Stack

Carry forward from current frontend:

- React 19 + React Router 6
- TanStack React Query 5 (server state)
- Vite (build)
- TypeScript (strict)
- CSS Modules
- react-data-grid (grid component — evaluate if it supports column-level filtering, or if a custom solution is needed)

### New Backend Requirement

The Export feature requires a new backend endpoint. All other features map to existing APIs.
