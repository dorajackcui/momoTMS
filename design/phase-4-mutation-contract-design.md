# Phase 4 Mutation Contract Design

## Status

- drafted on 2026-04-21
- validated in discussion before implementation

## Purpose

- define the canonical semantic model for branch mutation work in Phase 4
- separate branch mutation semantics from legacy runtime input shapes
- keep current runtime behavior compatible while introducing a stable semantic layer for later phases

## Scope

This spec defines:

- the top-level branch mutation categories
- the row-level result semantics for branch mutation
- the summary-level counting model for branch mutation
- how current runtime entry shapes relate to the canonical mutation contract

This spec does not define:

- preview contract convergence
- replace or promote semantics
- pivot preview or review changes
- lifecycle closure
- final public API redesign for mutation entry shapes

## Problem Statement

The current runtime exposes branch mutation through legacy input kinds such as `direct` and `import_batch`, while row results are reported through execution-oriented statuses such as:

- `UPDATED_BOUND_VARIANT`
- `BOUND_EXISTING_VARIANT`
- `UPDATED_AND_BOUND_EXISTING_VARIANT`
- `CREATED_AND_BOUND_VARIANT`
- `NOOP`

Those statuses are still useful for compatibility, but they mix together multiple concerns:

- whether the branch range changed
- whether shared or branch-visible content changed
- whether a row created a new variant, rebound to an existing one, or only updated content
- whether a row was a true noop or a filtered no-effect result under authority rules

Phase 4 should not redefine business interfaces yet. It should define the canonical mutation semantics that later interfaces, previews, and policies can share.

## Core Decision

Phase 4 defines one canonical `branch mutation` contract.

That contract has two top-level mutation classes:

1. `range mutation`
2. `content mutation`

Current runtime entry shapes such as `direct` and `import_batch` are not semantic categories in this model. They are compatibility transports that submit work into the same canonical mutation contract.

## Top-Level Mutation Classes

### Range Mutation

Definition:

- a mutation that changes the branch's effective coverage range
- this happens when the row changes `source`, or when the row introduces a new `business_key` into the branch

Semantic meaning:

- the branch is selecting a different variant identity for a key, or adding a key that the branch did not previously cover

Typical outcomes:

- create a new variant and bind it
- bind a key that previously had no branch binding
- rebind an already-covered key from one variant to another

Typical examples:

- same `business_key`, different `source`
- new `business_key` appears in the branch

### Content Mutation

Definition:

- a mutation that changes content only
- it does not change `source`
- it does not change which variant identity the branch currently covers

Semantic meaning:

- the branch keeps its current coverage range and only edits content on the currently covered row

Allowed fields:

- translations
- remarks
- `file_name`

Hard precondition:

- the target branch must already have the matching current `business_key + source` binding for the row

Failure rule:

- if that precondition is not satisfied, the mutation is not silently upgraded into a range mutation
- instead, it is treated as a missing-target content mutation

Typical examples:

- add a translation for one language
- update an existing translation
- update one or more remarks

## Branch Neutrality

Both mutation classes apply to all branch types:

- `rel/current`
- `dev/<version>`

Phase 4 does not define separate semantic models for `rel` and `dev`.

Product-facing differences may later emerge in naming, UX, and interface structure. For example:

- `dev` flows may more often present as content-completion work
- `rel` flows may more often present as a mix of range and content work

Those are later business-layer concerns. They do not change the canonical mutation semantics.

## Canonical Row Semantics

Phase 4 keeps the existing public row `status` values for compatibility, but adds a stable semantic layer alongside them.

Recommended semantic fields:

- `mutation_class`
  - `range`
  - `content`
- `binding_effect`
  - `none`
  - `bind`
  - `rebind`
- `content_effect`
  - `none`
  - `create`
  - `update`
  - `filtered`
- `row_outcome`
  - `applied`
  - `noop`
  - `missing`

### Meaning Of Each Semantic Field

`mutation_class`

- describes the intended business class of the row
- answers whether the row is trying to change branch range or only content

`binding_effect`

- describes what happened to the branch binding
- `bind` means the branch did not previously have an active binding for that key and now does
- `rebind` means the branch already had an active binding for that key and now points to a different variant

`content_effect`

- describes what happened to content on the resolved target variant
- `create` is reserved for newly created variant content
- `update` means existing variant content changed
- `filtered` means requested content edits were dropped by authority policy while any otherwise legal binding effect still proceeded

`row_outcome`

- describes the overall business result of the row
- `applied` means the row produced at least one real effect
- `noop` means no effect was applied
- `missing` means the row was a content mutation against a missing branch-visible target, or otherwise failed the missing-target rule without becoming a range mutation

## Canonical Mapping Rules

### Range Mutation Rules

Range mutation may produce:

- `binding_effect = bind`
- `binding_effect = rebind`

Range mutation may also produce one of these content effects:

- `content_effect = none`
- `content_effect = create`
- `content_effect = update`
- `content_effect = filtered`

Typical combinations:

- create new variant for a new identity: `bind/rebind + create + applied`
- switch to existing variant with no content edit: `bind/rebind + none + applied`
- switch to existing variant and update its content: `bind/rebind + update + applied`
- switch to existing variant but authority filters the content edit: `bind/rebind + filtered + applied`

### Content Mutation Rules

Content mutation must never implicitly change branch range.

Content mutation therefore only allows:

- `binding_effect = none`

Possible content results:

- `content_effect = update`
- `content_effect = filtered`
- `content_effect = none`

Possible row outcomes:

- `applied`
- `noop`
- `missing`

Canonical examples:

- content updated on current target: `none + update + applied`
- content requested but filtered by authority: `none + filtered + noop`
- content request exactly matches current state: `none + none + noop`
- content request for missing branch-visible target: `none + none + missing`

## Compatibility With Current Status Values

Existing public row statuses stay in place during Phase 4.

Examples of intended compatibility mapping:

| Current public status | Typical semantic interpretation |
| --- | --- |
| `UPDATED_BOUND_VARIANT` | `binding_effect = none`, `content_effect = update`, `row_outcome = applied` |
| `BOUND_EXISTING_VARIANT` | `binding_effect = bind` or `rebind`, `content_effect = none` or `filtered`, `row_outcome = applied` |
| `UPDATED_AND_BOUND_EXISTING_VARIANT` | `binding_effect = bind` or `rebind`, `content_effect = update`, `row_outcome = applied` |
| `CREATED_AND_BOUND_VARIANT` | `binding_effect = bind` or `rebind`, `content_effect = create`, `row_outcome = applied` |
| `NOOP` | `binding_effect = none`, `content_effect = none` or `filtered`, `row_outcome = noop` |
| `MISSING_IN_SCOPE` | `binding_effect = none`, `content_effect = none`, `row_outcome = missing` |

Important rule:

- the semantic layer is the source of truth for normalized meaning
- the compatibility `status` field remains a preserved legacy reporting surface

## Authority Semantics

Phase 4 reuses the Phase 2 authority model.

Authority still applies only to in-place content edits on the resolved target variant.

Implications for Phase 4:

- authority does not redefine the mutation class
- authority does not turn a content mutation into a range mutation
- authority does not invalidate an otherwise legal bind or rebind effect during range mutation
- authority-filtered content should be expressed through `content_effect = filtered`

Current compatibility metadata such as `content_filtered_by_authority = true` remains valid during Phase 4 and should continue to be emitted where applicable.

## Canonical Summary Semantics

Phase 4 keeps existing summary counters for compatibility, but adds semantic summary counters derived only from the new semantic fields.

Recommended semantic summary shape:

- `mutation_class_counts`
  - `range_count`
  - `content_count`
- `binding_effect_counts`
  - `none_count`
  - `bind_count`
  - `rebind_count`
- `content_effect_counts`
  - `none_count`
  - `create_count`
  - `update_count`
  - `filtered_count`
- `row_outcome_counts`
  - `applied_count`
  - `noop_count`
  - `missing_count`

Rules:

- compatibility counts continue to be derived from legacy `status`
- semantic counts are derived only from the semantic layer
- the two counting layers should coexist without trying to infer one from the other

This allows later phases to adopt the semantic counters without breaking existing clients that still read the legacy counters.

## Legacy Input Shapes

`direct` and `import_batch` are treated as legacy transport forms rather than canonical mutation semantics.

Phase 4 does not need to finalize their business meaning.

Instead, Phase 4 only requires this invariant:

- regardless of how mutation work enters the runtime, it must resolve to the same canonical mutation semantics

### Why Input Shapes Are Deferred

- Phase 3 already redefined branch bootstrap as a dedicated workflow, which reduced the need for `import_batch` to carry branch-init semantics
- current runtime usage patterns do not justify making `direct` and `import_batch` first-class semantic categories
- the product may later redesign business-facing mutation interfaces without changing the Phase 4 canonical mutation model

## Evolution Strategy

Phase 4 performs semantic convergence first.

That means:

- define one canonical branch mutation model
- demote legacy input shapes from semantic concepts to compatibility transports
- keep existing public statuses and current runtime entry shapes intact while the semantic layer is introduced

Public contract cleanup should happen later, after downstream phases stabilize:

- preview family convergence
- branch-to-branch operation semantics
- lifecycle closure
- final contract convergence

Recommended timing:

- Phase 4: semantic convergence
- Phase 9: interface convergence and cleanup of legacy mutation entry naming

## Implementation Guidance For Later Planning

When this spec moves into implementation, the plan should preserve these boundaries:

- do not rename existing public mutation statuses in the Phase 4 implementation
- do not remove `content_filtered_by_authority` in Phase 4
- do not mix preview or replace semantics into the Phase 4 mutation contract change
- add one shared semantic-mapping layer so current runtime entry paths cannot drift apart
- prove that semantically equivalent rows produce the same normalized semantics regardless of runtime transport path

## Success Criteria

Phase 4 is successful when:

- branch mutation has one explicit canonical semantic model
- `range mutation` and `content mutation` are clearly defined and branch-neutral
- content mutation has an explicit missing-target rule instead of silently degrading into range mutation
- compatibility statuses remain intact
- a stable semantic layer exists for rows and summaries
- legacy input shapes no longer define the meaning of mutation work
