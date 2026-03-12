# Domain Model

This file describes the business model the current runtime is built around.

## Project and Schema

Each project owns:

- entries
- variants
- scope bindings
- imports
- jobs
- one active schema definition

The schema contains:

- fixed columns: `business_key`, `source`
- translation columns: project-defined language keys such as `fr`, `en`
- remark columns: project-defined metadata keys such as `context`

`file_name` is runtime metadata derived from workbook path. It is not part of the user-defined schema.

## Entry

An `Entry` is the stable business slot.

- identity: `(project_id, business_key)`
- stores no translations directly
- can own multiple variants over time

## Variant

A `Variant` is the mutable content object under one entry.

Current identity rules:

- identity: `(project_id, business_key, source)` through the parent entry plus canonical `source`
- the runtime keeps one canonical non-trashed variant per `source` under an entry
- `file_name`, `translations`, and `remarks` are content, not identity

It stores:

- `file_name`
- `source`
- `translations`
- `remarks`
- lifecycle timestamps such as `orphaned_at`, `trashed_at`, `restored_at`

The target invariant is one canonical non-trashed variant per `source` under an entry. Incompatible local DBs are reset by schema rebuild instead of being repaired through old-data semantic migration.

## Scope Binding

A scope binding activates one variant for one entry in one scope.

Current scopes:

- `rel/current`
- `dev/<version>`

Rules:

- one scope can bind only one variant per entry
- different scopes may bind different variants for the same entry
- branch views and workflow reads operate on active bindings

## Variant Lifecycle

The runtime distinguishes three live states:

- `active`: referenced by at least one scope binding
- `orphan`: no active binding but still reusable for future same-source hits
- `trashed`: explicitly deleted from normal runtime usage

Implementation note:

- `retained` no longer exists as a lifecycle state, table, API, or UI surface

Default read behavior:

- overview, compare, queue, master query, fill, and QA use `active` variants only
- orphan and trashed variants are excluded from normal product reads

## Read Models

The product-facing read layer is projection-based, not table-shaped.

- `Branch Summary`: counts and status distribution for `rel/current` and active `dev/<version>` scopes
- `Branch Compare`: diff view for any two scopes, usually `rel/current` vs one dev scope
- `Translation Queue`: operational subset of compare rows for one target dev scope
- `Master Query`: exact lookup by `business_key` or exact `source`

Branch states:

- `aligned`
- `diverged`
- `base_only`
- `target_only`

Priority statuses used by compare/queue:

- `already_translated`
- `fillable`
- `needs_translation`
- `needs_review`
- `source_mismatch`
- `unmatched`

## Workflow Rules

### Import

- reads local `.xlsx` files
- skips temporary `~$*.xlsx` files
- validates required headers against project schema
- stores row-level results in `imports` and `import_rows`

### Scope Mutation

Branch writes are split by capability, not by `dev` / `rel` method names.

Input modes:

- `direct`: one or more business-key patches applied to a target scope
- `import_batch`: one persisted import batch applied to a target scope

Policy examples:

- `direct + rel/current` replaces the old rel hotfix behavior
- `direct + dev/<version>` supports single-row or batch dev patching
- `import_batch + dev/<version>` replaces the old dev import behavior
- `import_batch + rel/current` is invalid

Mutation rules:

- if `source` is omitted, mutation requires an existing binding in the target scope and updates the currently bound variant in place
- if `source` is provided and matches the currently bound variant, mutation updates that bound variant in place
- if `source` is provided and differs, mutation resolves or creates the target same-source canonical variant and rebinds the scope when needed
- `dev` policy keeps rel-owned canonical content authoritative when same-source hits a rel-bound variant
- `dev` policy may create missing entries when `source` is present
- `rel` policy always starts from the currently bound rel variant and never creates a missing business key from scratch

### Scope Sync

- previews and executes binding changes from one scope into another
- the live policy only supports `dev/<version> -> rel/current`
- sync rebinds active variants; it does not copy content or create variants
- execute runs in one DB transaction
- the `dev/<version> -> rel/current` policy still clears same-version-line dev bindings and marks those versions as promoted

### Trash / Restore

- delete is project-scoped and takes `scope_ref` plus `business_keys[]`
- delete removes the active binding in the selected scope
- if the affected variant no longer has any active bindings, lifecycle state refreshes it into `orphan` unless it is trashed
- restore is project-scoped and takes `variant_ids[]`
- restore clears trashed state for the selected variants only; it does not rebind scopes automatically

### Fill

- matches workbook rows by normalized `business_key + source`
- resolves actual content from active runtime bindings
- writes translations back to workbook artifacts through a job

### QA

- validates source/target content from workbook input
- uses project schema to locate columns
- remains a read-only validation workflow

## Branch Boundary

The runtime is branch-centric:

- `variant` is the only content identity
- `ScopeRef` is the branch identity exchanged across services and APIs
- project-scoped `/branches` routes are the public read surface plus mutation/sync write surface for branch workflows
