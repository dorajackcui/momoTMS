# File Name Source.Name Design

## Status

- drafted on 2026-05-07
- approach selected in discussion: make `file_name` a business field read from `Source.Name`

## Purpose

Correct the current model drift where `file_name` is treated as the physical
import workbook name or upload-relative path. In the actual business workbook,
`file_name` is the value from the Excel `Source.Name` column. It should sit at
the same semantic level as other non-content metadata fields such as remarks,
not at the level of import transport metadata.

## Problem Statement

The runtime currently conflates two different concepts:

- `import_rows.file_path`: the relative path of the uploaded or staged workbook
- `variants.file_name`: a business field carried by a variant

Several import paths write the physical workbook path into `payload.file_name`
and then into `variants.file_name`. This makes imported file names look like
variant content and causes later branch and variant views to show upload
transport details instead of the business value from `Source.Name`.

The docs also describe `file_name` as path-derived runtime metadata, which
reinforces the wrong behavior.

## Core Decision

`file_name` remains a variant field, but its source is the workbook sheet column
`Source.Name`.

`file_name` is not:

- the uploaded workbook filename
- the upload-relative file path
- derived from `import_rows.file_path`
- a project fixed column like `business_key` or `source`

`file_name` is:

- a non-content business field
- normalized with the same trimmed non-content normalization as remarks
- sparse during imports and workbook workflows
- shown in variant read models as the persisted business value

## Field Mapping

`Source.Name` is the default workbook header for `file_name`.

Classic import preview and mapping should expose `file_name` as an optional
mapping target next to translation and remark fields. A mapping override may
point `file_name` to another workbook header, but no mapping is required.

Workbook workflow intake should auto-detect `Source.Name` and include
`file_name` in row payloads only when that header exists.

Bulk seed should read `Source.Name` when present. When the column is absent,
new variants should store an empty `file_name` value instead of using the
physical workbook path.

## Sparse Semantics

`file_name` follows the same sparse patch semantics as remarks:

- missing or unmapped `Source.Name` means "do not update the current
  `file_name` value"
- a mapped blank `Source.Name` cell means "set `file_name` to an empty string"
- new variants created from rows without mapped `file_name` store an empty
  string

Bootstrap must not use `row["file_path"]` as a fallback when creating bare
variants. If bootstrap creates a new variant and the row did not provide
`file_name`, the new variant's `file_name` is empty.

## Data Flow

### Classic Import

1. Preview reads workbook headers and suggests `Source.Name` for optional
   `file_name` mapping when present.
2. Confirm import persists each row with:
   - `file_path` as upload-relative transport metadata
   - `payload.file_name` only when the `file_name` mapping is present
3. Import-batch mutation merges `payload.file_name` only when the key is present.

### Workbook Workflow Intake

1. Parser resolves required project headers for `business_key` and `source`.
2. Parser resolves optional `Source.Name` for `file_name`.
3. Workbook batch persistence writes `payload.file_name` only when the parser
   found the column.
4. Content mutation preserves existing `file_name` when the payload omits it,
   and updates it when the payload includes it.
5. Range mutation and bootstrap create new variants with the provided
   `file_name`, or with an empty value when omitted.

### Bulk Seed

Bulk seed is an initialization helper, so it creates variants directly. It
should read `Source.Name` when present and otherwise use an empty value.

## Documentation Updates

The stable runtime docs should be corrected in the same implementation change:

- `docs/system.md`: schema and variant descriptions must stop calling
  `file_name` path-derived metadata.
- `docs/workflows.md`: normalization, project template, import, workbook
  workflow, bootstrap, and sparse patch rules must state that `file_name`
  comes from `Source.Name`.

`docs/workflows.md` is the owner doc for the detailed Excel and import behavior.

## Tests

Focused regression coverage should include:

- classic import persists `payload.file_name` from `Source.Name`
- classic import omits `payload.file_name` when `Source.Name` is absent
- workbook batch persists `payload.file_name` from `Source.Name`
- workbook content mutation preserves existing `file_name` when `Source.Name`
  is absent
- workbook content mutation clears `file_name` when `Source.Name` is mapped but
  blank
- bootstrap-created bare variants do not fall back to `file_path`
- bulk seed reads `Source.Name` and does not fall back to workbook filename
- docs validation after active docs are updated

## Non-Goals

- Do not rename public report fields such as `file_path`; those remain useful
  import-tracking metadata.
- Do not add old-database migration compatibility. Current local databases may
  be reset or reseeded under the repo's normal compatibility boundary.
- Do not make `file_name` part of canonical same-source identity. The canonical
  same-source rule remains entry plus normalized `source`.
