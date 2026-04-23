# Phase 6 Branch-To-Branch Operations Design

## Status

- drafted on 2026-04-22
- approved in design discussion before implementation planning

## Purpose

- define Phase 6 branch-to-branch semantics without inventing a new top-level model
- simplify `replace` into one pure binding rewrite operation
- remove legacy publish-state metadata that conflicts with the branch-as-binding-view model

## Scope

This design defines:

- the formal meaning of `replace`
- the two-step semantic model for `replace`
- the current allowed source and target branch pair
- the minimal preview and execute contract for `branch_replace`
- the implementation boundary for pure binding rewrite
- the removal of `promoted_at`, `is_candidate_release`, `candidate_dev_branch`, and `mark_as_candidate_release`

This design does not define:

- new `replace` pairs beyond `dev/<version> -> rel/current`
- branch-binding count caps such as `max 5 branches per variant`
- content authority or shared-variant edit policy
- pivot preview or pivot review behavior
- lifecycle redesign beyond ordinary orphan refresh after binding changes
- compatibility shims for removed publish-state fields or removed old routes

## Problem Statement

The current runtime already has a `branch_replace` workflow, but it still mixes three different concerns:

- the real branch-to-branch operation
- same-series cleanup behavior
- release-candidate or promote metadata such as `promoted_at` and `is_candidate_release`

That blend makes the model harder to reason about than it needs to be.

The approved Phase 6 direction is simpler:

- `branch` is only a binding-view collection over variants
- `replace` is only a binding rewrite from one branch range into another
- publish-state metadata is not part of the best current-runtime design and should be removed instead of preserved

## Core Decision

Phase 6 keeps one public branch-to-branch workflow named `replace`.

`replace` is a pure binding operation with one `source branch` and one `target branch`.

The formal result is:

- after execute completes, the target branch's active variant range is exactly equal to the source branch's active variant range at execute time

`replace` is not:

- a content mutation
- a variant copy operation
- a variant creation workflow
- a branch lifecycle workflow
- a publish-state transition

## Two-Step Semantic Model

The approved semantic model is intentionally literal.

`replace` means:

1. unbind all current active bindings in the target branch
2. bind into the target branch every current active binding in the source branch

Implementation may optimize the write path internally, but the observable contract must remain equivalent to this two-step model.

Consequences:

- the target branch does not keep any extra binding that is absent from the source branch
- the source branch keeps all of its own bindings
- every source-bound variant that remains in the source range after execute will also be bound to the target branch after execute
- if the source branch is `dev/2.4.3` and the target branch is `rel/current`, then every active variant currently visible in `dev/2.4.3` will be bound to both `dev/2.4.3` and `rel/current` after execute

## Branch Model Boundary

Phase 6 makes one model boundary explicit:

- branch is a binding-view collection, not a release-state entity

Implications:

- a variant may be bound to multiple branches at the same time
- multiple branch bindings on the same variant are normal, not an error by themselves
- `replace` does not need any special-case logic when a variant is already shared with other branches
- shared-variant content authority stays governed by the existing authority model instead of being reopened inside `replace`

The only branch state that matters to `replace` is the current binding set.

## Allowed Pair Policy

Phase 6 keeps the current business policy narrow:

- the only supported public pair is `dev/<version> -> rel/current`

This pair restriction is a workflow policy, not part of the core semantics of `replace`.

Rejected pairs remain errors.

Phase 6 also fixes one negative rule:

- a `replace` operation must not modify any branch that is not the explicit target branch

That means:

- the selected source dev branch is not modified
- other dev branches in the same version series are not modified
- other dev branches in different version series are not modified
- `replace` must not perform same-series cleanup, cross-branch unbinding, or any hidden write against unrelated branch rows

## Legacy Publish-State Cleanup

The old publish-state model is explicitly out of scope for the best current-runtime design.

Phase 6 removes these runtime concepts entirely:

- `promoted_at`
- `is_candidate_release`
- `candidate_dev_branch`
- `mark_as_candidate_release`

Removal means:

- delete the persisted fields instead of keeping dormant compatibility columns
- delete the request and response fields instead of keeping compatibility aliases
- delete the frontend and test assumptions that depend on candidate or promote wording
- derive any UI defaults from the live branch list rather than from a persisted candidate flag

Phase 6 does not retain a compatibility period for these fields.

## Preview Contract

`branch_replace` stays in the Phase 5 preview family.

Required top-level preview envelope:

- `preview_kind = effect_forecast`
- `workflow_kind = branch_replace`
- `request_echo`
- `summary`
- `rows`

Required `request_echo` fields:

- `source_branch_ref`
- `target_branch_ref`

### Replace Status Vocabulary

The stable Phase 6 row statuses are:

- `ADD_TO_TARGET`
- `KEEP_IN_TARGET`
- `REBIND_TARGET`
- `REMOVE_FROM_TARGET`

These statuses are an observation layer over the two-step rewrite model. They do not replace the approved core semantics; they describe the net visible effect per `business_key`.

Meanings:

- `ADD_TO_TARGET`: the source branch has the key and the target branch does not
- `KEEP_IN_TARGET`: source and target already bind the same variant for the key
- `REBIND_TARGET`: source and target both have the key but currently bind different variants
- `REMOVE_FROM_TARGET`: the target branch has the key and the source branch does not

### Minimal Row Shape

The minimal stable row contract is:

- `business_key`
- `status`

`branch_replace` rows should stay compact:

- do not include full variant content snapshots
- do not include branch metadata
- do not include candidate or promote fields

Secondary machine fields such as `binding_effect`, `variant_resolution`, and `row_outcome` may still appear when they add clarity, but they are not the primary Phase 6 business contract for `replace`.

### Minimal Summary Shape

The stable Phase 6 summary fields are:

- `final_target_entry_count`
- `added_to_target_count`
- `kept_in_target_count`
- `rebind_target_count`
- `removed_from_target_count`

Phase 6 removes replace-specific summary noise such as:

- `cleanup_binding_count`
- candidate or promote-derived counters

The summary must answer the operator's main question first:

- what the target branch will look like after the rewrite

## Execute Contract

Execute uses the same request shape as preview:

- `source_branch_ref`
- `target_branch_ref`

Execution rules:

- execute is evaluated against current runtime state at execute time
- preview does not reserve bindings or promise future immutability
- execute runs in one transaction
- any unhandled failure rolls the entire operation back
- execute only changes target-branch bindings
- execute must not modify source-branch bindings
- execute must not modify any unrelated branch bindings
- execute must not write publish-state metadata

Execute reporting should reuse the same business vocabulary as preview:

- the same four statuses
- the same `final_target_entry_count` plus the same four change counters

Ordinary lifecycle maintenance after the binding rewrite remains allowed:

- if a removed target binding leaves a variant with no remaining bindings, normal orphan refresh may make that variant orphan

That orphan refresh is a general lifecycle consequence, not a special Phase 6 replace semantic.

## Implementation Shape

Phase 6 should keep the runtime structure simple.

### Preview

Preview should:

- load current active bindings from the source branch
- load current active bindings from the target branch
- compare them by `business_key`
- emit the four replace statuses plus the minimal summary counts

Preview should not:

- perform cleanup logic
- inspect or mutate publish-state metadata
- create jobs or write business state

### Execute

Execute should:

1. read the source branch's current active bindings
2. clear the target branch's current active bindings
3. upsert the source binding set into the target branch
4. refresh orphan state for the entries touched by the binding rewrite

The implementation should delete the old same-series cleanup path entirely.

### Supporting Model Cleanup

The surrounding runtime should simplify to match the new semantics:

- `dev_versions` keeps branch identity plus bootstrap facts only
- branch summary and bootstrap payloads no longer carry candidate or promote state
- import-batch mutation no longer accepts `mark_as_candidate_release`
- replace policy no longer includes unrelated-branch cleanup behavior

## Multiple-Branch Binding Note

Phase 6 explicitly accepts that one variant may be bound to many branches at once.

This design does not cap the number of branch bindings per variant.

Any future branch-binding cap is a separate cross-workflow design because it would affect:

- bootstrap
- mutation
- replace
- preview failure semantics

That question is therefore deferred out of Phase 6.

## Testing Implications

Phase 6 implementation should verify at least:

- replace preview still reports `ADD_TO_TARGET`, `KEEP_IN_TARGET`, `REBIND_TARGET`, and `REMOVE_FROM_TARGET`
- replace execute leaves the target branch range exactly equal to the source branch range
- source-branch bindings remain unchanged
- unrelated branches remain unchanged
- replace rollback still leaves the target branch unchanged after failure
- candidate and promote fields are absent from request models, response models, UI state, tests, and docs

## Success Criteria

Phase 6 is successful when:

- `replace` has one simple meaning: pure target binding rewrite
- the target branch range strictly equals the source branch range after execute
- source and unrelated branches remain untouched
- same-series cleanup is gone
- candidate and promote metadata are gone
- preview and execute speak in the same minimal replace vocabulary
- the runtime aligns with the branch-as-binding-view model instead of a hidden publish-state model
