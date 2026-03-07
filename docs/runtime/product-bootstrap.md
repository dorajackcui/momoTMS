# Product Bootstrap

This file describes the bootstrap payload for the operator-facing product surface at `/app`.

## Route

- `GET /api/projects/{project_id}/state`

## Purpose

- Primary bootstrap for `/app`
- Project-scoped only
- No compatibility-only fields

## Response Shape

The response includes:

- `project`
- `schema`
- `rel_summary`
- `candidate_dev_version`
- `dev_versions`
- `imports`
- `jobs`

The response does not include:

- `trash_count`
- `samples`

Those fields are reserved for the compatibility bootstrap at `GET /api/state`.

## Usage Rules

- `/app` should bootstrap and refresh from project-scoped APIs only.
- Frontend code should treat this payload as product state, not as a compatibility-shaped state blob.
- Project schema is fixed after project creation; bootstrap describes the current schema but does not imply schema-edit support.

## Source Of Truth

- Router: `app/routers/projects_state.py`
- Service: `app/services/project/state.py`
- Response model: `ProductStateResponse` in `app/schemas.py`
