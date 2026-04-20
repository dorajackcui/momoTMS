# Branch Authority Model

## Status

- complete
- implemented in current runtime for branch mutation filtering and reporting

## Purpose

- define the Phase 2 authority core for branch-shared variants
- make the branch authority matrix explicit before later mutation, preview, and lifecycle work
- keep Phase 2 scoped to content ownership, not later branch-to-branch or pivot workflows

## Scope

This note defines only one thing:

- when multiple branches share the same `variant`, who may modify that variant's in-place content

This note does not yet define:

- branch bootstrap and branch creation
- the full mutation result contract
- branch-to-branch operations such as replace or promote
- pivot review semantics

Those are deferred to later phases in [branch-infra-phase-map.md](branch-infra-phase-map.md).

## Core Boundary

`branch authority` applies only to in-place edits on an already resolved target variant.

Protected content:

- `translations`
- `remarks`

Not protected by this matrix:

- `source`

Reason:

- a `variant` owns exactly one shared content body: `translations + remarks`
- changing `source` is not an in-place edit to that content body
- when `source` changes, the system is selecting or creating a different variant rather than editing the current shared one

## Authority Ordering

Authority ordering is a system-level policy, not a project-level configuration.

The ordering model is:

1. `rel/current` is always the highest-authority branch.
2. `dev` authority is determined first by an explicit `ordered candidate version series list`.
3. Earlier series in that ordered list have higher authority than later series.
4. Within the same version series, higher patch versions have higher authority.

This means `dev` authority is based on release-candidate ordering first and patch order second. It is not derived from semver magnitude alone.

Example:

If the ordered candidate version series list is:

- `1.3.x`
- `2.11.x`

then the authority order is:

- `rel/current`
- `dev/1.3.9`
- `dev/1.3.2`
- `dev/2.11.7`
- `dev/2.11.3`

## Working Definitions

`Resolved target variant`

- the variant that a mutation row will ultimately operate on after `source` handling is resolved

`Actor authority`

- the authority of the branch that initiated the mutation row

`Highest bound authority`

- the greatest authority among branches that are currently bound to the resolved target variant

`Content write owner`

- the branch at the top of the current binding set for a shared variant
- only that branch, or a higher-authority branch that later joins the binding set, may edit that variant's in-place content

## Branch Authority Matrix

This matrix applies only after the system has already resolved the target variant for the row.

| Actor vs resolved target's highest bound authority | In-place edit on `translations + remarks` | Effect |
| --- | --- | --- |
| `actor < highest bound authority` | filtered | keep any otherwise legal bind or rebind; do not apply the content patch |
| `actor = highest bound authority` | allowed | apply the content patch in place |
| `actor > highest bound authority` | allowed | apply the content patch in place; actor becomes the highest-authority writer in the current shared set |
| no current bindings on resolved target | allowed | actor may edit because the target is not currently shared |

Implications:

- a shared variant has only one live same-source content body
- lower-authority branches may reuse that content, but they may not fork a same-source variant just to get write access
- authority does not block legitimate binding reuse by itself; it only filters the content-edit portion of a row

## Action Semantics

### In-Place Content Edit

Definition:

- the row resolves to an existing target variant
- `source` does not create a different target identity
- the request includes edits to `translations + remarks`

Rule:

- this is the core case governed by the branch authority matrix

### Pure Bind Or Rebind

Definition:

- the row binds the actor branch to an already existing variant
- the row does not need to change `translations + remarks`

Rule:

- pure bind or rebind is not blocked by content authority

### Source Switch

Definition:

- the row selects a different `source`

Rule:

- if a same-entry target variant with that `source` already exists, the row may bind or rebind to it
- if it does not exist, the row may create a new variant and bind to it
- `source` switching is not itself an authority-controlled content edit

### Composite Rows

A single mutation row may be a composite operation rather than a single action.

Examples:

- `rebind + in-place edit`
- `create new variant + initial content + bind`

The correct evaluation order is:

1. resolve the target variant
2. identify whether the row includes a bind or rebind
3. identify whether the row includes a `translations + remarks` edit
4. apply the authority matrix only to that content-edit portion, against the resolved target variant

This keeps authority attached to the actual content target rather than the previous binding.

## Orphan Rule

If the resolved target variant currently has no bindings, it has no current shared authority owner.

In that case:

- the actor may bind to it
- the actor may also apply an in-place content edit to it in the same row

This treats authority as a property of the current sharing set rather than a permanent historical lock.

## Internal Outcome Vocabulary

Phase 2 settles the internal semantic distinctions that later phases should preserve even if API-facing names change.

`EDIT_APPLIED`

- the row changed `translations + remarks` on the resolved target variant

`BIND_ONLY`

- the row produced a bind or rebind effect without a content edit

`CONTENT_FILTERED_BY_AUTHORITY`

- the row requested a content edit
- the bind or rebind portion was still legal
- the requested content edit was dropped because the actor lacked authority over the resolved target variant
- the current implementation surfaces this distinction as row metadata plus a summary count rather than a separate public row status

`NO_EFFECT`

- the row produced neither a binding change nor a content change
- this is different from `CONTENT_FILTERED_BY_AUTHORITY`

`NEW_VARIANT_CREATED_AND_BOUND`

- the row switched to a previously missing `source`, created a new variant, and bound the actor branch to it

## Rules That Phase 2 Intentionally Defers

The following questions are deliberately not closed in this note:

- branch-to-branch operation semantics for replace or promote
- whether later preview systems surface internal authority-filtered statuses directly or fold them into other row outcomes
- how pivot review should compare reviewer authority with changed-owner authority

Those later designs must reuse the authority ordering and content-ownership model defined here, but they should be finalized in their own phases rather than backfilled into Phase 2.
