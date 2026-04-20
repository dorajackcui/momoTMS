# Branch Variant Pivot Foundation Design

## Status

Design spec for clarifying the project's foundational domain model before further branch workflow design.

## Goal

Define a stable conceptual foundation for `entry`, `variant`, `branch`, and `pivot`, then use that foundation to decide the correct design order for backend capabilities and API contracts.

This spec is intentionally domain-first. It does not try to preserve every current implementation detail if that detail weakens the model.

## Scope

In scope:

- core domain concepts
- concept boundaries and terminology
- design order for foundational backend and API work
- minimum API contract skeleton
- placement of branch authority rules

Out of scope:

- UI flow design
- implementation task breakdown
- migration details
- concrete database refactors

## Primary Decisions

1. `branch` and `scope` are treated as the same concept for the main model. The project should converge on `branch` as the primary term.
2. `variant` is an `entry`-local content entity, primarily anchored by `entry + source`.
3. `pivot` is part of `variant` state. It is not a separate top-level domain object.
4. Foundational work should be designed in domain order, not workflow order.
5. Branch authority rules belong after the branch model is stable and before mutation semantics are finalized.

## Core Domain Model

### Entry

`entry` is the stable business slot for text content.

- identity: `project + business_key`
- responsibility: define business identity only
- non-responsibility: `entry` does not directly hold translations, remarks, or workflow status

The question answered by `entry` is: "Which business text slot are we talking about?"

### Variant

`variant` is the content entity under an `entry`.

- primary anchor: `entry + source`
- owned fields: `source`, `translations`, `remarks`, `file_name`, `pivot_*`
- role: represent one live content entity for a given source under a specific entry

The question answered by `variant` is: "What content do we have for this entry and source?"

This model intentionally treats `variant` as a live entity, not as an arbitrary version snapshot collection.

### Branch

`branch` is the selection layer.

- role: choose which `variant` is currently active for each `entry`
- non-role: `branch` is not the content entity itself
- expected invariant: one branch selects at most one active variant per entry

The question answered by `branch` is: "Which content is currently active for this entry in this branch?"

### Pivot

`pivot` is internal workflow state owned by a `variant`.

- role: describe review or synchronization state for that variant's content
- non-role: `pivot` is not a separate top-level object and should not become a parallel model

The question answered by `pivot` is: "What workflow state is this variant currently in?"

## Concept Layering

The model should be understood in four layers:

1. content identity layer: `entry`
2. content entity layer: `variant`
3. selection layer: `branch`
4. workflow layer: mutation, trash or restore, replace, pivot review

Higher layers may act on lower layers, but should not redefine them.

## Design Order

Foundational capabilities should be designed in the following order.

### Phase 1: Entry and Variant

First define the content model.

Questions to settle:

- what makes an entry unique
- what makes a variant unique
- whether live same-source duplicates are allowed
- which fields belong to variant state

This phase must finish before branch behavior is expanded. If the content model is unstable, every branch workflow becomes unstable.

### Phase 2: Branch

After the content model is stable, define branch as a pure binding or selection concept.

Questions to settle:

- what identifies a branch
- what metadata belongs to a branch
- what a branch can bind
- what branch invariants hold per entry

This phase should keep branch narrow. Branch chooses content; it does not redefine content.

### Phase 3: Minimal Read Contracts

Only after Phases 1 and 2 are stable should the project lock in the minimum read surface needed to observe the model.

The goal is to prove the model can be read consistently before defining writes.

### Phase 4: Branch Authority Policy

Branch authority should be designed after the branch model exists but before mutation semantics are finalized.

This is the correct place for rules such as:

- a lower-authority branch cannot modify a variant that is also bound by a higher-authority branch
- equal or higher authority may update shared content under defined conditions

Branch authority is not user permission. It is branch-to-branch policy.

This phase should define:

- the authority ordering between branches
- which write behaviors are blocked by authority
- which write behaviors remain allowed even when content mutation is blocked

### Phase 5: Mutation

After authority is defined, branch mutation behavior can be designed precisely.

This phase should clearly separate:

- changing variant content
- rebinding a branch to a different variant

Mutation must not behave like a single opaque "do everything" operation.

### Phase 6: Lifecycle

After mutation semantics are stable, define variant lifecycle consequences.

This includes:

- orphan
- trash
- restore

Lifecycle should be modeled as the result of branch binding changes and content availability, not as a competing identity model.

### Phase 7: Branch-to-Branch Operations

Only after content, branch, authority, mutation, and lifecycle are stable should the project design replace or promote behavior.

These are higher-order branch operations. They should reuse the lower model instead of inventing new concepts.

### Phase 8: Pivot Workflow

`pivot` should be connected last.

Because pivot belongs to variant state, pivot review and pivot authority should be expressed as constrained state transitions on variants, not as a separate system that drives the rest of the model.

## Minimum API Skeleton

The backend API skeleton should be kept intentionally small and should exist to prove the model, not to maximize endpoint count.

### Entry and Variant Observation

`GET /entries/{business_key}/variants`

Purpose:

- show all variants under one entry
- provide the truth view for content entities

Minimum row shape:

- `variant_id`
- `source`
- `translations`
- `remarks`
- `file_name`
- `pivot_*`

### Branch Catalog Read

`GET /branches/{branch_ref}/rows`

Purpose:

- show which variant each entry currently uses in a branch

This contract should answer "what is active here now?"

### Branch Lookup

`GET /branches/{branch_ref}/lookup?business_key=...`

`GET /branches/{branch_ref}/lookup?source=...`

Purpose:

- allow targeted lookup for workflows and operator inspection

### Branch Mutation

`POST /branches/mutations`

Purpose:

- apply controlled branch writes

The behavior model must distinguish:

- update currently bound variant content
- bind an existing variant
- create and bind a new variant when allowed

### Lifecycle Operations

`POST /variants/trash/delete`

`POST /variants/trash/restore`

Purpose:

- model removal of active usage separately from restoration of content availability

Delete should act through branch usage. Restore should act on variants.

### Branch Replace

`POST /branches/replace/preview`

`POST /branches/replace/execute`

Purpose:

- model branch-to-branch rebinding

Preview must express binding changes, not only key set overlap.

### Pivot Review

`POST /variants/pivot/review`

Purpose:

- perform constrained pivot state transitions on variants

## Concept Conflicts To Resolve

The current project should explicitly converge on the following cleanup targets.

### 1. Branch vs Scope

These should not remain competing first-class terms in the main design language.

Target:

- use `branch` as the main term
- keep `scope` only where legacy implementation detail still requires it

### 2. Variant vs History

`variant` should remain the live content entity.

`history` should remain a read perspective over content evolution.

Target:

- do not let history semantics redefine variant identity

### 3. Replace Preview vs Execute

Preview and execute must describe the same semantic change.

Target:

- preview must show what bindings will actually change
- preview must not reduce the operation to key-set comparison when binding replacement is the real effect

### 4. Pivot as Parallel System

Pivot should not grow into a competing top-level model.

Target:

- keep pivot attached to variant state
- describe pivot review as a constrained variant state transition

## Success Criteria

The design is successful when all of the following are true:

- the team can answer what content is, what chooses content, and what workflow state belongs to content without switching vocabularies
- branch writes can be explained as either content mutation or binding mutation
- replace and pivot workflows do not introduce new core concepts
- read and write design both derive from the same domain model

## Recommended Next Step

Use this design as the basis for a formal implementation plan. The implementation plan should follow the phase order in this document rather than starting from individual workflows.
