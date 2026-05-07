# Frontend Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Full frontend redesign — Project Hub + top-tab navigation + 4 project-level pages (Workspace, Release, Dev, Runs) grounded in the Phase 1–9 backend model.

**Architecture:** Replace the current sidebar-based AppShell with a two-level navigation: a Project Hub (top level) and a project interior with a horizontal tab bar. Shared components (VariantGrid, EditPanel) are extracted from page-specific code and reused across Workspace, Release, and Dev pages. All existing domain API modules and types are preserved and extended.

**Tech Stack:** React 19, React Router 6, TanStack React Query 5, react-data-grid 7, Vite 7, TypeScript 5 (strict), CSS Modules

**Spec:** `design/frontend-redesign-spec.md`

---

## File Map

### New Files

```
frontend/src/
├── app/
│   ├── shell/
│   │   ├── ProjectShell.tsx          # Top-tab layout for project interior
│   │   ├── ProjectShell.module.css
│   │   ├── HubShell.tsx              # Layout for Project Hub (no tabs)
│   │   └── HubShell.module.css
│   └── router.tsx                    # Rewritten routes
├── shared/
│   └── ui/
│       ├── VariantGrid.tsx           # Shared Excel-like grid with column-level filters
│       ├── VariantGrid.module.css
│       ├── EditPanel.tsx             # Shared mutation editor (type selector + input + preview + execute)
│       ├── EditPanel.module.css
│       ├── FolderUpload.tsx          # Shared folder upload control
│       ├── TrashPanel.tsx            # Shared unbind + project-trash panel
│       └── TrashPanel.module.css
├── pages/
│   ├── hub/
│   │   ├── HubPage.tsx              # Project list + create
│   │   └── HubPage.module.css
│   ├── workspace/
│   │   ├── WorkspacePage.tsx         # Grid-only variant browser
│   │   └── WorkspacePage.module.css
│   ├── release/
│   │   ├── ReleasePage.tsx           # Browse + Edit + Trash tabs
│   │   └── ReleasePage.module.css
│   ├── dev/
│   │   ├── DevPage.tsx              # Branch list, create flow, detail
│   │   ├── DevPage.module.css
│   │   ├── BranchDetail.tsx         # Browse + Edit + Replace + Trash tabs
│   │   ├── CreateBranch.tsx         # Stepped wizard (upload → preview → done)
│   │   └── ImportBatches.tsx        # Import batch history view
│   └── runs/
│       ├── RunsPage.tsx             # Jobs + Fill + QA + Export tabs
│       └── RunsPage.module.css
└── domains/
    └── branches/
        └── api.ts                   # Extended: bootstrap + mutation preview + project trash
```

### Modified Files

```
frontend/src/
├── main.tsx                          # No change (still renders App > RouterProvider)
├── App.tsx                           # No change (still wraps QueryClientProvider)
├── app/shell/AppShellContext.tsx      # Simplified: remove sidebar-specific state (tab, businessKey, jobId)
├── app/shell/AppShell.tsx            # Rewrite: two shell modes (hub vs project)
├── shared/api/queryKeys.ts           # Add bootstrapPreview key
├── domains/branches/api.ts           # Add bootstrapBranch, previewBootstrap, previewMutation, projectTrash
├── domains/branches/types.ts         # Add BootstrapPreview, MutationPreview types
└── styles.css                        # Minor: adjust body background for new layout
```

### Deleted Files (old pages)

```
frontend/src/pages/overview/          # Replaced by workspace/
frontend/src/pages/branches/          # Replaced by release/ + dev/
frontend/src/pages/intake/            # Merged into dev/CreateBranch
frontend/src/pages/project/           # Replaced by hub/
frontend/src/pages/variants/          # Removed (no drawer/timeline page)
frontend/src/pages/not-found/         # Keep or move
frontend/src/features/variant-drawer/ # Removed (no drawer in redesign)
frontend/src/features/import-preview/ # Logic merged into CreateBranch
frontend/src/features/job-detail/     # Logic merged into RunsPage
```

---

## Task 1: Extend Domain API — Bootstrap + Mutation Preview + Project Trash

**Files:**
- Modify: `frontend/src/domains/branches/api.ts`
- Modify: `frontend/src/domains/branches/types.ts`
- Modify: `frontend/src/shared/api/queryKeys.ts`

The backend has bootstrap, mutation preview, and project trash endpoints that the frontend never calls. Add the missing API functions and types.

- [ ] **Step 1: Add bootstrap and mutation preview types**

In `frontend/src/domains/branches/types.ts`, add at the end of the file:

```typescript
export type BranchBootstrapRequest = {
  branch_ref: string;
  import_batch_id: number;
};

export type BranchBootstrapPreview = EffectForecastPreview & {
  workflow_kind: "branch_bootstrap";
};

export type BranchMutationPreview = EffectForecastPreview & {
  workflow_kind: "branch_mutation";
};
```

- [ ] **Step 2: Add API functions for bootstrap, mutation preview, and project trash**

In `frontend/src/domains/branches/api.ts`, add these functions after the existing exports:

```typescript
import type {
  BranchBootstrapPreview,
  BranchBootstrapRequest,
  BranchMutationInput,
  BranchMutationPreview,
  BranchReplacePreview,
  BranchRowsResponse,
  BranchListResponse,
  BranchLookupResponse,
  DevBranchDetail,
  SameSourceCandidatesResponse,
  EffectForecastPreview,
} from "@/domains/branches/types";

// --- new functions ---

export function previewBootstrap(
  projectId: number,
  request: BranchBootstrapRequest,
) {
  return fetchJson<BranchBootstrapPreview>(
    `/api/projects/${projectId}/branches/bootstrap/preview`,
    { method: "POST", body: JSON.stringify(request) },
  );
}

export function bootstrapBranch(
  projectId: number,
  request: BranchBootstrapRequest,
) {
  return fetchJson<JobDetail>(
    `/api/projects/${projectId}/branches/bootstrap`,
    { method: "POST", body: JSON.stringify(request) },
  );
}

export function previewBranchMutation(
  projectId: number,
  branchRef: string,
  input: BranchMutationInput,
) {
  return fetchJson<BranchMutationPreview>(
    `/api/projects/${projectId}/branches/mutations/preview`,
    {
      method: "POST",
      body: JSON.stringify({ branch_ref: branchRef, input }),
    },
  );
}

export function projectTrash(
  projectId: number,
  businessKeys: string[],
) {
  return fetchJson<JobDetail>(
    `/api/projects/${projectId}/variants/trash`,
    {
      method: "POST",
      body: JSON.stringify({ business_keys: businessKeys }),
    },
  );
}
```

- [ ] **Step 3: Add query key for bootstrap preview**

In `frontend/src/shared/api/queryKeys.ts`, add inside the `queryKeys` object:

```typescript
bootstrapPreview: (projectId: number, branchRef: string, importBatchId: number) =>
  ["bootstrap-preview", projectId, branchRef, importBatchId] as const,
mutationPreview: (projectId: number, branchRef: string, input: Record<string, unknown>) =>
  ["mutation-preview", projectId, branchRef, input] as const,
```

- [ ] **Step 4: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: no type errors in new/modified files

- [ ] **Step 5: Commit**

```bash
git add frontend/src/domains/branches/api.ts frontend/src/domains/branches/types.ts frontend/src/shared/api/queryKeys.ts
git commit -m "feat: add bootstrap, mutation preview, and project trash API functions"
```

---

## Task 2: Shared VariantGrid Component

**Files:**
- Create: `frontend/src/shared/ui/VariantGrid.tsx`
- Create: `frontend/src/shared/ui/VariantGrid.module.css`

The same Excel-like grid pattern is used in Workspace, Release Browse, and Dev Branch Browse. Build it once as a shared component.

- [ ] **Step 1: Create VariantGrid component**

Create `frontend/src/shared/ui/VariantGrid.tsx`:

```tsx
import { useDeferredValue, useMemo, useState } from "react";
import DataGrid from "react-data-grid";
import type { Column } from "react-data-grid";

import type { ProjectSchema } from "@/domains/projects/types";
import type { ProjectVariantRow } from "@/domains/variants/types";

import styles from "@/shared/ui/VariantGrid.module.css";

export type VariantGridProps = {
  schema: ProjectSchema;
  rows: ProjectVariantRow[];
  totalRows: number;
  page: number;
  pageSize: number;
  onPageChange: (page: number) => void;
  columnFilters: Record<string, string>;
  onColumnFilterChange: (column: string, value: string) => void;
  stateFilter: "active" | "orphan" | "all";
  onStateFilterChange: (state: "active" | "orphan" | "all") => void;
  columnToggles: { translations: boolean; remarks: boolean; pivot: boolean };
  onColumnToggleChange: (group: "translations" | "remarks" | "pivot", on: boolean) => void;
};

function formatBranch(row: ProjectVariantRow): string {
  const refs = row.bindings.map((b) => b.branch_ref);
  if (refs.length === 0) return "-";
  const first = refs[0].replace("rel/current", "rel/c");
  return refs.length > 1 ? `${first} +${refs.length - 1}` : first;
}

function HeaderFilter(props: {
  column: string;
  value: string;
  onChange: (column: string, value: string) => void;
}) {
  return (
    <input
      className={styles.headerFilter}
      value={props.value}
      onChange={(e) => props.onChange(props.column, e.target.value)}
      placeholder="Filter..."
      onClick={(e) => e.stopPropagation()}
    />
  );
}

export function VariantGrid(props: VariantGridProps) {
  const {
    schema, rows, totalRows, page, pageSize,
    onPageChange, columnFilters, onColumnFilterChange,
    stateFilter, onStateFilterChange,
    columnToggles, onColumnToggleChange,
  } = props;

  const totalPages = Math.max(1, Math.ceil(totalRows / pageSize));

  const columns = useMemo(() => {
    const cols: Column<ProjectVariantRow>[] = [
      {
        key: "business_key",
        name: "business_key",
        width: 220,
        frozen: true,
        headerCellClass: styles.filterableHeader,
        renderHeaderCell: () => (
          <div className={styles.headerCell}>
            <span>business_key</span>
            <HeaderFilter column="search_business_key" value={columnFilters["search_business_key"] ?? ""} onChange={onColumnFilterChange} />
          </div>
        ),
      },
      {
        key: "file_name",
        name: "file_name",
        width: 160,
        renderCell: ({ row }) => <>{row.file_name ?? "-"}</>,
      },
      {
        key: "source",
        name: "source",
        width: 260,
        headerCellClass: styles.filterableHeader,
        renderHeaderCell: () => (
          <div className={styles.headerCell}>
            <span>source</span>
            <HeaderFilter column="search_source" value={columnFilters["search_source"] ?? ""} onChange={onColumnFilterChange} />
          </div>
        ),
      },
    ];

    if (columnToggles.translations) {
      for (const lang of schema.translation_columns) {
        cols.push({
          key: `translation:${lang}`,
          name: lang,
          width: 180,
          renderCell: ({ row }) => <>{row.translations[lang] ?? ""}</>,
        });
      }
    }

    if (columnToggles.remarks) {
      for (const key of schema.remark_columns) {
        cols.push({
          key: `remark:${key}`,
          name: key,
          width: 160,
          renderCell: ({ row }) => <>{row.remarks[key] ?? ""}</>,
        });
      }
    }

    if (columnToggles.pivot) {
      cols.push({
        key: "pivot_status",
        name: "pivot_status",
        width: 120,
      });
    }

    cols.push(
      {
        key: "branch",
        name: "branch",
        width: 170,
        renderCell: ({ row }) => <>{formatBranch(row)}</>,
      },
      {
        key: "state",
        name: "state",
        width: 100,
        renderCell: ({ row }) => (
          <span className={row.state === "orphan" ? styles.orphan : undefined}>
            {row.state}
          </span>
        ),
      },
    );

    return cols;
  }, [schema, columnToggles, columnFilters, onColumnFilterChange]);

  return (
    <div className={styles.grid}>
      <div className={styles.toolbar}>
        <label className={styles.toolbarItem}>
          State:
          <select
            value={stateFilter}
            onChange={(e) => onStateFilterChange(e.target.value as "active" | "orphan" | "all")}
          >
            <option value="active">Active</option>
            <option value="orphan">Orphan</option>
            <option value="all">All</option>
          </select>
        </label>
        <label className={styles.toggle}>
          <input type="checkbox" checked={columnToggles.translations} onChange={(e) => onColumnToggleChange("translations", e.target.checked)} />
          Translations
        </label>
        <label className={styles.toggle}>
          <input type="checkbox" checked={columnToggles.remarks} onChange={(e) => onColumnToggleChange("remarks", e.target.checked)} />
          Remarks
        </label>
        <label className={styles.toggle}>
          <input type="checkbox" checked={columnToggles.pivot} onChange={(e) => onColumnToggleChange("pivot", e.target.checked)} />
          Pivot
        </label>
      </div>
      <DataGrid
        columns={columns}
        rows={rows}
        rowKeyGetter={(row) => row.variant_id}
        className={styles.dataGrid}
      />
      <div className={styles.pagination}>
        <span>{totalRows} rows</span>
        <span>Page {page} of {totalPages}</span>
        <button disabled={page <= 1} onClick={() => onPageChange(page - 1)}>Prev</button>
        <button disabled={page >= totalPages} onClick={() => onPageChange(page + 1)}>Next</button>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Create VariantGrid styles**

Create `frontend/src/shared/ui/VariantGrid.module.css`:

```css
.grid {
  display: grid;
  gap: 8px;
}

.toolbar {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}

.toolbarItem {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--muted);
}

.toolbarItem select {
  padding: 4px 8px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--surface);
  font-size: 13px;
}

.toggle {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
  color: var(--muted);
  cursor: pointer;
}

.dataGrid {
  border: 1px solid var(--border);
  border-radius: 8px;
  block-size: 100%;
  min-height: 400px;
}

.filterableHeader {
  overflow: visible !important;
}

.headerCell {
  display: grid;
  gap: 4px;
  padding: 2px 0;
}

.headerFilter {
  width: 100%;
  padding: 2px 6px;
  border: 1px solid var(--border);
  border-radius: 4px;
  font-size: 12px;
  background: var(--surface);
}

.headerFilter:focus {
  outline: none;
  border-color: var(--accent);
}

.orphan {
  color: var(--muted);
}

.pagination {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 13px;
  color: var(--muted);
}

.pagination button {
  padding: 4px 12px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--surface);
  font-size: 13px;
  cursor: pointer;
}

.pagination button:disabled {
  opacity: 0.4;
  cursor: default;
}
```

- [ ] **Step 3: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit`

- [ ] **Step 4: Commit**

```bash
git add frontend/src/shared/ui/VariantGrid.tsx frontend/src/shared/ui/VariantGrid.module.css
git commit -m "feat: add shared VariantGrid component with column-level filtering"
```

---

## Task 3: Shared FolderUpload Component

**Files:**
- Create: `frontend/src/shared/ui/FolderUpload.tsx`

Reusable folder upload control used by CreateBranch, Fill tab, QA tab.

- [ ] **Step 1: Create FolderUpload component**

Create `frontend/src/shared/ui/FolderUpload.tsx`:

```tsx
import { useRef } from "react";
import { buttonClassName } from "@/shared/ui/primitives";

export type FolderUploadProps = {
  label: string;
  onFiles: (files: File[]) => void;
  disabled?: boolean;
};

export function FolderUpload(props: FolderUploadProps) {
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
        /* @ts-expect-error webkitdirectory is non-standard */
        webkitdirectory=""
        directory=""
        multiple
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

- [ ] **Step 2: Commit**

```bash
git add frontend/src/shared/ui/FolderUpload.tsx
git commit -m "feat: add shared FolderUpload component"
```

---

## Task 4: Shared EditPanel Component

**Files:**
- Create: `frontend/src/shared/ui/EditPanel.tsx`
- Create: `frontend/src/shared/ui/EditPanel.module.css`

Shared mutation editor used by Release Edit tab and Dev Edit tab. Handles mutation type selection, input method, preview, and execute.

- [ ] **Step 1: Create EditPanel component**

Create `frontend/src/shared/ui/EditPanel.tsx`:

```tsx
import { useState } from "react";
import { useMutation } from "@tanstack/react-query";

import type { BranchMutationInput, BranchMutationChange, EffectForecastPreview } from "@/domains/branches/types";
import type { ImportBatchSummary } from "@/domains/imports/types";
import type { JobDetail } from "@/domains/jobs/types";
import { previewBranchMutation, runBranchMutation } from "@/domains/branches/api";
import { buttonClassName, InlineNotice, StatGrid } from "@/shared/ui/primitives";

import styles from "@/shared/ui/EditPanel.module.css";

type MutationType = "range" | "content";
type InputMethod = "import_batch" | "direct";

export type EditPanelProps = {
  projectId: number;
  branchRef: string;
  allowRange: boolean;
  importBatches: ImportBatchSummary[];
  onJobCreated: (job: JobDetail) => void;
};

export function EditPanel(props: EditPanelProps) {
  const { projectId, branchRef, allowRange, importBatches, onJobCreated } = props;

  const [mutationType, setMutationType] = useState<MutationType>("content");
  const [inputMethod, setInputMethod] = useState<InputMethod>("direct");
  const [selectedBatchId, setSelectedBatchId] = useState<number | null>(null);
  const [directText, setDirectText] = useState("");
  const [preview, setPreview] = useState<EffectForecastPreview | null>(null);

  const previewMut = useMutation({
    mutationFn: () => {
      const input = buildInput();
      if (!input) throw new Error("No input");
      return previewBranchMutation(projectId, branchRef, input);
    },
    onSuccess: (data) => setPreview(data),
  });

  const executeMut = useMutation({
    mutationFn: () => {
      const input = buildInput();
      if (!input) throw new Error("No input");
      return runBranchMutation(projectId, branchRef, input);
    },
    onSuccess: (data) => {
      onJobCreated(data);
      setPreview(null);
      setDirectText("");
    },
  });

  function buildInput(): BranchMutationInput | null {
    if (inputMethod === "import_batch") {
      if (!selectedBatchId) return null;
      return { kind: "import_batch", import_batch_id: selectedBatchId };
    }
    const changes = parseDirectChanges(directText);
    if (changes.length === 0) return null;
    return { kind: "direct", changes };
  }

  const hasInput = inputMethod === "import_batch" ? selectedBatchId !== null : directText.trim().length > 0;

  return (
    <div className={styles.panel}>
      <div className={styles.selectors}>
        {allowRange ? (
          <fieldset className={styles.fieldset}>
            <legend>Mutation type</legend>
            <label><input type="radio" checked={mutationType === "range"} onChange={() => setMutationType("range")} /> Range (add/remove entries)</label>
            <label><input type="radio" checked={mutationType === "content"} onChange={() => setMutationType("content")} /> Content (edit translations/remarks)</label>
          </fieldset>
        ) : (
          <p className={styles.hint}>Content mutation on {branchRef}</p>
        )}
        <fieldset className={styles.fieldset}>
          <legend>Input method</legend>
          <label><input type="radio" checked={inputMethod === "import_batch"} onChange={() => setInputMethod("import_batch")} /> Import batch</label>
          <label><input type="radio" checked={inputMethod === "direct"} onChange={() => setInputMethod("direct")} /> Direct</label>
        </fieldset>
      </div>

      {inputMethod === "import_batch" ? (
        <div className={styles.inputArea}>
          <select value={selectedBatchId ?? ""} onChange={(e) => setSelectedBatchId(e.target.value ? Number(e.target.value) : null)}>
            <option value="">Select import batch...</option>
            {importBatches.map((b) => (
              <option key={b.import_batch_id} value={b.import_batch_id}>
                Batch #{b.import_batch_id} — {b.rows_scanned} rows — {b.created_at}
              </option>
            ))}
          </select>
        </div>
      ) : (
        <div className={styles.inputArea}>
          <textarea
            className={styles.directInput}
            value={directText}
            onChange={(e) => setDirectText(e.target.value)}
            placeholder={"business_key\\tsource\\ttranslation_lang\\n..."}
            rows={8}
          />
          <p className={styles.hint}>Tab-separated: business_key, source, then translation columns</p>
        </div>
      )}

      <div className={styles.actions}>
        <button
          className={buttonClassName("secondary")}
          disabled={!hasInput || previewMut.isPending}
          onClick={() => previewMut.mutate()}
        >
          {previewMut.isPending ? "Previewing..." : "Preview"}
        </button>
        {preview && (
          <button
            className={buttonClassName("primary")}
            disabled={executeMut.isPending}
            onClick={() => executeMut.mutate()}
          >
            {executeMut.isPending ? "Executing..." : "Execute"}
          </button>
        )}
      </div>

      {previewMut.isError && (
        <InlineNotice tone="error">{String(previewMut.error)}</InlineNotice>
      )}
      {executeMut.isError && (
        <InlineNotice tone="error">{String(executeMut.error)}</InlineNotice>
      )}

      {preview && (
        <div className={styles.previewResult}>
          <StatGrid items={Object.entries(preview.summary).map(([k, v]) => ({ label: k, value: String(v) }))} />
          <table className={styles.previewTable}>
            <thead>
              <tr>
                {preview.rows.length > 0 && Object.keys(preview.rows[0]).map((k) => <th key={k}>{k}</th>)}
              </tr>
            </thead>
            <tbody>
              {preview.rows.slice(0, 50).map((row, i) => (
                <tr key={i}>
                  {Object.values(row).map((v, j) => <td key={j}>{String(v ?? "")}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function parseDirectChanges(text: string): BranchMutationChange[] {
  const lines = text.trim().split("\n").filter((l) => l.trim());
  if (lines.length === 0) return [];
  return lines.map((line) => {
    const parts = line.split("\t");
    return {
      business_key: parts[0]?.trim() ?? "",
      source: parts[1]?.trim() || undefined,
      translations_by_lang: {},
      remarks_by_key: {},
    };
  });
}
```

- [ ] **Step 2: Create EditPanel styles**

Create `frontend/src/shared/ui/EditPanel.module.css`:

```css
.panel {
  display: grid;
  gap: 16px;
}

.selectors {
  display: flex;
  gap: 24px;
  flex-wrap: wrap;
}

.fieldset {
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 10px 14px;
  display: flex;
  gap: 14px;
  align-items: center;
}

.fieldset legend {
  font-size: 12px;
  color: var(--muted);
  padding: 0 4px;
}

.fieldset label {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
  cursor: pointer;
}

.hint {
  margin: 0;
  font-size: 12px;
  color: var(--muted);
}

.inputArea {
  display: grid;
  gap: 6px;
}

.inputArea select {
  padding: 8px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface);
  font-size: 13px;
}

.directInput {
  width: 100%;
  padding: 10px;
  border: 1px solid var(--border);
  border-radius: 8px;
  font-family: var(--font-mono);
  font-size: 13px;
  resize: vertical;
  background: var(--surface);
}

.actions {
  display: flex;
  gap: 10px;
}

.previewResult {
  display: grid;
  gap: 12px;
}

.previewTable {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}

.previewTable th,
.previewTable td {
  border: 1px solid var(--border);
  padding: 4px 8px;
  text-align: left;
}

.previewTable th {
  background: var(--surface-muted);
  font-weight: 600;
}
```

- [ ] **Step 3: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit`

- [ ] **Step 4: Commit**

```bash
git add frontend/src/shared/ui/EditPanel.tsx frontend/src/shared/ui/EditPanel.module.css
git commit -m "feat: add shared EditPanel component for mutation operations"
```

---

## Task 5: Shared TrashPanel Component

**Files:**
- Create: `frontend/src/shared/ui/TrashPanel.tsx`
- Create: `frontend/src/shared/ui/TrashPanel.module.css`

Reusable trash panel with unbind + project trash, used by Release Trash and Dev Trash tabs.

- [ ] **Step 1: Create TrashPanel component**

Create `frontend/src/shared/ui/TrashPanel.tsx`:

```tsx
import { useState } from "react";
import { useMutation } from "@tanstack/react-query";

import { deleteBranchBusinessKeys, projectTrash } from "@/domains/branches/api";
import type { JobDetail } from "@/domains/jobs/types";
import { buttonClassName, InlineNotice } from "@/shared/ui/primitives";

import styles from "@/shared/ui/TrashPanel.module.css";

export type TrashPanelProps = {
  projectId: number;
  branchRef: string;
  showProjectTrash: boolean;
  onJobCreated: (job: JobDetail) => void;
};

export function TrashPanel(props: TrashPanelProps) {
  const { projectId, branchRef, showProjectTrash, onJobCreated } = props;

  const [unbindKeys, setUnbindKeys] = useState("");
  const [trashKeys, setTrashKeys] = useState("");

  const unbindMut = useMutation({
    mutationFn: () => {
      const keys = parseKeys(unbindKeys);
      return deleteBranchBusinessKeys(projectId, branchRef, keys);
    },
    onSuccess: (data) => {
      onJobCreated(data);
      setUnbindKeys("");
    },
  });

  const trashMut = useMutation({
    mutationFn: () => {
      const keys = parseKeys(trashKeys);
      return projectTrash(projectId, keys);
    },
    onSuccess: (data) => {
      onJobCreated(data);
      setTrashKeys("");
    },
  });

  return (
    <div className={styles.panel}>
      <section className={styles.section}>
        <h3>Unbind from {branchRef}</h3>
        <p className={styles.hint}>Remove bindings from this branch. Variants with no remaining bindings become orphan.</p>
        <textarea
          className={styles.textarea}
          value={unbindKeys}
          onChange={(e) => setUnbindKeys(e.target.value)}
          placeholder={"One business_key per line"}
          rows={6}
        />
        <button
          className={buttonClassName("secondary")}
          disabled={!unbindKeys.trim() || unbindMut.isPending}
          onClick={() => unbindMut.mutate()}
        >
          {unbindMut.isPending ? "Unbinding..." : "Unbind"}
        </button>
        {unbindMut.isError && <InlineNotice tone="error">{String(unbindMut.error)}</InlineNotice>}
      </section>

      {showProjectTrash && (
        <section className={styles.section}>
          <h3>Project Trash</h3>
          <InlineNotice tone="warning" title="Irreversible">
            Trashed variants cannot be restored. Only orphan variants (zero bindings) will be trashed.
          </InlineNotice>
          <textarea
            className={styles.textarea}
            value={trashKeys}
            onChange={(e) => setTrashKeys(e.target.value)}
            placeholder={"One business_key per line"}
            rows={6}
          />
          <button
            className={buttonClassName("danger")}
            disabled={!trashKeys.trim() || trashMut.isPending}
            onClick={() => trashMut.mutate()}
          >
            {trashMut.isPending ? "Trashing..." : "Trash permanently"}
          </button>
          {trashMut.isError && <InlineNotice tone="error">{String(trashMut.error)}</InlineNotice>}
        </section>
      )}
    </div>
  );
}

function parseKeys(text: string): string[] {
  return text.split("\n").map((l) => l.trim()).filter(Boolean);
}
```

- [ ] **Step 2: Create TrashPanel styles**

Create `frontend/src/shared/ui/TrashPanel.module.css`:

```css
.panel {
  display: grid;
  gap: 24px;
}

.section {
  display: grid;
  gap: 10px;
}

.section h3 {
  margin: 0;
  font-size: 16px;
}

.hint {
  margin: 0;
  font-size: 13px;
  color: var(--muted);
}

.textarea {
  width: 100%;
  padding: 10px;
  border: 1px solid var(--border);
  border-radius: 8px;
  font-family: var(--font-mono);
  font-size: 13px;
  resize: vertical;
  background: var(--surface);
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/shared/ui/TrashPanel.tsx frontend/src/shared/ui/TrashPanel.module.css
git commit -m "feat: add shared TrashPanel component for unbind and project trash"
```

---

## Task 6: AppShell Rewrite — Two-Level Navigation

**Files:**
- Rewrite: `frontend/src/app/shell/AppShell.tsx`
- Create: `frontend/src/app/shell/ProjectShell.tsx`
- Create: `frontend/src/app/shell/ProjectShell.module.css`
- Modify: `frontend/src/app/shell/AppShellContext.tsx`
- Rewrite: `frontend/src/app/shell/AppShell.module.css`

Replace the sidebar layout with a two-level structure: HubShell (no tabs, full page for hub) and ProjectShell (top tab bar).

- [ ] **Step 1: Simplify AppShellContext**

The context type stays mostly the same — it already holds `projects`, `projectId`, `bootstrap`, `branchSummary`. Remove `businessKey` (no drawer) but keep everything else for now as pages use `tab`, `jobId` internally.

No code change needed — the context is already generic enough.

- [ ] **Step 2: Create ProjectShell layout**

Create `frontend/src/app/shell/ProjectShell.tsx`:

```tsx
import { NavLink, Outlet } from "react-router-dom";

import { useAppShell } from "@/app/shell/AppShellContext";
import { LoadingBlock, InlineNotice } from "@/shared/ui/primitives";

import styles from "@/app/shell/ProjectShell.module.css";

const tabs = [
  { to: "/app/workspace", label: "Workspace" },
  { to: "/app/release", label: "Release" },
  { to: "/app/dev", label: "Dev" },
  { to: "/app/runs", label: "Runs" },
] as const;

export function ProjectShell() {
  const shell = useAppShell();

  if (!shell.projectId) {
    return null;
  }

  const projectName = shell.bootstrap?.project.name ?? `Project #${shell.projectId}`;

  return (
    <div className={styles.shell}>
      <header className={styles.header}>
        <div className={styles.headerLeft}>
          <NavLink to={shell.buildHref("/app")} className={styles.backLink}>
            ← Hub
          </NavLink>
          <span className={styles.projectName}>{projectName}</span>
          {shell.bootstrap?.schema && (
            <details className={styles.schemaPopover}>
              <summary className={styles.infoIcon} title="Project schema">ⓘ</summary>
              <div className={styles.schemaContent}>
                <p><strong>Translations:</strong> {shell.bootstrap.schema.translation_columns.join(", ")}</p>
                <p><strong>Remarks:</strong> {shell.bootstrap.schema.remark_columns.join(", ") || "none"}</p>
                {shell.bootstrap.schema.pivot_language && (
                  <p><strong>Pivot:</strong> {shell.bootstrap.schema.pivot_language} → {shell.bootstrap.schema.pivoted_languages.join(", ")}</p>
                )}
              </div>
            </details>
          )}
        </div>
        <nav className={styles.tabs}>
          {tabs.map((tab) => (
            <NavLink
              key={tab.to}
              to={shell.buildHref(tab.to)}
              className={({ isActive }) =>
                `${styles.tab} ${isActive ? styles.tabActive : ""}`
              }
            >
              {tab.label}
            </NavLink>
          ))}
        </nav>
      </header>

      {shell.notice && (
        <InlineNotice tone={shell.notice.tone}>
          {shell.notice.message}
          <button onClick={shell.clearNotice}>×</button>
        </InlineNotice>
      )}

      {shell.shellLoading ? (
        <LoadingBlock label="Loading project..." />
      ) : shell.shellError ? (
        <InlineNotice tone="error">{shell.shellError}</InlineNotice>
      ) : (
        <main className={styles.content}>
          <Outlet />
        </main>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Create ProjectShell styles**

Create `frontend/src/app/shell/ProjectShell.module.css`:

```css
.shell {
  width: min(1680px, calc(100vw - 28px));
  margin: 0 auto;
  display: grid;
  gap: 0;
  min-height: 100vh;
}

.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 0;
  border-bottom: 1px solid var(--border);
  flex-wrap: wrap;
  gap: 8px;
}

.headerLeft {
  display: flex;
  align-items: center;
  gap: 12px;
}

.backLink {
  font-size: 13px;
  color: var(--muted);
  text-decoration: none;
  padding: 4px 8px;
  border-radius: 6px;
}

.backLink:hover {
  background: var(--surface-muted);
}

.projectName {
  font-size: 18px;
  font-weight: 700;
  font-family: var(--font-display);
}

.schemaPopover {
  position: relative;
}

.infoIcon {
  cursor: pointer;
  font-size: 16px;
  color: var(--muted);
  list-style: none;
  user-select: none;
}

.infoIcon::-webkit-details-marker {
  display: none;
}

.schemaContent {
  position: absolute;
  top: 100%;
  left: 0;
  z-index: 10;
  background: var(--surface-strong);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 12px 16px;
  box-shadow: var(--shadow-sm);
  min-width: 280px;
  font-size: 13px;
}

.schemaContent p {
  margin: 4px 0;
}

.tabs {
  display: flex;
  gap: 2px;
}

.tab {
  padding: 8px 18px;
  font-size: 14px;
  font-weight: 600;
  color: var(--muted);
  text-decoration: none;
  border-radius: 8px 8px 0 0;
  transition: color 120ms, background 120ms;
}

.tab:hover {
  color: var(--text);
  background: var(--surface-muted);
}

.tabActive {
  color: var(--accent);
  background: var(--surface);
  border: 1px solid var(--border);
  border-bottom-color: var(--surface);
}

.content {
  padding: 18px 0;
}
```

- [ ] **Step 4: Rewrite AppShell to handle both hub and project modes**

The existing `AppShell.tsx` currently manages project state, queries, and the sidebar. Rewrite it to:
1. Keep the project/lang/branch query logic
2. Remove the sidebar rendering
3. Wrap `<Outlet />` so the router decides whether to render Hub or ProjectShell

The key change: `AppShell` becomes a pure state provider. `ProjectShell` handles the tab layout. The hub page renders without tabs.

Rewrite `frontend/src/app/shell/AppShell.tsx` — keep the query hooks (`listProjects`, `getProjectState`, `getBranchSummary`), the `AppShellProvider`, and the URL state management. Remove the sidebar JSX, drawer logic, and replace the rendering section with just `<Outlet />`.

- [ ] **Step 5: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit`

- [ ] **Step 6: Commit**

```bash
git add frontend/src/app/shell/
git commit -m "feat: rewrite AppShell with two-level navigation (hub + project tabs)"
```

---

## Task 7: Router Rewrite

**Files:**
- Rewrite: `frontend/src/app/router.tsx`
- Create: `frontend/src/pages/hub/HubPage.tsx`
- Create: `frontend/src/pages/hub/HubPage.module.css`

- [ ] **Step 1: Create HubPage**

Create `frontend/src/pages/hub/HubPage.tsx`:

```tsx
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { useAppShell } from "@/app/shell/AppShellContext";
import { createProject } from "@/domains/projects/api";
import type { CreateProjectInput } from "@/domains/projects/types";
import { queryKeys } from "@/shared/api/queryKeys";
import { buttonClassName, EmptyState, LoadingBlock } from "@/shared/ui/primitives";

import styles from "@/pages/hub/HubPage.module.css";

export function HubPage() {
  const shell = useAppShell();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);

  const [name, setName] = useState("");
  const [translationCols, setTranslationCols] = useState("");
  const [remarkCols, setRemarkCols] = useState("");
  const [pivotLang, setPivotLang] = useState("");
  const [pivotedLangs, setPivotedLangs] = useState("");

  const createMut = useMutation({
    mutationFn: () => {
      const payload: CreateProjectInput = {
        name,
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
              <span className={styles.cardName}>{p.name}</span>
              <span className={styles.cardMeta}>Created {p.created_at}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Create HubPage styles**

Create `frontend/src/pages/hub/HubPage.module.css`:

```css
.hub {
  width: min(900px, calc(100vw - 40px));
  margin: 40px auto;
  display: grid;
  gap: 24px;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.title {
  margin: 0;
  font-size: 36px;
  font-family: var(--font-display);
}

.cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 14px;
}

.card {
  display: grid;
  gap: 6px;
  padding: 18px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--surface);
  text-align: left;
  cursor: pointer;
  transition: transform 120ms, border-color 120ms;
}

.card:hover {
  transform: translateY(-1px);
  border-color: var(--accent);
}

.cardName {
  font-weight: 700;
  font-size: 16px;
}

.cardMeta {
  font-size: 13px;
  color: var(--muted);
}

.createForm {
  display: grid;
  gap: 12px;
  padding: 20px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--surface);
}

.createForm label {
  display: grid;
  gap: 4px;
  font-size: 13px;
  color: var(--muted);
}

.createForm input {
  padding: 8px 10px;
  border: 1px solid var(--border);
  border-radius: 8px;
  font-size: 14px;
  color: var(--text);
  background: var(--surface-strong);
}

.formActions {
  display: flex;
  gap: 10px;
  margin-top: 4px;
}
```

- [ ] **Step 3: Rewrite router**

Rewrite `frontend/src/app/router.tsx`:

```tsx
import { Navigate, createBrowserRouter } from "react-router-dom";

import { AppShell } from "@/app/shell/AppShell";
import { ProjectShell } from "@/app/shell/ProjectShell";
import { useAppShell } from "@/app/shell/AppShellContext";
import { HubPage } from "@/pages/hub/HubPage";
import { WorkspacePage } from "@/pages/workspace/WorkspacePage";
import { ReleasePage } from "@/pages/release/ReleasePage";
import { DevPage } from "@/pages/dev/DevPage";
import { RunsPage } from "@/pages/runs/RunsPage";

function IndexRedirect() {
  const shell = useAppShell();
  if (shell.projectsLoading) return null;
  return (
    <Navigate
      replace
      to={shell.buildHref(shell.hasProjects ? "/app/workspace" : "/app")}
    />
  );
}

export const router = createBrowserRouter([
  {
    path: "/app",
    element: <AppShell />,
    children: [
      { index: true, element: <HubPage /> },
      {
        element: <ProjectShell />,
        children: [
          { path: "workspace", element: <WorkspacePage /> },
          { path: "release", element: <ReleasePage /> },
          { path: "dev", element: <DevPage /> },
          { path: "runs", element: <RunsPage /> },
        ],
      },
    ],
  },
]);
```

- [ ] **Step 4: Create placeholder pages for WorkspacePage, ReleasePage, DevPage, RunsPage**

Each as a minimal stub that renders a title so the app compiles and navigates:

Example `frontend/src/pages/workspace/WorkspacePage.tsx`:
```tsx
export function WorkspacePage() {
  return <div>Workspace — coming next</div>;
}
```

Create similar stubs for `ReleasePage`, `DevPage`, `RunsPage`.

- [ ] **Step 5: Verify app builds and navigates**

Run: `cd frontend && npx tsc --noEmit`
Run: `npm run build:app`
Test in browser: navigate to `/app` → Hub, select project → `/app/workspace` with top tabs

- [ ] **Step 6: Commit**

```bash
git add frontend/src/app/router.tsx frontend/src/pages/hub/ frontend/src/pages/workspace/ frontend/src/pages/release/ frontend/src/pages/dev/ frontend/src/pages/runs/
git commit -m "feat: rewrite router with hub + project-level tab pages"
```

---

## Task 8: Workspace Page

**Files:**
- Rewrite: `frontend/src/pages/workspace/WorkspacePage.tsx`
- Create: `frontend/src/pages/workspace/WorkspacePage.module.css`

- [ ] **Step 1: Implement WorkspacePage**

Replace the stub with the full implementation. Uses the shared VariantGrid component with project-wide variant query.

```tsx
import { useDeferredValue, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { useAppShell } from "@/app/shell/AppShellContext";
import { getProjectVariants } from "@/domains/variants/api";
import { queryKeys } from "@/shared/api/queryKeys";
import { InlineNotice, LoadingBlock } from "@/shared/ui/primitives";
import { VariantGrid } from "@/shared/ui/VariantGrid";

export function WorkspacePage() {
  const shell = useAppShell();
  const projectId = shell.projectId!;
  const schema = shell.bootstrap!.schema;

  const [stateFilter, setStateFilter] = useState<"active" | "orphan" | "all">("active");
  const [columnFilters, setColumnFilters] = useState<Record<string, string>>({});
  const [columnToggles, setColumnToggles] = useState({ translations: true, remarks: false, pivot: false });
  const [page, setPage] = useState(1);

  const deferredFilters = useDeferredValue(columnFilters);

  const params = {
    state: stateFilter,
    search_business_key: deferredFilters["search_business_key"] || undefined,
    search_source: deferredFilters["search_source"] || undefined,
    branch_ref: deferredFilters["branch"] ? [deferredFilters["branch"]] : undefined,
    page,
    page_size: 100,
  };

  const query = useQuery({
    queryKey: queryKeys.projectVariants(projectId, params),
    queryFn: () => getProjectVariants(projectId, params),
  });

  function handleColumnFilter(column: string, value: string) {
    setColumnFilters((prev) => ({ ...prev, [column]: value }));
    setPage(1);
  }

  if (query.isError) {
    return <InlineNotice tone="error">{String(query.error)}</InlineNotice>;
  }

  return (
    <VariantGrid
      schema={schema}
      rows={query.data?.rows ?? []}
      totalRows={query.data?.total_rows ?? 0}
      page={page}
      pageSize={100}
      onPageChange={setPage}
      columnFilters={columnFilters}
      onColumnFilterChange={handleColumnFilter}
      stateFilter={stateFilter}
      onStateFilterChange={(s) => { setStateFilter(s); setPage(1); }}
      columnToggles={columnToggles}
      onColumnToggleChange={(g, on) => setColumnToggles((prev) => ({ ...prev, [g]: on }))}
    />
  );
}
```

- [ ] **Step 2: Verify in browser**

Run dev server, navigate to `/app/workspace`. Confirm:
- Grid renders with data
- Column filters work (type in business_key header)
- State filter switches between active/orphan/all
- Pagination works
- Column toggles show/hide translation/remark/pivot columns

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/workspace/
git commit -m "feat: implement Workspace page with shared VariantGrid"
```

---

## Task 9: Release Page

**Files:**
- Rewrite: `frontend/src/pages/release/ReleasePage.tsx`
- Create: `frontend/src/pages/release/ReleasePage.module.css`

- [ ] **Step 1: Implement ReleasePage with Browse, Edit, Trash tabs**

```tsx
import { useDeferredValue, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { useAppShell } from "@/app/shell/AppShellContext";
import { getBranchRows } from "@/domains/branches/api";
import { queryKeys, invalidateProject } from "@/shared/api/queryKeys";
import { InlineNotice } from "@/shared/ui/primitives";
import { VariantGrid } from "@/shared/ui/VariantGrid";
import { EditPanel } from "@/shared/ui/EditPanel";
import { TrashPanel } from "@/shared/ui/TrashPanel";
import type { JobDetail } from "@/domains/jobs/types";

import styles from "@/pages/release/ReleasePage.module.css";

type ReleaseTab = "browse" | "edit" | "trash";

export function ReleasePage() {
  const shell = useAppShell();
  const queryClient = useQueryClient();
  const projectId = shell.projectId!;
  const schema = shell.bootstrap!.schema;
  const branchRef = "rel/current";

  const [tab, setTab] = useState<ReleaseTab>("browse");
  const [stateFilter, setStateFilter] = useState<"active" | "orphan" | "all">("active");
  const [columnFilters, setColumnFilters] = useState<Record<string, string>>({});
  const [columnToggles, setColumnToggles] = useState({ translations: true, remarks: false, pivot: false });
  const [page, setPage] = useState(1);

  const deferredFilters = useDeferredValue(columnFilters);
  const browseParams = {
    search_business_key: deferredFilters["search_business_key"] || undefined,
    search_source: deferredFilters["search_source"] || undefined,
    page,
    page_size: 100,
  };

  const browseQuery = useQuery({
    queryKey: queryKeys.branchRows(projectId, branchRef, browseParams),
    queryFn: () => getBranchRows(projectId, branchRef, browseParams),
    enabled: tab === "browse",
  });

  async function handleJobCreated(_job: JobDetail) {
    await invalidateProject(queryClient, projectId);
    shell.notify("Operation completed", "success");
    setTab("browse");
  }

  return (
    <div>
      <nav className={styles.tabs}>
        {(["browse", "edit", "trash"] as ReleaseTab[]).map((t) => (
          <button key={t} className={`${styles.tab} ${tab === t ? styles.tabActive : ""}`} onClick={() => setTab(t)}>
            {t.charAt(0).toUpperCase() + t.slice(1)}
          </button>
        ))}
      </nav>

      {tab === "browse" && (
        <VariantGrid
          schema={schema}
          rows={browseQuery.data?.rows ?? []}
          totalRows={browseQuery.data?.total_rows ?? 0}
          page={page}
          pageSize={100}
          onPageChange={setPage}
          columnFilters={columnFilters}
          onColumnFilterChange={(col, val) => { setColumnFilters((p) => ({ ...p, [col]: val })); setPage(1); }}
          stateFilter={stateFilter}
          onStateFilterChange={(s) => { setStateFilter(s); setPage(1); }}
          columnToggles={columnToggles}
          onColumnToggleChange={(g, on) => setColumnToggles((p) => ({ ...p, [g]: on }))}
        />
      )}

      {tab === "edit" && (
        <EditPanel
          projectId={projectId}
          branchRef={branchRef}
          allowRange={false}
          importBatches={shell.bootstrap?.imports ?? []}
          onJobCreated={handleJobCreated}
        />
      )}

      {tab === "trash" && (
        <TrashPanel
          projectId={projectId}
          branchRef={branchRef}
          showProjectTrash={true}
          onJobCreated={handleJobCreated}
        />
      )}
    </div>
  );
}
```

- [ ] **Step 2: Create ReleasePage styles**

Create `frontend/src/pages/release/ReleasePage.module.css`:

```css
.tabs {
  display: flex;
  gap: 2px;
  margin-bottom: 16px;
}

.tab {
  padding: 8px 18px;
  font-size: 14px;
  font-weight: 600;
  color: var(--muted);
  background: none;
  border: 1px solid transparent;
  border-radius: 8px 8px 0 0;
  cursor: pointer;
}

.tab:hover {
  color: var(--text);
  background: var(--surface-muted);
}

.tabActive {
  color: var(--accent);
  background: var(--surface);
  border-color: var(--border);
  border-bottom-color: transparent;
}
```

- [ ] **Step 3: Verify in browser**

Navigate to `/app/release`. Confirm:
- Browse tab shows rel/current entries
- Edit tab shows Content mutation editor (no Range option)
- Trash tab shows unbind + project trash sections

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/release/
git commit -m "feat: implement Release page with Browse, Edit, Trash tabs"
```

---

## Task 10: Dev Page — Branch List + Import Batches

**Files:**
- Rewrite: `frontend/src/pages/dev/DevPage.tsx`
- Create: `frontend/src/pages/dev/DevPage.module.css`
- Create: `frontend/src/pages/dev/ImportBatches.tsx`

- [ ] **Step 1: Implement DevPage with branch list view**

The Dev page has three sub-views controlled by local state: `list` (default), `create`, `batches`, and `detail:{version}`.

```tsx
import { useState } from "react";

import { useAppShell } from "@/app/shell/AppShellContext";
import type { DevBranchSummary } from "@/domains/branches/types";
import { buttonClassName } from "@/shared/ui/primitives";
import { CreateBranch } from "@/pages/dev/CreateBranch";
import { BranchDetail } from "@/pages/dev/BranchDetail";
import { ImportBatches } from "@/pages/dev/ImportBatches";

import styles from "@/pages/dev/DevPage.module.css";

type DevView =
  | { kind: "list" }
  | { kind: "create" }
  | { kind: "batches" }
  | { kind: "detail"; version: string };

export function DevPage() {
  const shell = useAppShell();
  const projectId = shell.projectId!;
  const devBranches = shell.bootstrap?.dev_branches ?? [];

  const [view, setView] = useState<DevView>({ kind: "list" });

  if (view.kind === "create") {
    return (
      <CreateBranch
        projectId={projectId}
        lang={shell.lang}
        onBack={() => setView({ kind: "list" })}
        onCreated={(version) => {
          shell.refreshShell();
          setView({ kind: "detail", version });
        }}
      />
    );
  }

  if (view.kind === "batches") {
    return (
      <ImportBatches
        projectId={projectId}
        onBack={() => setView({ kind: "list" })}
      />
    );
  }

  if (view.kind === "detail") {
    return (
      <BranchDetail
        projectId={projectId}
        version={view.version}
        onBack={() => setView({ kind: "list" })}
      />
    );
  }

  return (
    <div className={styles.page}>
      <div className={styles.actions}>
        <button className={buttonClassName("primary")} onClick={() => setView({ kind: "create" })}>
          + Create Branch
        </button>
        <button className={buttonClassName("secondary")} onClick={() => setView({ kind: "batches" })}>
          Import Batches
        </button>
      </div>
      <table className={styles.table}>
        <thead>
          <tr>
            <th>Branch</th>
            <th>Status</th>
            <th>Entries</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {devBranches.length === 0 ? (
            <tr><td colSpan={4}>No dev branches yet</td></tr>
          ) : (
            devBranches.map((b) => (
              <tr key={b.version}>
                <td>{b.branch_ref}</td>
                <td>{b.bootstrap_state}</td>
                <td>{b.entry_count}</td>
                <td>
                  <button className={buttonClassName("ghost")} onClick={() => setView({ kind: "detail", version: b.version })}>
                    Open
                  </button>
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
```

- [ ] **Step 2: Create ImportBatches view**

Create `frontend/src/pages/dev/ImportBatches.tsx`:

```tsx
import { useQuery } from "@tanstack/react-query";

import { getImports, getImportReport } from "@/domains/imports/api";
import { queryKeys } from "@/shared/api/queryKeys";
import { buttonClassName, LoadingBlock, InlineNotice, StatGrid } from "@/shared/ui/primitives";
import { useState } from "react";

import styles from "@/pages/dev/DevPage.module.css";

export function ImportBatches(props: { projectId: number; onBack: () => void }) {
  const { projectId, onBack } = props;
  const [selectedBatchId, setSelectedBatchId] = useState<number | null>(null);

  const batchesQuery = useQuery({
    queryKey: queryKeys.imports(projectId),
    queryFn: () => getImports(projectId),
  });

  const reportQuery = useQuery({
    queryKey: queryKeys.importReport(projectId, selectedBatchId!),
    queryFn: () => getImportReport(projectId, selectedBatchId!),
    enabled: selectedBatchId !== null,
  });

  return (
    <div className={styles.page}>
      <button className={buttonClassName("ghost")} onClick={onBack}>← Back to list</button>
      <h2>Import Batches</h2>

      {batchesQuery.isLoading && <LoadingBlock label="Loading batches..." />}
      {batchesQuery.isError && <InlineNotice tone="error">{String(batchesQuery.error)}</InlineNotice>}

      {batchesQuery.data && (
        <table className={styles.table}>
          <thead>
            <tr><th>ID</th><th>Files</th><th>Rows</th><th>Issues</th><th>Created</th><th></th></tr>
          </thead>
          <tbody>
            {batchesQuery.data.map((b) => (
              <tr key={b.import_batch_id}>
                <td>#{b.import_batch_id}</td>
                <td>{b.files_scanned}</td>
                <td>{b.rows_scanned}</td>
                <td>{b.issues}</td>
                <td>{b.created_at}</td>
                <td>
                  <button className={buttonClassName("ghost")} onClick={() => setSelectedBatchId(b.import_batch_id)}>
                    Report
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {selectedBatchId && reportQuery.data && (
        <div>
          <h3>Batch #{selectedBatchId} Report</h3>
          <StatGrid items={Object.entries(reportQuery.data.summary).map(([k, v]) => ({ label: k, value: String(v) }))} />
          <table className={styles.table}>
            <thead>
              <tr>{reportQuery.data.rows.length > 0 && Object.keys(reportQuery.data.rows[0]).map((k) => <th key={k}>{k}</th>)}</tr>
            </thead>
            <tbody>
              {reportQuery.data.rows.slice(0, 20).map((row, i) => (
                <tr key={i}>{Object.values(row).map((v, j) => <td key={j}>{String(v ?? "")}</td>)}</tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Create DevPage styles**

Create `frontend/src/pages/dev/DevPage.module.css`:

```css
.page {
  display: grid;
  gap: 16px;
}

.actions {
  display: flex;
  gap: 10px;
}

.table {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
}

.table th,
.table td {
  border: 1px solid var(--border);
  padding: 8px 12px;
  text-align: left;
}

.table th {
  background: var(--surface-muted);
  font-weight: 600;
  font-size: 13px;
}

.table tr:hover td {
  background: var(--surface);
}
```

- [ ] **Step 4: Create stub files for CreateBranch and BranchDetail**

Create `frontend/src/pages/dev/CreateBranch.tsx`:
```tsx
export function CreateBranch(props: { projectId: number; lang: string; onBack: () => void; onCreated: (version: string) => void }) {
  return <div>CreateBranch — coming next <button onClick={props.onBack}>Back</button></div>;
}
```

Create `frontend/src/pages/dev/BranchDetail.tsx`:
```tsx
export function BranchDetail(props: { projectId: number; version: string; onBack: () => void }) {
  return <div>BranchDetail for {props.version} — coming next <button onClick={props.onBack}>Back</button></div>;
}
```

- [ ] **Step 5: Verify TypeScript compiles and navigate in browser**

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/dev/
git commit -m "feat: implement Dev page branch list and import batches views"
```

---

## Task 11: Dev Page — Create Branch Flow

**Files:**
- Rewrite: `frontend/src/pages/dev/CreateBranch.tsx`

The stepped wizard: Upload → Preview/Bootstrap → Done (with fill/export option).

- [ ] **Step 1: Implement CreateBranch component**

```tsx
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { previewImportUpload, confirmImportUpload } from "@/domains/imports/api";
import { previewBootstrap, bootstrapBranch } from "@/domains/branches/api";
import { runFillUpload } from "@/domains/workflows/api";
import type { ImportUploadPreview } from "@/domains/imports/types";
import type { EffectForecastPreview } from "@/domains/branches/types";
import type { JobDetail } from "@/domains/jobs/types";
import { invalidateProject } from "@/shared/api/queryKeys";
import { buttonClassName, InlineNotice, LoadingBlock, StatGrid } from "@/shared/ui/primitives";
import { FolderUpload } from "@/shared/ui/FolderUpload";
import { buildJobArtifactHref } from "@/domains/jobs/api";

import styles from "@/pages/dev/DevPage.module.css";

type Step = "upload" | "preview" | "done";

export function CreateBranch(props: {
  projectId: number;
  lang: string;
  onBack: () => void;
  onCreated: (version: string) => void;
}) {
  const { projectId, lang, onBack, onCreated } = props;
  const queryClient = useQueryClient();

  const [step, setStep] = useState<Step>("upload");
  const [version, setVersion] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [uploadPreview, setUploadPreview] = useState<ImportUploadPreview | null>(null);
  const [importBatchId, setImportBatchId] = useState<number | null>(null);
  const [bootstrapPreview, setBootstrapPreview] = useState<EffectForecastPreview | null>(null);
  const [bootstrapResult, setBootstrapResult] = useState<JobDetail | null>(null);
  const [fillResult, setFillResult] = useState<JobDetail | null>(null);

  const previewUploadMut = useMutation({
    mutationFn: () => previewImportUpload(projectId, files),
    onSuccess: (data) => setUploadPreview(data),
  });

  const confirmUploadMut = useMutation({
    mutationFn: () => confirmImportUpload(projectId, uploadPreview!.upload_session_id, null),
    onSuccess: async (jobDetail) => {
      const batchId = (jobDetail.job.input as { import_batch_id?: number }).import_batch_id ??
        (jobDetail.job.summary as { import_batch_id?: number }).import_batch_id;
      if (batchId) {
        setImportBatchId(batchId);
        const bsPreview = await previewBootstrap(projectId, { branch_ref: `dev/${version}`, import_batch_id: batchId });
        setBootstrapPreview(bsPreview);
        setStep("preview");
      }
    },
  });

  const bootstrapMut = useMutation({
    mutationFn: () => bootstrapBranch(projectId, { branch_ref: `dev/${version}`, import_batch_id: importBatchId! }),
    onSuccess: async (data) => {
      setBootstrapResult(data);
      await invalidateProject(queryClient, projectId);
      setStep("done");
    },
  });

  const fillMut = useMutation({
    mutationFn: () => runFillUpload(projectId, lang, files),
    onSuccess: (data) => setFillResult(data),
  });

  const branchRef = `dev/${version}`;

  if (step === "upload") {
    return (
      <div className={styles.page}>
        <button className={buttonClassName("ghost")} onClick={onBack}>← Back</button>
        <h2>Create Branch</h2>
        <label>
          Version number
          <input value={version} onChange={(e) => setVersion(e.target.value)} placeholder="2.2.3" />
        </label>
        <p style={{ color: "var(--muted)", fontSize: 13 }}>Branch will be created as <strong>{branchRef}</strong></p>
        <FolderUpload label="Upload workbook folder" onFiles={(f) => { setFiles(f); previewUploadMut.reset(); setUploadPreview(null); }} />
        {files.length > 0 && <p>{files.length} files selected</p>}

        {!uploadPreview && files.length > 0 && (
          <button className={buttonClassName("secondary")} disabled={!version.trim() || previewUploadMut.isPending} onClick={() => previewUploadMut.mutate()}>
            {previewUploadMut.isPending ? "Previewing upload..." : "Preview Upload"}
          </button>
        )}

        {previewUploadMut.isError && <InlineNotice tone="error">{String(previewUploadMut.error)}</InlineNotice>}

        {uploadPreview && (
          <div>
            <StatGrid items={[
              { label: "Files", value: uploadPreview.file_count },
              { label: "Sheets", value: uploadPreview.sheet_count },
            ]} />
            <button
              className={buttonClassName("primary")}
              disabled={confirmUploadMut.isPending}
              onClick={() => confirmUploadMut.mutate()}
            >
              {confirmUploadMut.isPending ? "Creating batch & previewing bootstrap..." : "Next: Preview Bootstrap"}
            </button>
          </div>
        )}
        {confirmUploadMut.isError && <InlineNotice tone="error">{String(confirmUploadMut.error)}</InlineNotice>}
      </div>
    );
  }

  if (step === "preview") {
    return (
      <div className={styles.page}>
        <h2>Bootstrap Preview — {branchRef}</h2>
        {bootstrapPreview && (
          <>
            <StatGrid items={Object.entries(bootstrapPreview.summary).map(([k, v]) => ({ label: k, value: String(v) }))} />
            <table className={styles.table}>
              <thead>
                <tr>{bootstrapPreview.rows.length > 0 && Object.keys(bootstrapPreview.rows[0]).map((k) => <th key={k}>{k}</th>)}</tr>
              </thead>
              <tbody>
                {bootstrapPreview.rows.slice(0, 30).map((row, i) => (
                  <tr key={i}>{Object.values(row).map((v, j) => <td key={j}>{String(v ?? "")}</td>)}</tr>
                ))}
              </tbody>
            </table>
          </>
        )}
        <button
          className={buttonClassName("primary")}
          disabled={bootstrapMut.isPending}
          onClick={() => bootstrapMut.mutate()}
        >
          {bootstrapMut.isPending ? "Bootstrapping..." : "Execute Bootstrap"}
        </button>
        {bootstrapMut.isError && <InlineNotice tone="error">{String(bootstrapMut.error)}</InlineNotice>}
      </div>
    );
  }

  // step === "done"
  return (
    <div className={styles.page}>
      <h2>Branch Created — {branchRef}</h2>
      {bootstrapResult && (
        <StatGrid items={Object.entries(bootstrapResult.report.summary).map(([k, v]) => ({ label: k, value: String(v) }))} />
      )}
      <div className={styles.actions}>
        <button className={buttonClassName("secondary")} disabled={fillMut.isPending} onClick={() => fillMut.mutate()}>
          {fillMut.isPending ? "Filling..." : "Export for Translation"}
        </button>
        <button className={buttonClassName("primary")} onClick={() => onCreated(version)}>
          Go to Branch
        </button>
      </div>
      {fillMut.isError && <InlineNotice tone="error">{String(fillMut.error)}</InlineNotice>}
      {fillResult && (
        <InlineNotice tone="success">
          Fill complete.
          {fillResult.job.artifact_path && (
            <> <a href={buildJobArtifactHref(projectId, fillResult.job)} download>Download ZIP</a></>
          )}
        </InlineNotice>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Verify in browser**

Test the full Create Branch flow: enter version → upload folder → preview → bootstrap → done → fill/export

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/dev/CreateBranch.tsx
git commit -m "feat: implement Create Branch flow with bootstrap and fill/export"
```

---

## Task 12: Dev Page — Branch Detail

**Files:**
- Rewrite: `frontend/src/pages/dev/BranchDetail.tsx`

Branch detail with Browse, Edit, Replace, Trash tabs.

- [ ] **Step 1: Implement BranchDetail component**

```tsx
import { useDeferredValue, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";

import { useAppShell } from "@/app/shell/AppShellContext";
import { getBranchRows, previewBranchReplace, executeBranchReplace } from "@/domains/branches/api";
import type { EffectForecastPreview } from "@/domains/branches/types";
import type { JobDetail } from "@/domains/jobs/types";
import { queryKeys, invalidateProject } from "@/shared/api/queryKeys";
import { buttonClassName, InlineNotice, StatGrid } from "@/shared/ui/primitives";
import { VariantGrid } from "@/shared/ui/VariantGrid";
import { EditPanel } from "@/shared/ui/EditPanel";
import { TrashPanel } from "@/shared/ui/TrashPanel";

import styles from "@/pages/dev/DevPage.module.css";

type DetailTab = "browse" | "edit" | "replace" | "trash";

export function BranchDetail(props: { projectId: number; version: string; onBack: () => void }) {
  const { projectId, version, onBack } = props;
  const shell = useAppShell();
  const queryClient = useQueryClient();
  const branchRef = `dev/${version}`;

  const [tab, setTab] = useState<DetailTab>("browse");
  const [stateFilter, setStateFilter] = useState<"active" | "orphan" | "all">("active");
  const [columnFilters, setColumnFilters] = useState<Record<string, string>>({});
  const [columnToggles, setColumnToggles] = useState({ translations: true, remarks: false, pivot: false });
  const [page, setPage] = useState(1);
  const [replacePreview, setReplacePreview] = useState<EffectForecastPreview | null>(null);

  const deferredFilters = useDeferredValue(columnFilters);
  const browseParams = {
    search_business_key: deferredFilters["search_business_key"] || undefined,
    search_source: deferredFilters["search_source"] || undefined,
    page,
    page_size: 100,
  };

  const browseQuery = useQuery({
    queryKey: queryKeys.branchRows(projectId, branchRef, browseParams),
    queryFn: () => getBranchRows(projectId, branchRef, browseParams),
    enabled: tab === "browse",
  });

  const replacePreviewMut = useMutation({
    mutationFn: () => previewBranchReplace(projectId, branchRef, "rel/current"),
    onSuccess: (data) => setReplacePreview(data),
  });

  const replaceExecMut = useMutation({
    mutationFn: () => executeBranchReplace(projectId, branchRef, "rel/current"),
    onSuccess: async () => {
      await invalidateProject(queryClient, projectId);
      shell.notify("Replace complete", "success");
      setReplacePreview(null);
    },
  });

  async function handleJobCreated(_job: JobDetail) {
    await invalidateProject(queryClient, projectId);
    shell.notify("Operation completed", "success");
    setTab("browse");
  }

  const schema = shell.bootstrap!.schema;

  return (
    <div className={styles.page}>
      <div className={styles.actions}>
        <button className={buttonClassName("ghost")} onClick={onBack}>← Back to list</button>
        <strong>{branchRef}</strong>
      </div>

      <nav style={{ display: "flex", gap: 2 }}>
        {(["browse", "edit", "replace", "trash"] as DetailTab[]).map((t) => (
          <button key={t} className={buttonClassName(tab === t ? "primary" : "ghost")} onClick={() => setTab(t)}>
            {t.charAt(0).toUpperCase() + t.slice(1)}
          </button>
        ))}
      </nav>

      {tab === "browse" && (
        <VariantGrid
          schema={schema}
          rows={browseQuery.data?.rows ?? []}
          totalRows={browseQuery.data?.total_rows ?? 0}
          page={page}
          pageSize={100}
          onPageChange={setPage}
          columnFilters={columnFilters}
          onColumnFilterChange={(col, val) => { setColumnFilters((p) => ({ ...p, [col]: val })); setPage(1); }}
          stateFilter={stateFilter}
          onStateFilterChange={(s) => { setStateFilter(s); setPage(1); }}
          columnToggles={columnToggles}
          onColumnToggleChange={(g, on) => setColumnToggles((p) => ({ ...p, [g]: on }))}
        />
      )}

      {tab === "edit" && (
        <EditPanel
          projectId={projectId}
          branchRef={branchRef}
          allowRange={true}
          importBatches={shell.bootstrap?.imports ?? []}
          onJobCreated={handleJobCreated}
        />
      )}

      {tab === "replace" && (
        <div className={styles.page}>
          <p>Replace <strong>{branchRef}</strong> → <strong>rel/current</strong></p>
          {!replacePreview && (
            <button className={buttonClassName("secondary")} disabled={replacePreviewMut.isPending} onClick={() => replacePreviewMut.mutate()}>
              {replacePreviewMut.isPending ? "Loading preview..." : "Preview Replace"}
            </button>
          )}
          {replacePreviewMut.isError && <InlineNotice tone="error">{String(replacePreviewMut.error)}</InlineNotice>}
          {replacePreview && (
            <>
              <StatGrid items={Object.entries(replacePreview.summary).map(([k, v]) => ({ label: k, value: String(v) }))} />
              <table className={styles.table}>
                <thead>
                  <tr>{replacePreview.rows.length > 0 && Object.keys(replacePreview.rows[0]).map((k) => <th key={k}>{k}</th>)}</tr>
                </thead>
                <tbody>
                  {replacePreview.rows.slice(0, 50).map((row, i) => (
                    <tr key={i}>{Object.values(row).map((v, j) => <td key={j}>{String(v ?? "")}</td>)}</tr>
                  ))}
                </tbody>
              </table>
              <button className={buttonClassName("primary")} disabled={replaceExecMut.isPending} onClick={() => replaceExecMut.mutate()}>
                {replaceExecMut.isPending ? "Replacing..." : "Execute Replace"}
              </button>
            </>
          )}
          {replaceExecMut.isError && <InlineNotice tone="error">{String(replaceExecMut.error)}</InlineNotice>}
        </div>
      )}

      {tab === "trash" && (
        <TrashPanel
          projectId={projectId}
          branchRef={branchRef}
          showProjectTrash={false}
          onJobCreated={handleJobCreated}
        />
      )}
    </div>
  );
}
```

- [ ] **Step 2: Verify in browser**

Navigate to Dev → Open a branch. Confirm all 4 tabs work.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/dev/BranchDetail.tsx
git commit -m "feat: implement Dev branch detail with Browse, Edit, Replace, Trash tabs"
```

---

## Task 13: Runs Page

**Files:**
- Rewrite: `frontend/src/pages/runs/RunsPage.tsx`
- Create: `frontend/src/pages/runs/RunsPage.module.css`

Jobs + Fill + QA + Export tabs.

- [ ] **Step 1: Implement RunsPage**

```tsx
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";

import { useAppShell } from "@/app/shell/AppShellContext";
import { getJobs, getJobDetail, buildJobArtifactHref } from "@/domains/jobs/api";
import { runFillUpload, runQaUpload } from "@/domains/workflows/api";
import { queryKeys, invalidateProject } from "@/shared/api/queryKeys";
import { buttonClassName, InlineNotice, LoadingBlock, StatGrid } from "@/shared/ui/primitives";
import { FolderUpload } from "@/shared/ui/FolderUpload";

import styles from "@/pages/runs/RunsPage.module.css";

type RunsTab = "jobs" | "fill" | "qa" | "export";

export function RunsPage() {
  const shell = useAppShell();
  const queryClient = useQueryClient();
  const projectId = shell.projectId!;

  const [tab, setTab] = useState<RunsTab>("jobs");
  const [expandedJobId, setExpandedJobId] = useState<number | null>(null);

  // --- Fill state ---
  const [fillFiles, setFillFiles] = useState<File[]>([]);
  const [fillLang, setFillLang] = useState(shell.lang);
  // --- QA state ---
  const [qaFiles, setQaFiles] = useState<File[]>([]);
  const [qaLang, setQaLang] = useState(shell.lang);

  const jobsQuery = useQuery({
    queryKey: queryKeys.jobs(projectId),
    queryFn: () => getJobs(projectId),
    refetchInterval: (query) => {
      const data = query.state.data;
      if (data && data.some((j) => j.status === "running")) return 1000;
      return false;
    },
  });

  const jobDetailQuery = useQuery({
    queryKey: queryKeys.jobDetail(projectId, expandedJobId!),
    queryFn: () => getJobDetail(projectId, expandedJobId!),
    enabled: expandedJobId !== null,
  });

  const fillMut = useMutation({
    mutationFn: () => runFillUpload(projectId, fillLang, fillFiles),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.jobs(projectId) });
      setFillFiles([]);
      setTab("jobs");
    },
  });

  const qaMut = useMutation({
    mutationFn: () => runQaUpload(projectId, qaLang, qaFiles),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.jobs(projectId) });
      setQaFiles([]);
      setTab("jobs");
    },
  });

  const langs = shell.bootstrap?.schema.translation_columns ?? [];

  return (
    <div>
      <nav className={styles.tabs}>
        {(["jobs", "fill", "qa", "export"] as RunsTab[]).map((t) => (
          <button key={t} className={`${styles.tab} ${tab === t ? styles.tabActive : ""}`} onClick={() => setTab(t)}>
            {t.charAt(0).toUpperCase() + t.slice(1)}
          </button>
        ))}
      </nav>

      {tab === "jobs" && (
        <div className={styles.jobList}>
          {jobsQuery.isLoading && <LoadingBlock label="Loading jobs..." />}
          {jobsQuery.data?.map((job) => (
            <div key={job.job_id} className={styles.jobCard}>
              <div className={styles.jobHeader} onClick={() => setExpandedJobId(expandedJobId === job.job_id ? null : job.job_id)}>
                <span>#{job.job_id}</span>
                <span>{job.job_type}</span>
                <span className={job.status === "running" ? styles.running : job.status === "failed" ? styles.failed : styles.success}>
                  {job.status}
                </span>
                <span>{job.created_at}</span>
                {job.artifact_path && (
                  <a href={buildJobArtifactHref(projectId, job)} download onClick={(e) => e.stopPropagation()}>
                    Download
                  </a>
                )}
              </div>
              {expandedJobId === job.job_id && jobDetailQuery.data && (
                <div className={styles.jobDetail}>
                  <StatGrid items={Object.entries(jobDetailQuery.data.report.summary).map(([k, v]) => ({ label: k, value: String(v) }))} />
                  {jobDetailQuery.data.report.rows.length > 0 && (
                    <table className={styles.reportTable}>
                      <thead>
                        <tr>{Object.keys(jobDetailQuery.data.report.rows[0]).map((k) => <th key={k}>{k}</th>)}</tr>
                      </thead>
                      <tbody>
                        {jobDetailQuery.data.report.rows.slice(0, 12).map((row, i) => (
                          <tr key={i}>{Object.values(row).map((v, j) => <td key={j}>{String(v ?? "")}</td>)}</tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {tab === "fill" && (
        <div className={styles.uploadForm}>
          <h3>Fill Translation</h3>
          <label>Target language <select value={fillLang} onChange={(e) => setFillLang(e.target.value)}>
            {langs.map((l) => <option key={l} value={l}>{l}</option>)}
          </select></label>
          <FolderUpload label="Select workbook folder" onFiles={setFillFiles} />
          {fillFiles.length > 0 && <p>{fillFiles.length} files selected</p>}
          <button className={buttonClassName("primary")} disabled={fillFiles.length === 0 || fillMut.isPending} onClick={() => fillMut.mutate()}>
            {fillMut.isPending ? "Running fill..." : "Run Fill"}
          </button>
          {fillMut.isError && <InlineNotice tone="error">{String(fillMut.error)}</InlineNotice>}
        </div>
      )}

      {tab === "qa" && (
        <div className={styles.uploadForm}>
          <h3>QA Scan</h3>
          <label>Target language <select value={qaLang} onChange={(e) => setQaLang(e.target.value)}>
            {langs.map((l) => <option key={l} value={l}>{l}</option>)}
          </select></label>
          <FolderUpload label="Select workbook folder" onFiles={setQaFiles} />
          {qaFiles.length > 0 && <p>{qaFiles.length} files selected</p>}
          <button className={buttonClassName("primary")} disabled={qaFiles.length === 0 || qaMut.isPending} onClick={() => qaMut.mutate()}>
            {qaMut.isPending ? "Running QA..." : "Run QA Scan"}
          </button>
          {qaMut.isError && <InlineNotice tone="error">{String(qaMut.error)}</InlineNotice>}
        </div>
      )}

      {tab === "export" && (
        <div className={styles.uploadForm}>
          <h3>Export Variants</h3>
          <InlineNotice tone="info">Export requires a new backend endpoint (not yet implemented).</InlineNotice>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Create RunsPage styles**

Create `frontend/src/pages/runs/RunsPage.module.css`:

```css
.tabs {
  display: flex;
  gap: 2px;
  margin-bottom: 16px;
}

.tab {
  padding: 8px 18px;
  font-size: 14px;
  font-weight: 600;
  color: var(--muted);
  background: none;
  border: 1px solid transparent;
  border-radius: 8px 8px 0 0;
  cursor: pointer;
}

.tab:hover {
  color: var(--text);
  background: var(--surface-muted);
}

.tabActive {
  color: var(--accent);
  background: var(--surface);
  border-color: var(--border);
  border-bottom-color: transparent;
}

.jobList {
  display: grid;
  gap: 8px;
}

.jobCard {
  border: 1px solid var(--border);
  border-radius: 8px;
  overflow: hidden;
}

.jobHeader {
  display: flex;
  gap: 16px;
  padding: 10px 14px;
  cursor: pointer;
  font-size: 13px;
  align-items: center;
}

.jobHeader:hover {
  background: var(--surface-muted);
}

.jobDetail {
  padding: 12px 14px;
  border-top: 1px solid var(--border);
  display: grid;
  gap: 12px;
}

.running { color: var(--info); font-weight: 600; }
.failed { color: var(--danger); font-weight: 600; }
.success { color: var(--accent); font-weight: 600; }

.reportTable {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}

.reportTable th,
.reportTable td {
  border: 1px solid var(--border);
  padding: 4px 8px;
  text-align: left;
}

.reportTable th {
  background: var(--surface-muted);
  font-weight: 600;
}

.uploadForm {
  display: grid;
  gap: 12px;
  max-width: 500px;
}

.uploadForm label {
  display: grid;
  gap: 4px;
  font-size: 13px;
  color: var(--muted);
}

.uploadForm select {
  padding: 8px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface);
}
```

- [ ] **Step 3: Verify in browser**

Navigate to Runs. Confirm Jobs list, Fill upload, QA upload all work.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/runs/
git commit -m "feat: implement Runs page with Jobs, Fill, QA, Export tabs"
```

---

## Task 14: Cleanup Old Pages

**Files:**
- Delete: `frontend/src/pages/overview/`
- Delete: `frontend/src/pages/branches/`
- Delete: `frontend/src/pages/intake/`
- Delete: `frontend/src/pages/project/`
- Delete: `frontend/src/pages/variants/`
- Delete: `frontend/src/features/variant-drawer/`
- Delete: `frontend/src/features/import-preview/`
- Delete: `frontend/src/features/job-detail/`

- [ ] **Step 1: Remove old page directories**

```bash
rm -rf frontend/src/pages/overview frontend/src/pages/branches frontend/src/pages/intake frontend/src/pages/project frontend/src/pages/variants
rm -rf frontend/src/features/variant-drawer frontend/src/features/import-preview frontend/src/features/job-detail
```

- [ ] **Step 2: Remove any stale imports in AppShell.tsx or other files**

Grep for imports referencing deleted paths and remove them.

- [ ] **Step 3: Verify TypeScript compiles and app builds**

Run: `cd frontend && npx tsc --noEmit`
Run: `npm run build:app`

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "chore: remove old pages replaced by frontend redesign"
```

---

## Task 15: Update E2E Tests

**Files:**
- Modify: `tests/e2e/product-app.spec.js`

The existing e2e tests navigate to `/app/overview`, `/app/branches`, `/app/intake`, etc. Update them to use the new routes.

- [ ] **Step 1: Update route references in product-app.spec.js**

Replace:
- `/app/overview` → `/app/workspace`
- `/app/branches` → `/app/dev` or `/app/release` depending on context
- `/app/intake` → `/app/dev` (upload is now part of Create Branch)
- `/app/project` → `/app` (hub)
- `/app/variants` → `/app/workspace` (no separate variants page)

- [ ] **Step 2: Run e2e tests**

Run: `npm run test:e2e`
Fix any broken selectors or navigation steps.

- [ ] **Step 3: Commit**

```bash
git add tests/e2e/
git commit -m "test: update e2e tests for new frontend page routes"
```

---

## Task 16: Update Docs

**Files:**
- Modify: `docs/contracts.md` — update SPA routes section
- Modify: `docs/user-guide.md` — update navigation references
- Run: `.venv/Scripts/python.exe scripts/validate_docs.py`

- [ ] **Step 1: Update docs/contracts.md SPA routes**

Replace the old route table with:

| Route | Page | Purpose |
|-------|------|---------|
| `/app` | HubPage | Project list, create project |
| `/app/workspace` | WorkspacePage | Project-wide variant grid, Excel-like browser |
| `/app/release` | ReleasePage | rel/current browse, edit, trash |
| `/app/dev` | DevPage | Dev branch list, create, detail, replace |
| `/app/runs` | RunsPage | Job history, fill, QA, export |

- [ ] **Step 2: Run docs validator**

Run: `.venv/Scripts/python.exe scripts/validate_docs.py`
Fix any broken links or references.

- [ ] **Step 3: Commit**

```bash
git add docs/
git commit -m "docs: update SPA routes and navigation references for frontend redesign"
```

---

## Task 17: Final Build Verification

- [ ] **Step 1: Full TypeScript check**

Run: `cd frontend && npx tsc --noEmit`

- [ ] **Step 2: Production build**

Run: `npm run build:app`

- [ ] **Step 3: Backend tests**

Run: `.venv/Scripts/python.exe -m pytest -q`

- [ ] **Step 4: E2E tests**

Run: `npm run test:e2e`

- [ ] **Step 5: Manual browser walkthrough**

Verify in browser:
1. `/app` — Hub shows projects, create project works
2. `/app/workspace` — Grid loads, column filters work, column toggles work, pagination works
3. `/app/release` — Browse/Edit/Trash tabs work
4. `/app/dev` — Branch list, Create Branch flow (upload → preview → bootstrap → fill/export → go to branch), Branch Detail (browse/edit/replace/trash)
5. `/app/runs` — Jobs list, Fill trigger, QA trigger
6. Tab navigation and ← Hub link work correctly

- [ ] **Step 6: Final commit if any fixes needed**

```bash
git add -A
git commit -m "fix: final adjustments from build verification"
```
