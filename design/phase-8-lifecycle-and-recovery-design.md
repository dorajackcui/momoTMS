# Phase 8: Lifecycle And Recovery Design

## Goal

Redesign the variant lifecycle model around three terminal-aware states (active, orphan, trashed) so that:

- **Trash** means removed from the project: no fill, no read_models, no participation in any live system query
- **Orphan** is a first-class virtual branch (`BranchRef.orphan()`): the computed set of all variants with zero real branch bindings, still live, still participates in fill and read_models
- Branch delete becomes pure unbind (last binding produces orphan, not trash)
- Project trash is a separate explicit operation targeting orphan variants only
- No variant-level restore or cleanup

## Lifecycle State Model

Three states with strict definitions:

| State | Bindings | `trashed_at` | Fill | Read Models | Scope |
|-------|----------|--------------|------|-------------|-------|
| **Active** | >= 1 real branch | NULL | Yes | Yes | Real branch(es) |
| **Orphan** | 0 | NULL | Yes | Yes | `BranchRef.orphan()` |
| **Trashed** | 0 | SET | No | No | None |

### State Resolution

Same logic as current `_resolve_state()`:

1. `trashed_at` is not NULL -> **trashed**
2. Has bindings -> **active**
3. Otherwise -> **orphan**

### Allowed Transitions

```
active ──last binding removed──> orphan ──explicit project trash──> trashed
  |                                 ^
  |                                 |
  +──binding removed but others──>  |  (stays active)
                                    |
  orphan ──new binding created──> active  (via mutation or bootstrap reuse)
```

- **Active -> Orphan**: last real binding removed (via branch delete, replace, or any unbind operation)
- **Active -> Active**: binding removed but other bindings remain
- **Orphan -> Active**: new binding created (via mutation same-source reuse, bootstrap same-source reuse)
- **Orphan -> Trashed**: explicit project trash operation
- **Trashed is terminal**: no restore, no cleanup, no way back

### Key Change From Current Behavior

Trashed variants are completely excluded from fill and all read models. The current behavior where fill falls back to trashed history as a last resort is removed.

## Branch Delete (Unbind)

### What It Is

The branch-scoped "remove entries from my branch" operation. Replaces the current trash/delete auto-trash behavior.

### API Shape

Same as current: `POST /api/projects/{project_id}/variants/trash/delete` with `{ branch_ref, business_keys[] }`.

The route path can be renamed later in Phase 9 contract convergence. The behavior changes now.

### Behavior Change

- Current: unbind -> if last binding, auto-trash the variant
- New: unbind -> if last binding, variant becomes orphan (not trashed)

### Authority

No authority check. An operator can always unbind entries from their own branch. Authority protects content mutation, not binding removal.

### Report Statuses

| Status | Meaning |
|--------|---------|
| `REMOVED_BINDING` | Binding removed, variant still active in other branches |
| `ORPHANED_VARIANT` | Last binding removed, variant enters orphan state (was `TRASHED_VARIANT`) |
| `NOT_BOUND_IN_SCOPE` | Entry not bound in this branch |
| `MISSING` | Business key not found |

### Summary Fields

- `orphaned_variant_count` (was `trashed_variant_count`)
- `removed_binding_count` (unchanged)
- `not_bound_count` (unchanged)
- `missing_count` (unchanged)

## Project Trash

### What It Is

Project-scoped operation that permanently removes orphan variants from the live system. Only orphan variants (zero bindings) can be trashed.

### API Shape

`POST /api/projects/{project_id}/variants/trash` with `{ business_keys[] }`

No `branch_ref` needed. This operates on orphan variants only.

### Behavior

For each `business_key`:

1. Find the entry in the project
2. Find non-trashed variants under that entry with zero bindings (orphans)
3. Set `trashed_at` on each orphan variant
4. If the variant is active (has bindings), report as `NOT_ORPHAN` and skip

### Report Statuses

| Status | Meaning |
|--------|---------|
| `TRASHED` | Orphan variant successfully trashed |
| `NOT_ORPHAN` | Variant has active bindings, cannot be project-trashed |
| `NO_ORPHAN_FOUND` | Entry exists but has no orphan variant |
| `MISSING` | Business key not found |

### Summary Fields

- `trashed_count`
- `not_orphan_count`
- `no_orphan_found_count`
- `missing_count`

### No Preview

Project trash does not have an effect_forecast preview. It is a simple, direct operation.

### No Authority Check

Project trash is a project-level admin action. No branch authority applies.

## BranchRef.orphan() Computed Scope

### Approach

Orphan is a query-time computed scope. No rows in `scope_bindings`. The read model detects orphans by the absence of bindings. This is Approach A (Computed Scope), chosen over synthetic binding or separate query path approaches.

### BranchRef Model Change

- Add `BranchRef.orphan()` class method (like `BranchRef.rel_current()` and `BranchRef.dev(...)`)
- String representation: `"orphan"`
- `BranchRef.parse("orphan")` returns orphan ref
- Orphan ref is not a writable branch: mutations, bootstrap, and replace cannot target it

### Read Model Integration

- When scope is `BranchRef.orphan()`, the scope-members query returns all variants with zero bindings and `trashed_at IS NULL`
- The query uses `LEFT JOIN scope_bindings ... WHERE sb.scope_ref IS NULL AND v.trashed_at IS NULL` instead of the normal binding lookup
- Hydration follows the same path as other scopes; `_resolve_state()` returns `"orphan"` for these variants
- Pagination, filtering, and sorting work the same as for real branches

### Where Orphan Scope Appears

- Scope catalog reads: `GET /api/projects/{project_id}/branches/orphan/members`
- Project variants workspace: can filter by orphan state
- Branch summary: includes orphan as a pseudo-branch entry with variant count

### Where Orphan Scope Does NOT Appear

- Branch mutation, bootstrap, replace: orphan is not a writable scope
- Branch authority: orphan has no authority level
- Dev versions metadata: orphan is not a dev branch

## Fill And Read Model Changes

### Fill Changes

- Current: fill matches against all recorded variants, prefers non-trashed, falls back to trashed
- New: fill matches against live variants only (active + orphan). Trashed variants are completely excluded from fill candidate lookup
- `match_variant_state` in fill report: keeps `"active"` and `"orphan"`, removes `"trashed"` as a possible value

### Read Model Changes

| Read model component | Current behavior | New behavior |
|---|---|---|
| Live variants dataset | Filters `trashed_at IS NULL` | No change needed |
| Same-source candidate lookup | Includes trashed | Exclude trashed |
| Entry timeline / inspection | Shows trashed variants | Exclude trashed |
| Master scope | Already excludes trashed | No change needed |
| Scope catalog reads | Already scoped to bindings | No change needed |
| Variants workspace | Already includes orphans | No change needed |

### New: Orphan in Read Models

- Scope catalog for `BranchRef.orphan()`: new query path (computed, LEFT JOIN)
- Branch summary: add orphan as a pseudo-branch entry with variant count

## Existing API Migration

### Endpoint Changes

| Current Endpoint | Current Behavior | New Behavior |
|---|---|---|
| `POST .../variants/trash/delete` | Unbind + auto-trash on last | Unbind only, orphan on last binding removal |
| `POST .../variants/trash/restore` | Restore trashed -> orphan | Remove (no restore in new model) |
| `GET .../orphan-variants` | Inspection endpoint | Kept, now also served via `BranchRef.orphan()` scope catalog |

### New Endpoint

| Endpoint | Behavior |
|---|---|
| `POST .../variants/trash` | Project trash: trash orphan variants by business_keys |

## Orphan Rebinding

No new direct rebind-from-orphan operation is added. Existing indirect paths are sufficient:

- **Branch mutation**: if a mutation row has `business_key + source` matching an orphan, the system reuses the orphan variant and binds it to the actor branch (the `reuse_existing` variant resolution path)
- **Branch bootstrap**: same pattern; import rows matching an orphan's source cause it to be rebound to the dev branch

## Edge Cases And Invariants

### Pivot Status

- Orphan variants preserve their `pivot_status` (`init`, `changed`, or `reviewed`). When rebound via mutation, the pivot status is already correct.
- Trashed variants: pivot status becomes irrelevant since the variant is excluded from everything. No need to clear it; `trashed_at` is the gate.

### Same-Source Canonical Invariant

- Current unique constraint: `(entry_id, source) WHERE trashed_at IS NULL`
- No change needed. Orphan variants are non-trashed, so the invariant still holds: one live variant per source per entry.

### Replace Interaction

- Replace clears target bindings and copies source bindings. Variants that lose their last binding become orphan. This is already correct via `refresh_orphan_states()`. No change to replace logic itself.

### Bootstrap Interaction

- Bootstrap binds variants to a dev branch. Same-source reuse may rebind orphan variants. Already correct via existing same-source resolution. No change needed.

### Mutation Interaction

- Mutation may rebind orphan variants through same-source resolution. Already correct. No change needed.

## Success Conditions

1. Branch delete (unbind) produces orphan instead of trashed when the last binding is removed
2. Project trash is a separate explicit operation that only targets orphan variants
3. Trashed variants are excluded from fill completely (no fallback)
4. Trashed variants are excluded from same-source candidate lookup and entry inspection
5. `BranchRef.orphan()` is a readable computed scope with full read model integration
6. Orphan scope appears in branch summary with variant count
7. Restore endpoint is removed
8. All existing branch operations (replace, bootstrap, mutation) correctly produce orphans when bindings are lost
9. No existing behavior is changed for active variants
10. Same-source canonical invariant is preserved
