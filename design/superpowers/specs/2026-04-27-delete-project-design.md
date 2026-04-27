# Delete Project

## Summary

Add the ability to delete a project from the HubPage. Deletion is permanent (hard delete) and requires the user to type the project name as confirmation, following the GitHub repo-deletion pattern. Any project is deletable, including the default project.

## Backend

### Endpoint

`DELETE /api/projects/{project_id}`

- Request body: `{ "name": "<project_name>" }` — server validates the name matches the project's actual name
- Success: `200` with `{ "deleted": true, "project_id": <id>, "name": "<name>" }`
- Name mismatch: `400`
- Project not found: `404`

### Service Method

`ProjectService.delete_project(project_id, name)` — single transaction, explicit ordered deletion:

1. Load project, validate it exists and name matches
2. `DELETE FROM scope_bindings` where variant belongs to project entries
3. `DELETE FROM variant_translations` where variant belongs to project entries
4. `DELETE FROM variant_remarks` where variant belongs to project entries
5. `DELETE FROM variants` where entry belongs to project
6. `DELETE FROM entries WHERE project_id = ?`
7. `DELETE FROM import_rows` where import belongs to project
8. `DELETE FROM imports WHERE project_id = ?`
9. `DELETE FROM jobs WHERE project_id = ?`
10. `DELETE FROM dev_versions WHERE project_id = ?`
11. `DELETE FROM project_schemas WHERE project_id = ?`
12. `DELETE FROM projects WHERE project_id = ?`

All deletions are strictly scoped by `project_id`. No cross-project data is affected. The existing database schema has no `ON DELETE CASCADE` on project foreign keys, so explicit ordered deletion is required.

### Schema

Add `DeleteProjectRequest` to `app/schemas.py`:

```python
class DeleteProjectRequest(BaseModel):
    name: str
```

Add `DeleteProjectResponse`:

```python
class DeleteProjectResponse(BaseModel):
    deleted: bool
    project_id: int
    name: str
```

## Frontend

### Confirmation Dialog

Located on HubPage. Each project card gets a delete icon button (top-right corner). Clicking it opens a confirmation panel:

- Warning: "This will permanently delete **{project name}** and all its data. This action cannot be undone."
- Input field: "Type the project name to confirm"
- Delete button: disabled until input matches project name exactly
- Cancel button: closes the panel

### API Layer

Add to `frontend/src/domains/projects/api.ts`:

```typescript
deleteProject(projectId: number, name: string): Promise<DeleteProjectResponse>
```

### Post-Deletion Behavior

- Invalidate the `projects()` query cache via `queryClient.invalidateQueries`
- If the deleted project was the currently selected project, clear `projectId` and navigate to `/app`
- The HubPage re-renders with the updated project list

## Testing

- Backend unit test: delete succeeds, name mismatch returns 400, not-found returns 404
- E2E: create a project, delete it with confirmation dialog, verify it disappears from the project list

## Scope Exclusions

- No soft-delete or undo functionality
- No schema migration (no `ON DELETE CASCADE` changes)
- No batch deletion
- No cleanup of orphaned job artifact files on disk (`data/jobs/`). DB rows are deleted; disk files become inert and can be cleaned up manually or in a future maintenance task.
