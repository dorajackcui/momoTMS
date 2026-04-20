# Branch Infra Phase Map

## Purpose

- keep a durable multi-session roadmap for backend infra work around `entry`, `variant`, `branch`, and `pivot`
- record what has already been clarified, what still needs design work, and what order future sessions should follow
- reduce context loss when a new session starts

## Current Status

`Phase 1` is complete.

What is already clear:

- `entry` is the stable business slot
- `variant` is the content entity under one entry
- `branch` is the selection layer
- `pivot` is variant-local workflow state
- operator-facing reads should converge into `app/services/read_models`
- branch writes should converge around `app/services/branch`
- replace preview should describe real binding changes, not only key overlap

What is not fully closed yet:

- `create` and `update` flows for branches are not yet expressed as one unified infra contract
- preview capabilities are still only partially systematized
- `scope` compatibility still exists in the runtime and frontend contract surface
- lifecycle, pivot preview, and branch bootstrap flows still need an ordered design pass

## Working Principles

- design the backend in domain and infra order, not in ad hoc workflow order
- settle lower-layer invariants before higher-layer workflows
- separate content mutation from branch rebinding
- treat preview as a first-class operator contract, not as a best-effort hint
- keep `pivot` attached to variant state instead of letting it become a parallel model
- keep `branch` as the primary operator-facing term, with `scope` retained only where compatibility or selector machinery still needs it

## Phase Map

### Phase 1: Foundation Alignment

Status:

- complete

Goal:

- stabilize the core vocabulary and basic architectural direction

Outcomes:

- clarify `entry`, `variant`, `branch`, and `pivot`
- move operator-facing branch reads toward `read_models`
- add canonical branch-first rows and lookup routes
- make authority failures explicit in mutation results
- align replace preview with execute semantics
- update active docs to reflect the current branch foundation

Artifacts:

- foundation design spec
- branch foundation implementation plan
- code, tests, and docs aligned to the current model

### Phase 2: Authority Model

Status:

- complete

Goal:

- define a stable branch-to-branch authority policy

Questions to answer:

- what is the authority ordering between `rel/current` and `dev/x.y.z`
- how should authority compare between multiple dev branches
- when a variant is shared across multiple branches, who may mutate content
- which actions are authority-controlled content changes versus allowed rebinds

Completed decisions:

- authority protects only in-place edits on shared `translations + remarks`
- `source` change is variant resolution, not shared-content mutation
- branch ordering uses a system-level ordered candidate version-series list plus patch ordering within a series
- when a row resolves to an existing target variant, lower-authority branches may still bind or rebind to it but their requested content edit is filtered
- same-source authority bypass by auto-fork is not allowed
- orphan variants without any current bindings may be rebound and edited by the first branch that reuses them

Delivered outputs:

- explicit authority matrix
- stable status vocabulary for authority outcomes
- service-level rules that can be reused by later mutation work

Artifacts:

- [branch-authority-model.md](branch-authority-model.md): Phase 2 authority scope, ordering, matrix, and internal authority-filtered outcome vocabulary
- [branch-authority-implementation-plan.md](branch-authority-implementation-plan.md): execution plan used to land the Phase 2 runtime changes

Implementation result:

- branch mutation flows now preserve legal bind or rebind effects while filtering unauthorized shared-content edits
- mutation reporting now exposes filtered-content outcomes through row metadata and summary counts

### Phase 3: Branch Creation And Bootstrap

Status:

- not started

Goal:

- define how a branch is created and how its initial working surface is established

Questions to answer:

- is `dev/2.4.3` created explicitly or implicitly during import
- what is the canonical meaning of uploading a large `key + source` package to define the whole branch range
- should branch bootstrap be modeled as a dedicated workflow separate from ordinary mutation
- how should later uploads that add translations or remarks merge into the bootstrapped branch
- what branch metadata is created at bootstrap time

Target outputs:

- branch bootstrap model
- clear API or workflow contract for branch creation
- consistent semantics for sparse follow-up uploads

Session focus:

- design the operator flow for building a new dev branch from an initial source-only package, then layering translations afterward

### Phase 4: Mutation Contract

Status:

- partially clarified, not fully closed

Goal:

- define one coherent write contract for branch-scoped changes

Questions to answer:

- what exactly counts as content mutation
- what exactly counts as rebinding
- when does a write create a new variant
- when does a write bind an existing variant
- what result types should be reported for direct and import-batch writes

Target outputs:

- mutation result matrix
- shared semantics across `direct` and `import_batch`
- explicit distinction between create, update, bind, rebind, noop, and forbidden outcomes

Session focus:

- take a set of representative write scenarios and normalize them into one result taxonomy

### Phase 5: Preview System

Status:

- not started as a unified design

Goal:

- define preview as a consistent operator contract across workflows

Questions to answer:

- what is the common preview row shape
- which previews describe content change versus binding change
- how should bootstrap import preview differ from mutation preview
- what should pivot preview show
- how should preview results line up with job reports and execute summaries

Target outputs:

- preview design family
- stable status names and count fields
- consistency rules between preview and execute

Session focus:

- align bootstrap preview, mutation preview, replace preview, and pivot preview into one conceptual family

### Phase 6: Branch-To-Branch Operations

Status:

- partially implemented, not fully generalized

Goal:

- define higher-order operations between branches without inventing new core concepts

Questions to answer:

- what is the exact semantic difference between replace and promote
- which branch pairs are valid for these operations
- how authority should constrain branch-to-branch operations
- how cleanup and candidate-release behavior fit into the same model

Target outputs:

- stable replace/promote semantics
- clear policy restrictions for allowed source and target branch pairs
- consistent preview and execute behavior

Session focus:

- turn branch-to-branch operations into policy-specialized rebinding workflows

### Phase 7: Pivot Workflow And Preview

Status:

- partially present, not fully systematized

Goal:

- complete the pivot layer without letting it become a separate top-level model

Questions to answer:

- what pivot preview should display
- how pivot state changes relate to branch visibility
- how pivot review authority relates to branch authority
- what the operator-facing review flow should look like for changed variants

Target outputs:

- pivot preview contract
- pivot review state transition rules
- integration points between pivot workflow and branch authority

Session focus:

- keep pivot grounded as variant-local workflow state and finish the remaining preview/review semantics

### Phase 8: Lifecycle And Recovery

Status:

- partially modeled, not fully closed

Goal:

- finish the lifecycle story for active, orphan, trashed, and restored variants

Questions to answer:

- exactly when a variant becomes orphan
- when delete should trash versus only unbind
- what restore brings back and what it does not
- how replace, bootstrap, and cleanup flows should refresh lifecycle state

Target outputs:

- finalized lifecycle rules
- clear recovery semantics
- cleanup expectations for batch workflows

Session focus:

- validate lifecycle semantics against branch bootstrap, mutation, and replace flows

### Phase 9: Contract Convergence

Status:

- final tightening phase

Goal:

- converge code, docs, frontend, and compatibility layers onto the intended long-term shape

Questions to answer:

- when the frontend should switch from scope aliases to canonical branch-first routes
- how long compatibility aliases should stay
- which workflow responsibilities should remain in `workflows/` versus move into more stable branch or read-model layers
- which docs should graduate from design notes into stable runtime guidance

Target outputs:

- reduced compatibility surface
- cleaner service boundaries
- final contract alignment across backend, frontend, docs, and tests

Session focus:

- do the final convergence work only after the lower-layer policies and contracts are already stable

## Recommended Session Order

1. Phase 3: Branch Creation And Bootstrap
2. Phase 4: Mutation Contract
3. Phase 5: Preview System
4. Phase 6: Branch-To-Branch Operations
5. Phase 7: Pivot Workflow And Preview
6. Phase 8: Lifecycle And Recovery
7. Phase 9: Contract Convergence

## Why This Order

- authority must be defined before mutation semantics are finalized
- branch creation must be defined before import- and upload-based workflows can be made canonical
- mutation should be stable before preview families are generalized
- replace and promote should be expressed on top of branch and mutation rules, not before them
- pivot should plug into a stable variant and branch model
- lifecycle should be checked against real workflows after the main write semantics are known
- frontend and compatibility convergence should happen after the backend contracts stop moving

## Suggested Next Session

Start with `Phase 3: Branch Creation And Bootstrap`.

Concrete goal for that session:

- define how a dev branch is created or bootstrapped
- settle the semantic meaning of an initial branch-wide `key + source` upload
- decide what branch metadata and follow-up merge rules bootstrap must establish

Success condition:

- after that session, the project should have a stable bootstrap contract that later mutation and preview work can build on

## Simple Memory Hook

If a future session needs a quick restart point, use this sentence:

`Phase 1 and Phase 2 are done; next define branch bootstrap before mutation, preview, pivot, and lifecycle are expanded.`
