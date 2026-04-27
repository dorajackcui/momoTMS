# Single File Upload Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add single Excel file upload as the default mode in WorkbookWorkflowPanel, keeping folder upload as a secondary toggle.

**Architecture:** New `FileUpload` component mirrors `FolderUpload` but for single `.xlsx` files. New `WorkbookUpload` composition component encapsulates mode switching between the two. `WorkbookWorkflowPanel` swaps `FolderUpload` for `WorkbookUpload`. Backend and `postFolderForm` are unchanged.

**Tech Stack:** React, TypeScript, CSS Modules, Playwright (e2e)

---

### Task 1: Create `FileUpload` component

**Files:**
- Create: `frontend/src/shared/ui/FileUpload.tsx`

- [ ] **Step 1: Create `FileUpload.tsx`**

```tsx
import { useRef } from "react";
import { buttonClassName } from "@/shared/ui/primitives";

export type FileUploadProps = {
  label: string;
  onFiles: (files: File[]) => void;
  disabled?: boolean;
};

export function FileUpload(props: FileUploadProps) {
  const inputRef = useRef<HTMLInputElement>(null);

  function handleChange() {
    const input = inputRef.current;
    if (!input?.files) return;
    const files = Array.from(input.files).filter(
      (f) => !f.name.startsWith("~$"),
    );
    if (files.length > 0) props.onFiles(files);
    input.value = "";
  }

  return (
    <label>
      <input
        ref={inputRef}
        type="file"
        accept=".xlsx"
        onChange={handleChange}
        style={{ display: "none" }}
        disabled={props.disabled}
      />
      <span className={buttonClassName("secondary")} role="button">
        {props.label}
      </span>
    </label>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors related to `FileUpload.tsx`.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/shared/ui/FileUpload.tsx
git commit -m "feat: add FileUpload component for single .xlsx upload"
```

---

### Task 2: Create `WorkbookUpload` composition component

**Files:**
- Create: `frontend/src/shared/ui/WorkbookUpload.tsx`
- Create: `frontend/src/shared/ui/WorkbookUpload.module.css`

- [ ] **Step 1: Create `WorkbookUpload.module.css`**

```css
.toggle {
  color: var(--muted);
  font-size: 13px;
  background: none;
  border: none;
  padding: 0;
  cursor: pointer;
  text-decoration: underline;
}

.toggle:hover {
  color: var(--text);
}
```

- [ ] **Step 2: Create `WorkbookUpload.tsx`**

```tsx
import { useState } from "react";

import { FileUpload } from "@/shared/ui/FileUpload";
import { FolderUpload } from "@/shared/ui/FolderUpload";

import styles from "@/shared/ui/WorkbookUpload.module.css";

export type WorkbookUploadProps = {
  label: string;
  onFiles: (files: File[]) => void;
  disabled?: boolean;
};

export function WorkbookUpload(props: WorkbookUploadProps) {
  const [mode, setMode] = useState<"file" | "folder">("file");

  function handleToggle() {
    setMode((prev) => (prev === "file" ? "folder" : "file"));
    props.onFiles([]);
  }

  return (
    <div>
      {mode === "file" ? (
        <FileUpload
          label={props.label}
          onFiles={props.onFiles}
          disabled={props.disabled}
        />
      ) : (
        <FolderUpload
          label={props.label}
          onFiles={props.onFiles}
          disabled={props.disabled}
        />
      )}
      <button
        type="button"
        className={styles.toggle}
        onClick={handleToggle}
        disabled={props.disabled}
      >
        {mode === "file" ? "or upload folder" : "or upload single file"}
      </button>
    </div>
  );
}
```

- [ ] **Step 3: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors related to `WorkbookUpload.tsx`.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/shared/ui/WorkbookUpload.tsx frontend/src/shared/ui/WorkbookUpload.module.css
git commit -m "feat: add WorkbookUpload composition component with file/folder toggle"
```

---

### Task 3: Replace `FolderUpload` with `WorkbookUpload` in `WorkbookWorkflowPanel`

**Files:**
- Modify: `frontend/src/shared/ui/WorkbookWorkflowPanel.tsx`

- [ ] **Step 1: Update imports**

Replace the `FolderUpload` import with `WorkbookUpload`:

```tsx
// old
import { FolderUpload } from "@/shared/ui/FolderUpload";
// new
import { WorkbookUpload } from "@/shared/ui/WorkbookUpload";
```

- [ ] **Step 2: Replace `FolderUpload` usage in JSX**

Replace line 69-79 (the `<FolderUpload ... />` block) with:

```tsx
      <WorkbookUpload
        label={props.uploadLabel ?? "Upload workbook"}
        disabled={props.disabled}
        onFiles={(nextFiles) => {
          setFiles(nextFiles);
          setPreview(null);
          setCompletedJob(null);
          previewMut.reset();
          executeMut.reset();
        }}
      />
```

- [ ] **Step 3: Update file count display**

Replace the file count paragraph (line 80):

```tsx
// old
{files.length > 0 && <p className={styles.meta}>{files.length} files selected</p>}
// new
{files.length > 0 && (
  <p className={styles.meta}>
    {files.length === 1 ? files[0].name : `${files.length} files selected`}
  </p>
)}
```

- [ ] **Step 4: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/shared/ui/WorkbookWorkflowPanel.tsx
git commit -m "feat: use WorkbookUpload in WorkbookWorkflowPanel for single file default"
```

---

### Task 4: Build frontend static assets

**Files:**
- Modify: `app/static/product-app/` (build output)

- [ ] **Step 1: Build the frontend**

Run: `cd frontend && npm run build`
Expected: Build succeeds with no errors.

- [ ] **Step 2: Commit build output**

```bash
git add app/static/product-app/
git commit -m "chore: rebuild static assets with single file upload support"
```

---

### Task 5: Verify e2e tests pass

**Files:**
- None modified (existing tests exercise the changed components)

The existing e2e test `"Dev create branch uses workbook panel with preview and execute"` uses `page.locator('input[type="file"]').setInputFiles(importDir)` which sets files on the first file input. After this change, the first file input is the single-file `FileUpload` (default mode). Playwright's `setInputFiles` with a directory path works on both regular and `webkitdirectory` inputs — the test should continue to work as-is.

- [ ] **Step 1: Run e2e tests**

Run: `npx playwright test tests/e2e/product-app.spec.js`
Expected: All existing tests pass.

- [ ] **Step 2: If any test fails due to the upload mode change**

If a test fails because it expected folder upload but now gets single-file upload, the fix is to click the "or upload folder" toggle link before setting files:

```js
await page.getByRole("button", { name: "or upload folder" }).click();
await page.locator('input[type="file"]').setInputFiles(importDir);
```

Check each failing test and apply this pattern only where needed.

- [ ] **Step 3: Commit any test fixes**

```bash
git add tests/e2e/product-app.spec.js
git commit -m "test: update e2e tests for default single file upload mode"
```
