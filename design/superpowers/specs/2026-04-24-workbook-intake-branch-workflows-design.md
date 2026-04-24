# Workbook Intake Branch Workflows Design

## Purpose

Redesign upload-driven write workflows so operators use one workbook-based path for create branch, branch mutation, and trash actions. The design keeps upload transport, workbook parsing, and workflow application separate so future import methods can change without rewriting branch business logic.

## Goals

- Use workflow-specific workbook uploads for create branch, branch edit, and trash.
- Remove product-facing `Direct` and `Import batch` input choices from branch write UI.
- Define project-level workbook headers at project creation.
- Support large workbooks around 200,000 rows without rendering or buffering full row sets in the UI.
- Keep upload transport and workbook parsing independently extensible.
- Preserve branch workflow semantics: bootstrap, content mutation, range mutation, branch delete, and project trash.

## Non-Goals

- Do not support mixed action rows in one workbook.
- Do not add schema editing after project creation.
- Do not keep old local database compatibility as a design target.
- Do not run a full workflow effect preview before execute for large workbook paths.

## Project Workbook Contract

Project creation defines the workbook business headers:

- `business_key_header`: the exact workbook header used for internal `business_key`, for example `key`.
- `source_header`: the exact workbook header used for internal `source`, for example `source`.

Translation columns and remark columns stay as they work today: the project schema column name is the workbook header. There is no separate alias list for translation or remark columns.

Header matching is exact after non-content normalization, matching the current trim behavior. There is no case folding and no alternate header aliases in this design.

Workflow required columns:

- Create branch requires `business_key_header + source_header`.
- Branch content mutation requires `business_key_header + source_header`.
- Branch range mutation requires `business_key_header + source_header`.
- Branch trash and project trash require `business_key_header` only.

## Service Boundaries

`Upload Transport`

- Owns how files enter the runtime.
- Current transport may accept browser multipart workbook files or workbook folders.
- Future transports may include zip upload, local directory, cloud file, or prior job artifact.
- Output is a staged workbook input reference.
- It does not parse workbook business fields.

`Workbook Parser`

- Owns workbook reading and row extraction.
- Reads staged workbook input using project workbook contract.
- Produces normalized row payloads and input issues.
- Supports chunked or streaming reads for large files.
- Does not know which workflow will consume the rows.

`Workbook Intake`

- Orchestrates transport plus parser.
- Provides lightweight precheck before execution.
- During execute jobs, persists workflow-neutral batch rows for downstream consumers.
- May initially reuse existing `imports` and `import_rows` tables internally, but public naming and service ownership should move toward `workbook_batch`.

`Workflow Consumers`

- Consume normalized workbook rows or a workbook batch reader.
- Do not care whether the input came from multipart upload, folder upload, local directory, or another future transport.
- Preserve existing branch, variant, binding, authority, and trash semantics.

Boundary summary:

```text
Upload Transport -> Staged Workbook Input
Workbook Parser  -> Parsed Rows + Header/Row Issues
Workbook Intake  -> Persisted Workbook Batch / Row Stream
Workflow Service -> Execute Job + Report
```

## Large Workbook Flow

The primary operator flow is intentionally simple:

```text
Upload workbook
-> lightweight precheck
-> execute one async workflow job
-> job summary + report preview + full report access
```

There is no complete workflow effect preview job before execute. A full preview for 200,000 rows would duplicate much of the execution cost.

Lightweight precheck includes:

- file readability
- sheet and header discovery
- workflow required-column validation
- limited sample row validation
- file, sheet, and sampled issue counts

Precheck does not return all row payloads and does not render a large row table.

Execution jobs should stream or chunk parsing and persistence. Existing chunk sizes such as 1,000-row inserts are acceptable starting points. Job reports should remain summary-first with a bounded report preview; full reports should be available through report endpoints or artifacts.

Job stages should expose coarse progress states such as:

- `parsing_workbook`
- `persisting_workbook_batch`
- `applying_workflow`
- `writing_report`

## Workflow Semantics

### Create Branch

Create branch uses a workbook upload to establish the initial range for `dev/<version>`.

Required columns:

- configured key header
- configured source header

Execution:

- parse workbook rows
- persist workbook batch rows
- bootstrap the dev branch from those rows
- reuse existing same-source canonical variants when available
- create and bind variants when no same-source canonical variant exists
- reject duplicate keys within the bootstrap batch using existing bootstrap semantics

The job is async and returns summary plus report preview.

### Branch Content Mutation

Branch content mutation is available in Dev branch edit and Release edit.

Required columns:

- configured key header
- configured source header

Content mutation never performs variant resolution, creation, bind, or rebind. It only updates content on the currently bound variant when the row matches that exact branch-visible variant.

Per-row behavior:

```text
key + source
-> find current branch binding for key
-> compare currently bound variant.source with workbook source
-> if equal, check authority and update translations or remarks
-> if missing or mismatched, skip and report
```

Expected report outcomes include:

- `UPDATED_BOUND_VARIANT`
- `NOOP`
- `MISSING_IN_SCOPE`
- `SOURCE_MISMATCH`
- `INVALID_ROW`
- authority-filtered content outcome

The legacy direct-input behavior where source may be omitted is not part of the workbook workflow contract.

### Branch Range Mutation

Branch range mutation is available in Dev branch edit and Release edit, subject to branch policy.

Required columns:

- configured key header
- configured source header

Range mutation may:

- resolve an existing same-source canonical variant
- create a new variant when policy allows
- bind or rebind the branch to the target variant
- apply sparse translation or remark payloads when authority allows

Release and Dev use the same product panel, but backend policy continues to decide whether a row can create missing entries or mutate authority-protected content.

### Branch Trash

Branch trash is a branch-scoped unbind from workbook keys.

Required columns:

- configured key header

Execution reads keys from workbook rows and applies branch delete semantics:

- remove the active binding in the selected branch
- orphan the variant when the last binding is removed
- report missing or not-bound keys

### Project Trash

Project trash is a project-scoped orphan trash from workbook keys.

Required columns:

- configured key header

Execution reads keys from workbook rows and applies project trash semantics:

- trash orphan variants only
- skip active variants
- keep trashed terminal

## API Shape

The new product-facing API should avoid exposing `import_batch` as an operator input method.

Workbook intake endpoints:

```text
POST /api/projects/{project_id}/workbooks/intake/preview
POST /api/projects/{project_id}/workbooks/intake/execute
GET  /api/projects/{project_id}/workbook-batches
GET  /api/projects/{project_id}/workbook-batches/{batch_id}/report
```

`preview` accepts staged upload input and workflow context, then returns lightweight precheck data.

`execute` starts one async job that performs intake plus target workflow. The request includes workflow context such as:

- `workflow_kind`
- `branch_ref` when branch-scoped
- `mutation_type` for branch edit
- `version` or `branch_ref` for create branch

Existing workflow routes may remain as internal or transitional adapters during migration, but the new frontend should call workbook workflow APIs.

## Frontend Design

Create a reusable workbook workflow panel shared by create branch, branch edit, and trash flows.

Common UI states:

- configure workflow target
- choose mutation type where needed
- upload workbook
- show lightweight precheck
- execute async job
- show job status, summary, report preview, and full report access

Page behavior:

- `Dev -> Create Branch`: enter version, upload workbook, execute create branch.
- `Dev branch detail -> Edit`: choose content or range mutation, upload workbook, execute mutation.
- `Release -> Edit`: choose content or range mutation, upload workbook, execute mutation.
- Branch trash: upload key-only workbook, execute branch delete.
- Project trash: upload key-only workbook, execute project trash.
- `Runs` remains the job history and report surface.

The frontend should no longer show:

- `Input method`
- `Direct`
- TSV textarea
- `Import batch` selector
- unbounded row preview tables

## Cleanup Plan

Remove or demote these product-facing paths:

- Direct TSV input in branch edit UI.
- Import batch selection as a branch mutation input method.
- Create branch page-specific upload/import orchestration.
- Product docs that present `Import batch` as the operator input method.
- Legacy direct workbook semantics where content mutation can omit source.

Backend cleanup should be staged:

- Introduce workbook intake services and request models first.
- Point new frontend flows at workbook workflow APIs.
- Move branch services from `ImportService` dependency toward a neutral workbook batch reader.
- Keep old import routes only as transitional compatibility until tests and docs no longer depend on them.
- Remove or tombstone old public routes once the new contract is stable.

## Testing Strategy

Backend tests:

- project creation stores exact key/source workbook headers
- parser maps configured key/source headers to internal `business_key/source`
- create branch workbook job handles duplicate keys, invalid rows, and same-source reuse
- content mutation requires key+source and never binds, rebinds, creates, or changes range
- range mutation preserves existing policy behavior
- trash workbook requires key only
- large workbook tests verify chunked persistence and bounded report preview

Frontend tests:

- create branch uses workbook upload and job polling
- Dev edit and Release edit require mutation type selection
- content and range mutation pass the selected type to backend
- trash upload accepts key-only workbook contract
- Direct and Import batch choices are absent

Docs checks:

- update `docs/contracts.md` and `docs/workflows.md` when implementation changes public routes or workflow behavior
- run `scripts/validate_docs.py` after docs and route changes

## Implementation Decisions

- The first backend implementation should reuse `imports/import_rows` internally behind a neutral `WorkbookBatchReader`. New database table names can follow after the service boundary is proven.
- Single workbook upload and folder upload should share the same transport abstraction. The first API can keep the existing multipart shape with `files` and `relative_paths`; selecting a single workbook simply produces one relative path.
- Content mutation source mismatches should report `SOURCE_MISMATCH`.
