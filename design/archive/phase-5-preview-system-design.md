# Phase 5 Preview System Design

## Status

- drafted on 2026-04-22
- validated in discussion before implementation planning

## Purpose

- define `preview` as a stable operator-facing concept
- converge existing workflow previews into one preview family without flattening away workflow-specific meaning
- make large-batch preview useful for business decisions such as reuse, rebind, and new-variant creation
- reserve extension points for later `pivot` preview work without designing `pivot` in Phase 5

## Scope

This design defines:

- the formal meaning of `preview`
- preview read-only constraints
- the shared preview family shape
- the canonical Phase 5 contract for `effect_forecast`
- how `branch_replace`, `branch_mutation`, and `branch_bootstrap` map into that contract
- how `input_precheck` fits into the same family without being forced into execute-style semantics

This design does not define:

- detailed `pivot` preview behavior
- `fill` preview behavior
- a requirement that every preview row use identical top-level fields
- full frontend adoption order
- final public route cleanup or compatibility removal

## Problem Statement

The runtime currently has multiple things called `preview`, but they answer different questions:

- import upload preview answers whether incoming input can be consumed
- branch replace preview answers what a workflow would do if executed
- job detail returns a report preview window rather than a standalone preview contract

Those surfaces are individually useful, but there is no shared contract that explains:

- what `preview` is actually previewing
- whether preview is read-only
- which preview kinds must align with execute semantics
- which summary counts matter most for large batches
- how later workflows such as `pivot` should join the same family

Phase 5 should solve that without reopening Phase 3 bootstrap semantics or Phase 4 mutation semantics.

## Core Decision

Phase 5 defines one `preview family`.

Every preview in that family is:

- tied to a concrete request
- computed against the current runtime state
- read-only with respect to business state
- explicit about which preview kind it is

Phase 5 defines two preview kinds:

1. `input_precheck`
2. `effect_forecast`

`input_precheck` and `effect_forecast` are both previews, but only `effect_forecast` is required to align with execute semantics.

## Formal Preview Definition

`preview` is a read-only operation that returns the expected result summary for a concrete request against the current runtime state.

That expected result may be one of two shapes:

- `input_precheck`: whether the request input is structurally usable by a later workflow
- `effect_forecast`: what business effect the workflow is expected to produce if executed immediately

Preview therefore does not mean:

- a snapshot of all current runtime state
- a partial execution
- a promise that later execute results can never change

Preview is a forecast derived from the state visible at preview time.

## Read-Only Requirement

Preview is read-only at the business-state level.

Phase 5 requires that preview must not:

- modify `projects`, `entries`, `variants`, `scope_bindings`, `dev_versions`, or workflow-owned business state
- create execution jobs
- write execution reports or workflow artifacts
- change lifecycle state
- change pivot state
- reserve branch range or variant identity for later execution

Preview may:

- read current runtime state
- perform request-scoped computation
- return derived counts and lightweight row classifications

Preview should not rely on write-then-rollback techniques or any implementation that exposes partial side effects to callers.

## Large-Batch Design Constraint

Preview must work for workloads around `200000` rows.

That requires:

- summary-first responses
- minimal row payloads
- stable low-cardinality status vocabularies
- no full variant content snapshots inside preview rows unless a workflow cannot express its result otherwise

Preview is therefore an operator decision aid, not a debug dump.

## Shared Preview Family Shape

All preview responses belong to the same family and should expose the same top-level envelope:

- `preview_kind`
- `workflow_kind`
- `request_echo`
- `summary`
- `rows`

### `preview_kind`

Allowed Phase 5 values:

- `input_precheck`
- `effect_forecast`

### `workflow_kind`

Identifies which workflow the preview belongs to.

Phase 5 relevant values:

- `import_upload`
- `branch_bootstrap`
- `branch_mutation`
- `branch_replace`

Later phases may add values such as `pivot_review` or `fill`.

### `request_echo`

`request_echo` returns the business-meaningful request inputs that determine the preview result.

Examples:

- upload session id or sheet selection for import precheck
- branch refs for replace preview
- branch ref plus mutation input kind for mutation preview
- branch ref plus import batch id for bootstrap preview

`request_echo` should omit incidental transport noise.

### `summary`

`summary` is the primary output for large-batch preview.

It should:

- expose counts that matter for operator decisions
- be machine-readable
- line up with row classifications
- avoid embedding high-volume content

### `rows`

`rows` are a lightweight classification surface.

They should:

- keep only necessary row identity plus core result fields
- avoid full content payloads
- support preview windows, paging, or later full-report style access without assuming that all rows are returned inline

## Minimal Row Shape

Phase 5 does not require every preview row to be top-level identical.

It does require every preview row to stay minimal and include:

- row identity
- a workflow-specific status
- only the smallest additional semantic fields needed for business interpretation

For workbook-derived rows, row identity may include:

- `business_key`
- `file_path`
- `sheet_name`
- `row_index`

For branch-derived rows, row identity may be only:

- `business_key`

The critical rule is minimality, not artificial field uniformity.

## `input_precheck`

`input_precheck` answers whether input is structurally ready for a later workflow.

Examples:

- workbook upload preview
- header mapping preview
- missing required business columns

`input_precheck` is part of the preview family, but it is not required to project into execute-style business-effect semantics.

Phase 5 keeps `input_precheck` in the family so the runtime can speak about one preview concept without pretending that all previews are effect forecasts.

## `effect_forecast`

`effect_forecast` is the Phase 5 center of gravity.

It answers:

- what binding change is expected
- whether a row reuses an existing variant or creates a new one
- whether a row applies, noops, is missing, or is invalid

Phase 5 defines one shared semantic block for `effect_forecast`.

### Shared Semantic Fields

- `binding_effect`
- `variant_resolution`
- `row_outcome`

#### `binding_effect`

Allowed values:

- `none`
- `bind`
- `rebind`

Meaning:

- whether the branch binding changes for the row

#### `variant_resolution`

Allowed values:

- `stay_current`
- `reuse_existing`
- `create_new`

Meaning:

- whether the row stays on the current target, reuses an already-existing variant, or creates a new variant

This field exists because operators care directly about:

- how many rows only reuse existing variants
- how many rows will create new variants
- how many rows only rebind

#### `row_outcome`

Allowed values:

- `applied`
- `noop`
- `missing`
- `invalid`

Meaning:

- the overall business result of the row

## Why Phase 5 Uses `variant_resolution`

Phase 4 already normalized mutation semantics around:

- `mutation_class`
- `binding_effect`
- `content_effect`
- `row_outcome`

That remains correct for mutation execution.

Phase 5 adds `variant_resolution` at preview time because business operators frequently ask questions that Phase 4 alone does not answer directly enough:

- how many rows only reuse an existing variant
- how many rows create a new variant
- how many rows stay on the current variant

`variant_resolution` is therefore not a replacement for Phase 4 semantics. It is the minimal extra dimension needed to make preview useful at business scale.

## Preview-To-Execute Alignment Rule

Only `effect_forecast` must align with execute semantics.

Alignment rule:

- preview and execute do not need identical legacy `status` vocabularies
- preview and execute must both be projectable into the same semantic interpretation for:
  - `binding_effect`
  - `variant_resolution`
  - `row_outcome`

This allows the runtime to preserve compatibility statuses where useful while still giving operators one stable way to understand business effect.

## Workflow Mapping

### Branch Bootstrap

Bootstrap preview is an `effect_forecast`.

Its job is to answer:

- how many rows will bind an existing variant
- how many rows will create and bind a new variant
- how many rows are invalid before execution

Recommended mapping:

- `BOUND_EXISTING_VARIANT`
  - `binding_effect = bind`
  - `variant_resolution = reuse_existing`
  - `row_outcome = applied`
- `CREATED_AND_BOUND_VARIANT`
  - `binding_effect = bind`
  - `variant_resolution = create_new`
  - `row_outcome = applied`
- `INVALID_ROW`
  - `row_outcome = invalid`
- `DUPLICATE_KEY_IN_BOOTSTRAP`
  - `row_outcome = invalid`

Bootstrap preview summary should emphasize:

- existing-variant reuse count
- new-variant creation count
- invalid row count

### Branch Mutation

Mutation preview is an `effect_forecast`.

It should preserve the Phase 4 distinction between range-changing and content-only work while surfacing the operator-centered `variant_resolution` dimension.

Representative mappings:

- content-only work on the current target
  - `binding_effect = none`
  - `variant_resolution = stay_current`
- rebind to an already-existing target variant
  - `binding_effect = bind` or `rebind`
  - `variant_resolution = reuse_existing`
- create a new variant
  - `binding_effect = bind` or `rebind`
  - `variant_resolution = create_new`
- missing-target content mutation
  - `row_outcome = missing`
- invalid request row
  - `row_outcome = invalid`

Mutation preview must not erase Phase 4 semantics. Instead, it should layer on top of them and keep summary counts that answer the preview-oriented reuse or create questions.

### Branch Replace

Replace preview is an `effect_forecast`.

It already expresses real binding-change semantics and should remain the anchor example for Phase 5.

Representative mappings:

- `ADD_TO_TARGET`
  - `binding_effect = bind`
  - `variant_resolution = reuse_existing`
  - `row_outcome = applied`
- `REBIND_TARGET`
  - `binding_effect = rebind`
  - `variant_resolution = reuse_existing`
  - `row_outcome = applied`
- `KEEP_IN_TARGET`
  - `binding_effect = none`
  - `variant_resolution = stay_current`
  - `row_outcome = noop`
- `REMOVE_FROM_TARGET`
  - keep workflow-specific `status = REMOVE_FROM_TARGET`
  - `row_outcome = applied`

Phase 5 deliberately does not invent another generic top-level semantic field just to flatten `REMOVE_FROM_TARGET`.

That would add abstraction cost without improving operator decisions.

## Summary Requirements For `effect_forecast`

Every `effect_forecast` summary should be able to answer at least:

- how many rows bind
- how many rows rebind
- how many rows reuse an existing variant
- how many rows create a new variant
- how many rows stay on the current variant
- how many rows apply
- how many rows noop
- how many rows are missing
- how many rows are invalid

Workflows may add narrower counts where useful, but they should not omit these operator-critical aggregates.

## Phase 5 Range

Phase 5 includes:

- a shared preview family definition
- `preview_kind`
- `effect_forecast` semantic convergence
- `branch_replace` alignment to the shared family
- preview contract definitions for `branch_mutation` and `branch_bootstrap`
- active-doc updates for the new preview language

Phase 5 does not require:

- implementing every planned preview route in one change
- redesigning import upload preview into an effect preview
- defining `pivot` preview details
- solving future `fill` preview behavior

## Reserved Extension Point For Phase 7

Later `pivot` preview work should join the same preview family by:

- using `preview_kind = effect_forecast`
- defining `workflow_kind` for the pivot workflow
- reusing the summary-first, minimal-row principles

Phase 5 intentionally leaves the exact pivot row contract open.

## Non-Goals

- forcing every preview row across all workflows to use identical fields
- turning preview into a job-backed workflow
- embedding full variant content snapshots in preview rows
- treating import upload precheck as if it were execute-effect forecasting
- reopening bootstrap or mutation core semantics already settled in Phases 3 and 4

## Success Criteria

Phase 5 is successful when:

- `preview` has one stable formal definition
- preview is explicitly read-only
- the runtime distinguishes `input_precheck` from `effect_forecast` without creating separate conceptual families
- `effect_forecast` exposes the three shared semantic dimensions:
  - `binding_effect`
  - `variant_resolution`
  - `row_outcome`
- preview summaries can directly answer reuse, rebind, and new-variant questions for large batches
- `branch_replace`, `branch_mutation`, and `branch_bootstrap` can be described within the same preview family
- `pivot` has a clear extension point without Phase 5 trying to solve it early
