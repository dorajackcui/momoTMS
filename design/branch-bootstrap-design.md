# Phase 3 Branch Bootstrap Design

## Status

- proposed
- approved in design discussion on 2026-04-20

## Purpose

- define Phase 3 as a dedicated branch bootstrap workflow
- establish how a new `dev/<version>` branch gets its initial working surface
- keep bootstrap separate from the later general mutation contract

## Scope

This design defines:

- the semantic role of `bootstrap`
- allowed bootstrap inputs
- bootstrap execution rules
- bootstrap status and reporting shape
- performance constraints for large bootstrap batches
- minimal branch metadata needed to reflect bootstrap state

This design does not define:

- the full Phase 4 mutation taxonomy
- the final preview family for bootstrap and mutation flows
- branch-to-branch replace or promote semantics
- pivot preview or review behavior
- broad branch management metadata such as owner, note, or lock state

## Problem Statement

Phase 1 and Phase 2 clarified the core model and authority behavior, but branch creation is still implicit in ordinary mutation flows. That is not enough for the real Phase 3 workload:

- operators may create a new `dev/<version>` branch by uploading a branch-wide workbook
- the workbook may contain only `business_key + source`
- the workbook may also contain `business_key + source` plus one or more translation columns
- the workbook can be very large, up to roughly `200000` rows
- most rows may already match variants that exist in the project and only need a new branch binding

That workload is not just “ordinary import mutation on an empty branch.” It is a separate workflow that establishes a branch's initial range and must optimize for bind-heavy batch execution.

## Core Decision

Phase 3 introduces a dedicated `bootstrap` workflow for dev branches.

`bootstrap` is:

- branch-wide
- import-batch based
- asynchronous and job-backed
- used only to establish the initial range of a not-yet-bootstrapped `dev/<version>` branch

`bootstrap` is not:

- a synonym for ordinary `import_batch` mutation
- a generic content-edit workflow
- a repeatable “replace branch range” action for already initialized branches

After a branch has been bootstrapped once, later work must move into the later mutation model instead of reusing bootstrap.

## Input Semantics

Bootstrap input is a branch-wide uploaded workbook that resolves to a persisted import batch.

Required row fields:

- `business_key`
- `source`

Allowed optional row fields:

- any configured translation columns
- any configured remark columns

Two bootstrap input shapes are valid:

1. `business_key + source`
2. `business_key + source + partial content columns`

Both are bootstrap. The second form does not become “post-bootstrap mutation”; it is still an initial branch-establishment upload.

## Initial Range Semantics

The first successful bootstrap upload defines the branch's initial range.

Rules:

- only keys present in the bootstrap upload become part of the branch's initial range
- the branch does not implicitly inherit keys or bindings from any baseline branch
- a bootstrap upload is therefore a branch-range establishment action, not a patch against inherited bindings

Implication:

- a newly created `dev/<version>` branch starts empty
- bootstrap is the first action that gives it active bindings

## Row Resolution Model

Operator-facing bootstrap semantics are expressed in terms of `business_key + source`.

Internal resolution remains aligned to the existing domain model:

1. resolve or create the `entry` for `business_key`
2. within that entry, resolve the live same-source `variant` for `source`
3. bind the branch to that variant, or create and bind a new variant if none exists

This keeps the external contract simple without changing the current `entry` plus per-entry `variant(source)` model.

## Row Execution Rules

Each bootstrap row follows one of two primary paths.

### Path A: Existing Same-Source Variant Exists

If the project already has a live non-trashed variant for the same `business_key + source`:

- bootstrap reuses that variant
- bootstrap binds the target dev branch to that variant
- bootstrap does not compare uploaded content against the existing variant content
- bootstrap does not treat uploaded translations or remarks as an in-place edit on that shared variant
- row status is `BOUND_EXISTING_VARIANT`

This is true even when the uploaded row includes content columns that differ from the existing variant.

### Path B: No Same-Source Variant Exists

If no live non-trashed variant exists for that `business_key + source`:

- bootstrap creates a new variant under the resolved entry
- `source` comes from the upload row
- provided translations and remarks are written to the new variant
- omitted translation and remark fields initialize as empty values
- bootstrap binds the target dev branch to the new variant
- row status is `CREATED_AND_BOUND_VARIANT`

## Relationship To Authority

Phase 2 authority protects in-place edits on shared `translations + remarks`.

Bootstrap intentionally avoids becoming that kind of workflow:

- when bootstrap hits an existing same-source variant, it only binds
- when bootstrap misses, it creates a new variant and binds
- bootstrap therefore does not perform the shared-variant in-place content edit that Phase 2 authority governs

Design consequence:

- bootstrap does not run shared-content authority filtering for rows that bind an existing same-source variant
- uploaded content on reuse-hit rows is ignored rather than evaluated as an edit request

## Branch State Model

Phase 3 introduces a minimal lifecycle distinction for dev branches:

- `not_bootstrapped`
- `bootstrapped`

Rules:

- a dev branch starts as `not_bootstrapped`
- the first successful bootstrap transitions it to `bootstrapped`
- a `bootstrapped` branch cannot run bootstrap again
- later changes to range or content must use later mutation workflows

This state should be reflected in branch metadata and bootstrap-related reads, but Phase 3 does not add broader branch management fields.

## Performance Constraints

Bootstrap must be designed for very large batches, including workloads around `200000` rows where most rows resolve to existing project variants.

The dominant expected success path is:

- resolve row
- hit existing same-source variant
- bind branch to that variant

Because of that, bootstrap is explicitly a bind-heavy, batch-oriented workflow.

Required implementation characteristics:

- job-backed asynchronous execution
- chunked import-row reading
- batch entry lookup or creation
- batch variant loading for touched entries
- in-memory `(business_key, source) -> variant` indexing per loaded chunk or preloaded working set
- optimization for `bind existing` instead of optimization for content comparison
- no per-row content diff for reuse-hit rows
- no per-row authority content evaluation for reuse-hit rows
- no per-row orphan refresh when rows are only adding bindings
- chunk-level or touched-entry-set refresh for derived lifecycle maintenance
- streaming or chunked report generation so the runtime does not hold an oversized report payload in memory unnecessarily

This keeps Phase 3 aligned to the actual workload: adding a large number of branch bindings is materially cheaper than cloning the same number of variants, but it is still large enough to require dedicated batch design.

## Validation And Error Boundaries

Bootstrap validation should stay focused on initial-range establishment.

### Request-Level Rejection

Reject the request when:

- `branch_ref` is not `dev/<version>`
- the target branch is already `bootstrapped`
- the import batch does not belong to the project
- the request cannot resolve to a valid bootstrap job input

### Row-Level Validation

Row-level invalid conditions:

- blank `business_key`
- blank `source`
- other input-shape errors that make the row unusable for bootstrap

Row-level invalid status:

- `INVALID_ROW`

### Batch-Level Key Rule

Within one bootstrap upload:

- `business_key` must be unique
- the same key may not appear in multiple rows, regardless of source

Reason:

- bootstrap defines the branch's initial current range
- one branch may have only one current active binding per key

Recommended row status for this condition:

- `DUPLICATE_KEY_IN_BOOTSTRAP`

### Explicit Non-Errors

The following are intentionally not bootstrap errors:

- uploaded content differs from an existing same-source variant
- a reuse-hit row includes translations or remarks that are ignored
- a row binds to a shared existing variant instead of creating a branch-private copy

## Reporting Contract

Bootstrap reporting should stay minimal and optimized for large runs.

### Row Shape

Recommended row payload:

- `business_key`
- `file_path`
- `sheet_name`
- `row_index`
- `status`

Recommended Phase 3 statuses:

- `BOUND_EXISTING_VARIANT`
- `CREATED_AND_BOUND_VARIANT`
- `INVALID_ROW`
- `DUPLICATE_KEY_IN_BOOTSTRAP`

When a row reuses an existing same-source variant, the report still only returns `BOUND_EXISTING_VARIANT`, even if uploaded content was present and ignored.

### Summary Shape

Recommended summary fields:

- `branch_ref`
- `input_kind = bootstrap`
- `import_batch_id`
- `processed_count`
- `bound_existing_variant_count`
- `created_and_bound_variant_count`
- `invalid_row_count`
- `duplicate_key_count`
- `created_entry_count`
- `created_variant_count`
- `elapsed_ms`

The summary should emphasize batch outcome totals, not detailed content-ignore diagnostics.

## Workflow Contract

Phase 3 should expose bootstrap as a dedicated workflow instead of overloading ordinary branch mutation.

Recommended route shape:

- `POST /api/projects/{project_id}/branches/bootstrap`

Recommended request body:

- `branch_ref`
- `import_batch_id`

Recommended behavior:

- create a job
- execute asynchronously
- allow standard polling for job status
- expose summary and row report through the existing job-oriented workflow pattern

This route should reject already bootstrapped branches instead of silently treating bootstrap as an idempotent re-run or as a general range-reset tool.

## Metadata Requirements

Phase 3 only needs the minimum branch metadata necessary to support bootstrap semantics.

Recommended metadata additions or guarantees:

- whether the dev branch is bootstrapped
- when bootstrap completed
- which bootstrap import batch or job established the branch

Phase 3 does not need to add:

- branch owner
- branch note
- branch lock reason
- broader management state unrelated to bootstrap

## Boundaries With Phase 4

Phase 3 deliberately stops before the full mutation contract.

After bootstrap, later writes should be modeled in Phase 4 under two categories:

1. Range-changing writes
   - add a new key
   - change `source`
   - create a new variant or rebind to a different same-source variant

2. Content-only writes
   - modify translations or remarks without changing `source`
   - require the branch to already resolve to the matching `business_key + source`
   - are invalid when the branch does not currently contain that row identity

Phase 3 should not attempt to collapse those later rules into bootstrap.

## Testing Implications

Phase 3 implementation should be verified with tests that cover:

- bootstrap for a new dev branch with `business_key + source` only
- bootstrap for a new dev branch with `business_key + source + partial translations`
- reuse of existing same-source variants without content comparison
- creation of new entries and variants when no match exists
- duplicate-key rejection within the same bootstrap upload
- rejection for already bootstrapped branches
- large-batch execution behavior at the service level, including chunked bind-heavy runs
- summary and row report contracts for bootstrap jobs

## Success Criteria

Phase 3 is successful when the runtime can:

- create a new `dev/<version>` branch through a dedicated bootstrap workflow
- establish that branch's initial range from a large uploaded workbook
- reuse existing same-source variants by default
- create only the missing entries and variants
- report results in a compact job-oriented format
- prevent bootstrap from becoming a repeatable post-init mutation path
