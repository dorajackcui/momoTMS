# Product Bootstrap

This file describes the bootstrap payload for the operator-facing product surface at `/app`.

## Route

- `GET /api/projects/{project_id}/state`

## Purpose

- primary bootstrap for `/app`
- project-scoped only
- no compatibility-only fields

## Response Shape

The response includes:

- `project`: selected project summary
- `schema`: translation and remark column definitions for the project
- `release_summary`: summary information for `rel/current`
- `candidate_dev_branch`: the current promote candidate, if any
- `dev_branches`: active dev branch metadata
- `imports`: recent import batch summaries
- `jobs`: recent job summaries

## Usage Rules

- `/app` should bootstrap and refresh from project-scoped APIs only
- frontend code should treat this payload as product state, not as a compatibility-shaped state blob
- project schema is fixed after project creation; bootstrap describes the current schema but does not imply schema-edit support

## Source Of Truth

- router: `app/routers/projects_state.py`
- service: `app/services/project/state.py`
- response model: `ProductStateResponse` in `app/schemas.py`
