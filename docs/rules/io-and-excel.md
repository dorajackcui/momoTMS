# IO and Excel Rules

This file captures the stable normalization and workbook-processing rules used by import, fill, and QA.

## Normalization Helpers

Implemented in `app/services/shared/io.py`.

### `safe_to_str(value, strip=True)`

Rules:

- `None` becomes `""`
- non-string values are converted with `str(value)`
- `strip=True` trims leading and trailing whitespace
- `strip=False` preserves surrounding whitespace

### `is_blank_value(value)`

Blank is true only when:

- `value is None`
- `value` is a string whose trimmed value is empty

Blank is false for values like `0`, `0.0`, and `float("nan")`.

## Field Normalization Policy

Different columns use different normalization rules.

- non-content fields use trimmed normalization
- translation content preserves surrounding whitespace

Non-content fields:

- `business_key`
- `source`
- `file_name`
- remark columns

Content fields:

- all project translation columns

## Project Template Rules

Project schema defines:

- fixed columns: `business_key`, `source`
- translation columns
- remark columns

Header matching is schema-driven.

- `business_key` and `source` are required
- every configured translation column is required
- every configured remark column is required
- `file_name` is derived from workbook relative path, not from a sheet column

Preview and guided mapping are implemented by `ProjectService.preview_headers()` and `ProjectService.resolve_headers()`.

## Import Rules

Implemented mainly in `app/services/imports/service.py`.

- read only `.xlsx` files
- skip temporary files whose names start with `~$`
- each sheet uses row `1` as header row
- rows missing normalized `business_key` are invalid
- rows missing normalized `source` are invalid
- import results are persisted row by row in `import_rows`
- upload preview is sheet-based and returns suggested mappings per sheet

## Fill Rules

Fill uses normalized `business_key + source` as the row match key.

Rules:

- both values are normalized as non-content fields
- if either value becomes empty, the row is not a valid fill candidate
- runtime content still comes from active scope bindings, not from workbook rows alone

Implication:

- `business_key + source` is a fill-match key
- it is not the identity of an entry
- it is not the identity of a variant

## QA Rules

QA is schema-driven and read-only.

- it reads source and selected target language columns from the workbook
- it validates row-level source/target content
- it does not mutate runtime scope bindings

## Stability Notes

These rules are part of the stable project contract and should be preserved across refactors.

If import or fill behavior changes, update this document and `app/services/shared/io.py` together.
