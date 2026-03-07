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

It stores:

- `file_name`
- `source`
- `translations`
- `remarks`
- lifecycle timestamps such as `orphaned_at`, `trashed_at`, `restored_at`

Multiple variants may exist under the same entry so different scopes can point at different content.

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

The runtime distinguishes four useful states:

- `active`: referenced by at least one scope binding
- `retained`: no active binding, but intentionally preserved for reuse
- `orphan`: no active binding and not retained
- `trashed`: explicitly deleted from normal runtime usage

Default read behavior:

- overview, compare, queue, master query, fill, and QA use `active` variants only
- retained, orphan, and trashed variants are excluded from normal product reads

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
- updates the currently bound dev variant in place when the target scope already owns the entry
- otherwise creates or reuses a compatible variant and rebinds the target dev scope
- can mark the imported version as candidate release

### Release Hotfix

- operates on the variant bound to `rel/current`
- active hotfix changes one translation field
- passive hotfix can update source, translations, remarks, and file metadata

### Promote

- previews and executes binding changes from one `dev/<version>` into `rel/current`
- moves release bindings to the variants currently bound by the target dev scope
- may clear old dev bindings inside the same version line

### Trash / Restore

- current compatibility flow still targets entries by `business_key`
- underlying lifecycle work happens at the variant/binding level

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
