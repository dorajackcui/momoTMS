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

### Dev Import

- creates missing entries
- looks up canonical variants by `same business_key + same source` across all non-trashed variants under the entry
- if the hit is rel-bound, it only binds the target `dev/<version>` scope and keeps canonical content unchanged
- if the hit is non-rel active or orphan, it updates canonical content in place and binds the target `dev/<version>` scope
- if no same-source variant exists, it creates a new canonical variant and binds the target `dev/<version>` scope
- can mark the imported version as candidate release

### Release Hotfix

- operates on the variant bound to `rel/current`
- active hotfix changes one translation field
- passive hotfix with unchanged `source` updates the current rel canonical variant in place
- passive hotfix with changed `source` looks up or creates the target same-source canonical variant, updates its content, and rebinds `rel/current`
- when rel moves away from a variant and no other scope still uses it, that old variant becomes `orphan`

### Promote

- previews and executes binding changes from one `dev/<version>` into `rel/current`
- moves release bindings to the variants currently bound by the target dev scope
- does not copy content or create variants
- may clear old dev bindings inside the same version line

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

## Compatibility Boundary

Two APIs still expose old string-shaped views:

- `app/services/variant/compatibility.py`
- `app/services/variant/facade.py`

They exist to support validation routes and compatibility callers. New behavior should live in split domain services and repositories under `app/services/variant/`.
