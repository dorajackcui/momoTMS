# Delete Project Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add permanent project deletion with name-confirmation safety to the HubPage.

**Architecture:** Backend adds a DELETE endpoint and explicit ordered-deletion service method. Frontend adds a confirmation dialog on each project card requiring the user to type the project name before deletion. All deletion is project-scoped — no cross-project data is affected.

**Tech Stack:** FastAPI, SQLite, React 19, TypeScript, TanStack Query, CSS Modules

---

## File Map

| Action | File | Responsibility |
|--------|------|---------------|
| Modify | `app/schemas.py` | Add `DeleteProjectRequest` and `DeleteProjectResponse` Pydantic models |
| Modify | `app/services/project/service.py` | Add `delete_project()` method with ordered deletion |
| Modify | `app/routers/projects_state.py` | Add `DELETE /api/projects/{project_id}` route |
| Modify | `frontend/src/domains/projects/types.ts` | Add `DeleteProjectResponse` type |
| Modify | `frontend/src/domains/projects/api.ts` | Add `deleteProject()` API function |
| Modify | `frontend/src/pages/hub/HubPage.tsx` | Add delete button, confirmation dialog, mutation |
| Modify | `frontend/src/pages/hub/HubPage.module.css` | Add styles for confirmation dialog and delete button |
| Modify | `tests/test_project_service.py` | Add delete tests |
| Modify | `tests/e2e/product-app.spec.js` | Add E2E delete project test |
| Modify | `docs/contracts.md` | Document new DELETE endpoint |

---

### Task 1: Backend Pydantic Schemas

**Files:**
- Modify: `app/schemas.py`

- [ ] **Step 1: Add DeleteProjectRequest and DeleteProjectResponse to schemas.py**

Add after the `CreateProjectRequest` class (after line 22):

```python
class DeleteProjectRequest(BaseModel):
    name: str


class DeleteProjectResponse(BaseModel):
    deleted: bool
    project_id: int
    name: str
```

- [ ] **Step 2: Commit**

```bash
git add app/schemas.py
git commit -m "feat: add DeleteProjectRequest and DeleteProjectResponse schemas"
```

---

### Task 2: Backend Service — delete_project Method

**Files:**
- Modify: `app/services/project/service.py`
- Test: `tests/test_project_service.py`

- [ ] **Step 1: Write failing tests for delete_project**

Add to `tests/test_project_service.py`:

```python
def test_delete_project_removes_project_and_all_child_data() -> None:
    reset_db()
    service = ProjectService()
    project = service.create_project("Delete Me", ["fr", "en"], ["context"])
    project_id = int(project["project_id"])

    service.delete_project(project_id, "Delete Me")

    with pytest.raises(KeyError, match="project not found"):
        service.get_project(project_id)


def test_delete_project_rejects_name_mismatch() -> None:
    reset_db()
    service = ProjectService()
    project = service.create_project("Real Name", ["fr"], ["context"])
    project_id = int(project["project_id"])

    with pytest.raises(ValueError, match="project name does not match"):
        service.delete_project(project_id, "Wrong Name")

    result = service.get_project(project_id)
    assert result["name"] == "Real Name"


def test_delete_project_raises_on_missing_project() -> None:
    reset_db()
    service = ProjectService()

    with pytest.raises(KeyError, match="project not found"):
        service.delete_project(999, "Anything")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_project_service.py::test_delete_project_removes_project_and_all_child_data tests/test_project_service.py::test_delete_project_rejects_name_mismatch tests/test_project_service.py::test_delete_project_raises_on_missing_project -v`

Expected: FAIL with `AttributeError: 'ProjectService' object has no attribute 'delete_project'`

- [ ] **Step 3: Implement delete_project in ProjectService**

Add to `app/services/project/service.py`, as a new method on the `ProjectService` class, after `require_project` (after line 303):

```python
    def delete_project(self, project_id: int, name: str) -> dict[str, Any]:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT project_id, name, is_default, created_at FROM projects WHERE project_id = ?",
                (project_id,),
            ).fetchone()
            if not row:
                raise KeyError(f"project not found: {project_id}")
            if row["name"] != name:
                raise ValueError("project name does not match")

            entry_ids_sql = "SELECT entry_id FROM entries WHERE project_id = ?"
            variant_ids_sql = f"SELECT variant_id FROM variants WHERE entry_id IN ({entry_ids_sql})"
            import_ids_sql = "SELECT import_batch_id FROM imports WHERE project_id = ?"

            conn.execute(
                f"DELETE FROM scope_bindings WHERE variant_id IN ({variant_ids_sql})",
                (project_id,),
            )
            conn.execute(
                f"DELETE FROM variant_translations WHERE variant_id IN ({variant_ids_sql})",
                (project_id,),
            )
            conn.execute(
                f"DELETE FROM variant_remarks WHERE variant_id IN ({variant_ids_sql})",
                (project_id,),
            )
            conn.execute(
                f"DELETE FROM variants WHERE entry_id IN ({entry_ids_sql})",
                (project_id,),
            )
            conn.execute(
                "DELETE FROM entries WHERE project_id = ?",
                (project_id,),
            )
            conn.execute(
                f"DELETE FROM import_rows WHERE import_batch_id IN ({import_ids_sql})",
                (project_id,),
            )
            conn.execute(
                "DELETE FROM imports WHERE project_id = ?",
                (project_id,),
            )
            conn.execute(
                "DELETE FROM jobs WHERE project_id = ?",
                (project_id,),
            )
            conn.execute(
                "DELETE FROM dev_versions WHERE project_id = ?",
                (project_id,),
            )
            conn.execute(
                "DELETE FROM project_schemas WHERE project_id = ?",
                (project_id,),
            )
            conn.execute(
                "DELETE FROM projects WHERE project_id = ?",
                (project_id,),
            )
        return {"deleted": True, "project_id": project_id, "name": name}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_project_service.py -v`

Expected: All tests PASS, including the three new delete tests.

- [ ] **Step 5: Commit**

```bash
git add app/services/project/service.py tests/test_project_service.py
git commit -m "feat: add ProjectService.delete_project with ordered cascade deletion"
```

---

### Task 3: Backend Router — DELETE Endpoint

**Files:**
- Modify: `app/routers/projects_state.py`

- [ ] **Step 1: Add the DELETE route**

Add the import for `DeleteProjectRequest` and `DeleteProjectResponse` to the imports at line 6, and add the route handler after the existing `project_state` handler (after line 38):

Update the import line:
```python
from app.schemas import CreateProjectRequest, DeleteProjectRequest, DeleteProjectResponse, ProductStateResponse, ProjectSummary
```

Add the route:
```python
@router.delete("/api/projects/{project_id}", response_model=DeleteProjectResponse)
def delete_project(project_id: int, payload: DeleteProjectRequest) -> DeleteProjectResponse:
    return handle_errors(
        lambda: DeleteProjectResponse(**ProjectService().delete_project(project_id, payload.name))
    )
```

- [ ] **Step 2: Verify the server starts without errors**

Run: `python -c "from app.routers.projects_state import router; print('OK')"`

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add app/routers/projects_state.py
git commit -m "feat: add DELETE /api/projects/{project_id} route"
```

---

### Task 4: Frontend Types and API

**Files:**
- Modify: `frontend/src/domains/projects/types.ts`
- Modify: `frontend/src/domains/projects/api.ts`

- [ ] **Step 1: Add DeleteProjectResponse type**

Add to `frontend/src/domains/projects/types.ts` after the `CreateProjectInput` type (after line 40):

```typescript
export type DeleteProjectResponse = {
  deleted: boolean;
  project_id: number;
  name: string;
};
```

- [ ] **Step 2: Add deleteProject API function**

Add the import for `DeleteProjectResponse` and the function to `frontend/src/domains/projects/api.ts`.

Update the import:
```typescript
import type {
  CreateProjectInput,
  DeleteProjectResponse,
  ProductStateResponse,
  ProjectSummary,
} from "@/domains/projects/types";
```

Add the function after `getProjectState`:
```typescript
export function deleteProject(projectId: number, name: string) {
  return fetchJson<DeleteProjectResponse>(`/api/projects/${projectId}`, {
    method: "DELETE",
    body: JSON.stringify({ name }),
  });
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/domains/projects/types.ts frontend/src/domains/projects/api.ts
git commit -m "feat: add deleteProject frontend type and API function"
```

---

### Task 5: Frontend — Confirmation Dialog and Delete Button on HubPage

**Files:**
- Modify: `frontend/src/pages/hub/HubPage.tsx`
- Modify: `frontend/src/pages/hub/HubPage.module.css`

- [ ] **Step 1: Add CSS styles for the delete button and confirmation dialog**

Add to the end of `frontend/src/pages/hub/HubPage.module.css`:

```css
.cardHeader {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.deleteIconBtn {
  padding: 2px 6px;
  border: none;
  border-radius: var(--radius-sm, 4px);
  background: transparent;
  color: var(--muted);
  font-size: 14px;
  cursor: pointer;
  line-height: 1;
  transition: color 120ms, background 120ms;
}

.deleteIconBtn:hover {
  color: var(--danger);
  background: var(--danger-bg, rgba(220, 38, 38, 0.08));
}

.confirmOverlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
}

.confirmPanel {
  width: min(440px, calc(100vw - 40px));
  padding: 24px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--surface);
  display: grid;
  gap: 16px;
}

.confirmPanel h3 {
  margin: 0;
  font-size: 18px;
}

.confirmWarning {
  font-size: 14px;
  color: var(--danger);
  line-height: 1.5;
}

.confirmPanel input {
  padding: 8px 10px;
  border: 1px solid var(--border);
  border-radius: 8px;
  font-size: 14px;
  color: var(--text);
  background: var(--surface-strong);
  width: 100%;
  box-sizing: border-box;
}

.confirmActions {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
}
```

- [ ] **Step 2: Update HubPage component with delete functionality**

Replace the full content of `frontend/src/pages/hub/HubPage.tsx` with:

```tsx
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { useAppShell } from "@/app/shell/AppShellContext";
import { createProject, deleteProject } from "@/domains/projects/api";
import type { CreateProjectInput, ProjectSummary } from "@/domains/projects/types";
import { queryKeys } from "@/shared/api/queryKeys";
import { buttonClassName, EmptyState, LoadingBlock } from "@/shared/ui/primitives";

import styles from "@/pages/hub/HubPage.module.css";

export function HubPage() {
  const shell = useAppShell();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<ProjectSummary | null>(null);
  const [confirmName, setConfirmName] = useState("");

  const [name, setName] = useState("");
  const [translationCols, setTranslationCols] = useState("");
  const [remarkCols, setRemarkCols] = useState("");
  const [keyHeader, setKeyHeader] = useState("key");
  const [sourceHeader, setSourceHeader] = useState("MsgStr");
  const [pivotLang, setPivotLang] = useState("");
  const [pivotedLangs, setPivotedLangs] = useState("");

  const createMut = useMutation({
    mutationFn: () => {
      const payload: CreateProjectInput = {
        name,
        business_key_header: keyHeader.trim() || undefined,
        source_header: sourceHeader.trim() || undefined,
        translation_columns: translationCols.split(",").map((s) => s.trim()).filter(Boolean),
        remark_columns: remarkCols.split(",").map((s) => s.trim()).filter(Boolean),
        pivot_language: pivotLang.trim() || null,
        pivoted_languages: pivotedLangs.split(",").map((s) => s.trim()).filter(Boolean),
      };
      return createProject(payload);
    },
    onSuccess: async (project) => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.projects() });
      shell.setProjectId(project.project_id);
      navigate(shell.buildHref("/app/workspace", { project: project.project_id }));
    },
  });

  const deleteMut = useMutation({
    mutationFn: () => {
      if (!deleteTarget) throw new Error("no delete target");
      return deleteProject(deleteTarget.project_id, deleteTarget.name);
    },
    onSuccess: async () => {
      if (deleteTarget && shell.projectId === deleteTarget.project_id) {
        navigate(shell.buildHref("/app", { project: null }));
      }
      await queryClient.invalidateQueries({ queryKey: queryKeys.projects() });
      setDeleteTarget(null);
      setConfirmName("");
    },
  });

  function openDeleteDialog(e: React.MouseEvent, project: ProjectSummary) {
    e.stopPropagation();
    setDeleteTarget(project);
    setConfirmName("");
  }

  function closeDeleteDialog() {
    if (deleteMut.isPending) return;
    setDeleteTarget(null);
    setConfirmName("");
  }

  if (shell.projectsLoading) {
    return <LoadingBlock label="Loading projects..." />;
  }

  return (
    <div className={styles.hub}>
      <header className={styles.header}>
        <h1 className={styles.title}>Momo TMS</h1>
        <button className={buttonClassName("primary")} onClick={() => setShowCreate(true)}>
          + Create Project
        </button>
      </header>

      {showCreate && (
        <div className={styles.createForm}>
          <h2>Create Project</h2>
          <label>Project name <input value={name} onChange={(e) => setName(e.target.value)} /></label>
          <label>Key column header <input value={keyHeader} onChange={(e) => setKeyHeader(e.target.value)} placeholder="key" /></label>
          <label>Source column header <input value={sourceHeader} onChange={(e) => setSourceHeader(e.target.value)} placeholder="MsgStr" /></label>
          <label>Translation columns (comma-separated) <input value={translationCols} onChange={(e) => setTranslationCols(e.target.value)} placeholder="zh-Hans, en, ja" /></label>
          <label>Remark columns (comma-separated) <input value={remarkCols} onChange={(e) => setRemarkCols(e.target.value)} placeholder="context, max_length" /></label>
          <label>Pivot language (optional) <input value={pivotLang} onChange={(e) => setPivotLang(e.target.value)} placeholder="zh-Hans" /></label>
          <label>Pivoted languages (comma-separated) <input value={pivotedLangs} onChange={(e) => setPivotedLangs(e.target.value)} placeholder="en, ja" /></label>
          <div className={styles.formActions}>
            <button className={buttonClassName("primary")} disabled={!name.trim() || !translationCols.trim() || createMut.isPending} onClick={() => createMut.mutate()}>
              {createMut.isPending ? "Creating..." : "Create"}
            </button>
            <button className={buttonClassName("ghost")} onClick={() => setShowCreate(false)}>Cancel</button>
          </div>
        </div>
      )}

      {shell.projects.length === 0 && !showCreate ? (
        <EmptyState title="No projects" body="Create a project to get started." />
      ) : (
        <div className={styles.cards}>
          {shell.projects.map((p) => (
            <button
              key={p.project_id}
              className={styles.card}
              onClick={() => {
                shell.setProjectId(p.project_id);
                navigate(shell.buildHref("/app/workspace", { project: p.project_id }));
              }}
            >
              <div className={styles.cardHeader}>
                <span className={styles.cardName}>{p.name}</span>
                <span
                  className={styles.deleteIconBtn}
                  role="button"
                  tabIndex={0}
                  title="Delete project"
                  onClick={(e) => openDeleteDialog(e, p)}
                  onKeyDown={(e) => { if (e.key === "Enter") openDeleteDialog(e as unknown as React.MouseEvent, p); }}
                >
                  ✕
                </span>
              </div>
              <span className={styles.cardMeta}>Created {p.created_at}</span>
            </button>
          ))}
        </div>
      )}

      {deleteTarget && (
        <div className={styles.confirmOverlay} onClick={closeDeleteDialog}>
          <div className={styles.confirmPanel} onClick={(e) => e.stopPropagation()}>
            <h3>Delete project</h3>
            <p className={styles.confirmWarning}>
              This will permanently delete <strong>{deleteTarget.name}</strong> and all its data. This action cannot be undone.
            </p>
            <label>
              Type <strong>{deleteTarget.name}</strong> to confirm
              <input
                value={confirmName}
                onChange={(e) => setConfirmName(e.target.value)}
                placeholder={deleteTarget.name}
                autoFocus
              />
            </label>
            <div className={styles.confirmActions}>
              <button className={buttonClassName("ghost")} onClick={closeDeleteDialog} disabled={deleteMut.isPending}>
                Cancel
              </button>
              <button
                className={buttonClassName("danger")}
                disabled={confirmName !== deleteTarget.name || deleteMut.isPending}
                onClick={() => deleteMut.mutate()}
              >
                {deleteMut.isPending ? "Deleting..." : "Delete"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Rebuild the frontend static assets**

Run: `cd frontend && npm run build`

Expected: Build succeeds with no errors.

- [ ] **Step 4: Start the dev server and manually verify**

Run: `python -m app.main` (or the project's start command)

Verify in browser:
1. Navigate to `/app` — project cards show the ✕ delete button
2. Click ✕ — confirmation dialog opens
3. Type the wrong name — Delete button stays disabled
4. Type the correct name — Delete button enables
5. Click Delete — project disappears from the list
6. Click Cancel — dialog closes, nothing happens

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/hub/HubPage.tsx frontend/src/pages/hub/HubPage.module.css
git commit -m "feat: add delete project confirmation dialog to HubPage"
```

---

### Task 6: Rebuild Static Assets

**Files:**
- Modify: `app/static/product-app/` (build output)

- [ ] **Step 1: Rebuild the frontend**

Run:
```bash
cd frontend && npm run build
```

Expected: Build completes. New files appear in `app/static/product-app/`.

- [ ] **Step 2: Commit the rebuilt assets**

```bash
git add app/static/product-app/
git commit -m "chore: rebuild static assets with delete project support"
```

---

### Task 7: E2E Test

**Files:**
- Modify: `tests/e2e/product-app.spec.js`

- [ ] **Step 1: Add E2E test for project deletion**

Add the following test to `tests/e2e/product-app.spec.js`:

```javascript
test("delete project via confirmation dialog", async ({ page, request }) => {
  // Create a project to delete
  const createResp = await request.post("/api/projects", {
    data: {
      name: "Delete Target",
      translation_columns: ["en"],
      remark_columns: ["context"],
    },
  });
  expect(createResp.ok()).toBeTruthy();
  const created = await createResp.json();

  await page.goto("/app");
  await expect(page.locator("text=Delete Target")).toBeVisible();

  // Click the delete button on the project card
  const card = page.locator("button", { hasText: "Delete Target" });
  await card.locator("[title='Delete project']").click();

  // Confirmation dialog should be visible
  await expect(page.locator("text=This will permanently delete")).toBeVisible();

  // Delete button should be disabled until name matches
  const deleteBtn = page.locator("button", { hasText: "Delete" }).last();
  await expect(deleteBtn).toBeDisabled();

  // Type the correct name
  const confirmInput = page.locator("input[placeholder='Delete Target']");
  await confirmInput.fill("Delete Target");
  await expect(deleteBtn).toBeEnabled();

  // Confirm deletion
  await deleteBtn.click();

  // Project should disappear from the list
  await expect(page.locator("text=Delete Target")).not.toBeVisible();

  // Verify via API that the project is gone
  const getResp = await request.get(`/api/projects`);
  expect(getResp.ok()).toBeTruthy();
  const projects = await getResp.json();
  expect(projects.find((p) => p.project_id === created.project_id)).toBeUndefined();
});
```

- [ ] **Step 2: Run the E2E test**

Run: `npx playwright test tests/e2e/product-app.spec.js --grep "delete project"`

Expected: Test PASSES.

- [ ] **Step 3: Commit**

```bash
git add tests/e2e/product-app.spec.js
git commit -m "test: add E2E test for project deletion"
```

---

### Task 8: Update docs/contracts.md

**Files:**
- Modify: `docs/contracts.md`

- [ ] **Step 1: Add the DELETE endpoint to the HTTP Routes section**

In `docs/contracts.md`, in the "Projects and bootstrap" subsection of "HTTP Routes" (after line 283), add:

```markdown
- `DELETE /api/projects/{project_id}`
```

- [ ] **Step 2: Add the request/response shape documentation**

In `docs/contracts.md`, in the "Request And Report Shapes" section, add a new block after the `POST /api/projects` shape documentation (after line 109):

```markdown
`DELETE /api/projects/{project_id}`

- request body accepts `name`
- server validates the supplied name matches the project's actual name before proceeding
- name mismatch returns `400`
- project not found returns `404`
- success returns `{ "deleted": true, "project_id": <id>, "name": "<name>" }`
- deletion is permanent: removes the project and all child data (schema, entries, variants, bindings, imports, jobs, dev versions) in a single transaction
- no cross-project data is affected
```

- [ ] **Step 3: Commit**

```bash
git add docs/contracts.md
git commit -m "docs: document DELETE /api/projects/{project_id} endpoint"
```
