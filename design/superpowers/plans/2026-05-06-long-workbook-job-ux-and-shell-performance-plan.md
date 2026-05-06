# Long Workbook Job UX And Shell Performance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make 200k-row workbook branch creation behave as a durable background workflow in the product UI, without false frontend timeouts or shell-level blocking reads after the job succeeds.

**Architecture:** Treat workbook workflow execution as job submission plus job-state rendering, not as a promise that must resolve within a fixed timeout. Keep the backend job API contract intact, add a frontend polling hook for durable jobs, and remove the eager heavy branch summary query from `AppShell`; branch state resolution should use the lightweight project state payload.

**Tech Stack:** React, TypeScript, TanStack Query, Playwright e2e, FastAPI job APIs, SQLite-backed read models.

---

## Scope Check

Root cause evidence:

- The real `dev/2.5.4` create-branch job took about 160 seconds and finished with `status = success`.
- The frontend helper `waitForJobDetail()` waits only `500ms * 120 = 60s`, then throws `job did not finish before the preview timeout`.
- `AppShell` eagerly calls `/api/projects/{project_id}/branches?lang=...`; on the 200k project that route scans hundreds of thousands of branch projections and measured in the multi-second range.

In scope:

- Replace `WorkbookWorkflowPanel`'s fixed-timeout wait with durable job polling.
- Show running/success/failed job state in the workbook panel.
- Call `onJobCompleted()` exactly once when the job reaches success.
- Remove eager branch summary loading from `AppShell`.
- Resolve valid branch refs from project state: `rel/current` plus `dev_branches`.
- Add frontend e2e regression coverage for long-running jobs and shell loading without branch summary.
- Update active docs only where user-facing workflow wording changes.

Out of scope:

- Do not increase `maxAttempts` as the fix.
- Do not make workbook execution synchronous.
- Do not change backend job route contracts.
- Do not optimize Excel parsing in this change.
- Do not rewrite branch bootstrap SQL in this change.
- Do not add local desktop workbook paths to tests or docs.

## File Structure

Frontend job lifecycle:

- Create: `frontend/src/domains/jobs/useJobDetailPolling.ts`
  - Owns job detail polling for a single job id.
  - Polls while status is `running`.
  - Does not convert "still running" into an error.
- Modify: `frontend/src/shared/ui/WorkbookWorkflowPanel.tsx`
  - Submits workflow once, stores active job id, renders active job status, reacts to success/failure.
  - Stops using `waitForJobDetail()` for product UI execution.
- Modify: `frontend/src/domains/jobs/api.ts`
  - Keep `getJobDetail()` and `waitForJobDetail()` available for non-UI helper use, but do not route long product workflows through the fixed timeout helper.

Shell loading:

- Modify: `frontend/src/app/shell/AppShell.tsx`
  - Remove `getBranchSummary()` query from shell bootstrap.
  - Resolve branch refs from project state only.
  - Stop treating branch summary failures or loading as shell failures.
- Modify: `frontend/src/app/shell/AppShellContext.tsx`
  - Remove `branchSummary` from the shell context if no component uses it after the shell cleanup.
- Modify: `frontend/src/shared/api/queryKeys.ts`
  - Keep `branchSummary()` and invalidation if the endpoint remains available, but no shell code should require it.

Tests:

- Modify: `tests/e2e/product-app.spec.js`
  - Add a long-running workbook job regression.
  - Add a shell-loading regression that fails if `/branches?lang=...` is required by `/app/dev`.

Docs:

- Modify: `docs/user-guide.md` only if the create-branch user flow wording needs to mention background job state.
- Modify: `docs/contracts.md` only if response contracts change. They should not.
- Modify: `docs/testing.md` only if verification commands change. They should not.

---

### Task 1: Lock The Long-Running Job UX Regression

**Files:**

- Modify: `tests/e2e/product-app.spec.js`

- [ ] **Step 1: Add a helper that returns a running workbook job**

Add this helper below `buildJobDetail()`:

```js
function buildRunningWorkbookJob(jobId = 902) {
  return buildJobDetail({
    job_id: jobId,
    job_type: "workbook_create_branch",
    status: "running",
    summary: {},
    finished_at: null,
  });
}
```

- [ ] **Step 2: Add the failing long-job test**

Append this test near the existing Dev create-branch workbook panel tests:

```js
test("Dev create branch keeps showing a running job instead of timing out", async ({
  page,
}) => {
  let jobPollCount = 0;

  await page.route("**/api/projects/1/workbooks/intake/preview", async (route) => {
    await route.fulfill({
      json: {
        upload_session_id: "session-for-long-create-branch",
        workflow_kind: "create_branch",
        mutation_type: null,
        file_count: 1,
        sheet_count: 1,
        missing_required_headers: [],
        sampled_issue_count: 0,
        sheet_previews: [],
      },
    });
  });

  await page.route("**/api/projects/1/workbooks/intake/execute", async (route) => {
    await route.fulfill({ json: buildRunningWorkbookJob(902) });
  });

  await page.route("**/api/projects/1/jobs/902", async (route) => {
    jobPollCount += 1;
    await route.fulfill({ json: buildRunningWorkbookJob(902) });
  });

  await page.goto("/app/dev?project=1&lang=fr");
  await page.getByRole("button", { name: /Create Branch/ }).click();
  await page.getByLabel("Version number").fill("2.5.4");
  await page.getByRole("button", { name: "or upload folder" }).click();
  await page.locator('input[type="file"]').setInputFiles(importDir);
  await page.getByRole("button", { name: "Check Workbook" }).click();
  await page.getByRole("button", { name: "Create Branch" }).last().click();

  await expect(page.getByText(/Job #902/)).toBeVisible();
  await expect(page.getByText(/running/i)).toBeVisible();
  await expect(page.getByText(/preview timeout/i)).toHaveCount(0);
  await expect.poll(() => jobPollCount).toBeGreaterThan(0);
});
```

- [ ] **Step 3: Run the focused e2e test and verify it fails**

Run:

```powershell
npm run test:e2e -- tests/e2e/product-app.spec.js -g "keeps showing a running job"
```

Expected before implementation: FAIL because the panel does not expose a durable running job state.

- [ ] **Step 4: Commit the failing test**

```powershell
git add tests/e2e/product-app.spec.js
git commit -m "test: cover long workbook job polling"
```

---

### Task 2: Introduce Durable Job Polling For Workbook Workflows

**Files:**

- Create: `frontend/src/domains/jobs/useJobDetailPolling.ts`
- Modify: `frontend/src/shared/ui/WorkbookWorkflowPanel.tsx`

- [ ] **Step 1: Create the polling hook**

Create `frontend/src/domains/jobs/useJobDetailPolling.ts`:

```ts
import { useQuery } from "@tanstack/react-query";

import { getJobDetail } from "@/domains/jobs/api";
import type { JobDetail } from "@/domains/jobs/types";
import { queryKeys } from "@/shared/api/queryKeys";

export function useJobDetailPolling(
  projectId: number,
  jobId: number | null,
  options: { pollMs?: number } = {},
) {
  const pollMs = options.pollMs ?? 1000;

  return useQuery<JobDetail>({
    queryKey: jobId === null
      ? ["job-detail", projectId, "idle"]
      : queryKeys.jobDetail(projectId, jobId),
    queryFn: () => getJobDetail(projectId, jobId!),
    enabled: jobId !== null,
    refetchInterval: (query) => {
      const detail = query.state.data;
      return detail?.job.status === "running" ? pollMs : false;
    },
  });
}
```

- [ ] **Step 2: Replace fixed-timeout waiting in the workbook panel**

In `frontend/src/shared/ui/WorkbookWorkflowPanel.tsx`:

- remove the `waitForJobDetail` import
- import `useEffect`, `useRef`, and `useJobDetailPolling`
- add state for `activeJobId`
- have `executeMut` return the submitted `JobDetail` immediately
- let the polling hook drive final success/failure UI

The key shape should be:

```tsx
const [activeJobId, setActiveJobId] = useState<number | null>(null);
const completedJobIdRef = useRef<number | null>(null);
const activeJobQuery = useJobDetailPolling(props.projectId, activeJobId);
const activeJob = activeJobQuery.data ?? null;

const executeMut = useMutation({
  mutationFn: async () => {
    if (!preview) throw new Error("Preview is required before execute");
    const started = await executeWorkbookWorkflow(props.projectId, {
      upload_session_id: preview.upload_session_id,
      workflow_kind: props.workflowKind,
      branch_ref: props.branchRef,
      mutation_type: props.mutationType,
    });
    setActiveJobId(started.job.job_id);
    return started;
  },
});

useEffect(() => {
  if (!activeJob) return;
  if (activeJob.job.status === "success") {
    if (completedJobIdRef.current === activeJob.job.job_id) return;
    completedJobIdRef.current = activeJob.job.job_id;
    setCompletedJob(activeJob);
    props.onJobCompleted(activeJob);
    return;
  }
  if (activeJob.job.status === "failed") {
    setCompletedJob(null);
  }
}, [activeJob, props]);
```

- [ ] **Step 3: Render running and failed job state**

In the panel body, render the active job state above completed summary:

```tsx
{activeJob && (
  <div className={styles.preview}>
    <StatGrid
      items={[
        { label: "Job", value: `#${activeJob.job.job_id}` },
        { label: "Status", value: activeJob.job.status },
        ...Object.entries(activeJob.job.summary).map(([label, value]) => ({
          label,
          value: String(value),
        })),
      ]}
    />
    {activeJob.job.status === "failed" && (
      <InlineNotice tone="error">
        {activeJob.job.error_message || "Workbook workflow failed"}
      </InlineNotice>
    )}
  </div>
)}
```

Keep the button text as `Running...` while `executeMut.isPending` or `activeJob?.job.status === "running"`.

- [ ] **Step 4: Clear active job state on new file selection**

Inside the `onFiles` handler, add:

```tsx
setActiveJobId(null);
completedJobIdRef.current = null;
```

- [ ] **Step 5: Run the long-job e2e regression**

Run:

```powershell
npm run test:e2e -- tests/e2e/product-app.spec.js -g "keeps showing a running job"
```

Expected: PASS.

- [ ] **Step 6: Run existing workbook panel e2e coverage**

Run:

```powershell
npm run test:e2e -- tests/e2e/product-app.spec.js -g "Dev create branch"
```

Expected: PASS for success, failure, and long-running cases.

- [ ] **Step 7: Commit**

```powershell
git add frontend/src/domains/jobs/useJobDetailPolling.ts frontend/src/shared/ui/WorkbookWorkflowPanel.tsx tests/e2e/product-app.spec.js
git commit -m "feat: track workbook workflows as durable jobs"
```

---

### Task 3: Stop AppShell From Requiring Heavy Branch Summary

**Files:**

- Modify: `tests/e2e/product-app.spec.js`
- Modify: `frontend/src/app/shell/AppShell.tsx`
- Modify: `frontend/src/app/shell/AppShellContext.tsx`

- [ ] **Step 1: Add the failing shell regression**

Append this test near the stale branch param test:

```js
test("Dev page shell does not require heavy branch summary", async ({ page }) => {
  let branchSummaryRequested = false;

  await page.route("**/api/projects/1/branches?*", async (route) => {
    branchSummaryRequested = true;
    await route.fulfill({
      status: 500,
      json: { detail: "branch summary should not be required for shell load" },
    });
  });

  await page.goto("/app/dev?project=1&lang=fr");

  await expect(page.getByTestId("product-app")).toBeVisible();
  await expect(page.getByRole("button", { name: /Create Branch/ })).toBeVisible();
  await expect(page.getByText(/Failed to load shell data/)).toHaveCount(0);
  expect(branchSummaryRequested).toBeFalsy();
});
```

- [ ] **Step 2: Run the shell regression and verify it fails**

Run:

```powershell
npm run test:e2e -- tests/e2e/product-app.spec.js -g "does not require heavy branch summary"
```

Expected before implementation: FAIL because `AppShell` currently requests `/branches?lang=...`.

- [ ] **Step 3: Remove branch summary query from AppShell**

In `frontend/src/app/shell/AppShell.tsx`:

- remove `getBranchSummary` import
- remove `BranchListResponse` import if unused
- delete `branchSummaryQuery`
- call `resolveBranchRef(requestedBranch, projectStateQuery.data)`
- remove branch summary from `shellError`
- remove branch summary from `shellLoading`
- remove `branchSummary` from `shellValue`
- remove `branchSummary` invalidation from `refreshShell`

The resolver should become:

```tsx
function resolveBranchRef(
  requestedBranchRef: string | null,
  bootstrap: ProductStateResponse | undefined,
) {
  const branchRefs = new Set<string>(["rel/current"]);
  bootstrap?.dev_branches.forEach((branch) => branchRefs.add(branch.branch_ref));
  if (requestedBranchRef && branchRefs.has(requestedBranchRef)) {
    return requestedBranchRef;
  }
  if (!bootstrap) {
    return null;
  }
  return bootstrap.dev_branches[0]?.branch_ref || "rel/current";
}
```

- [ ] **Step 4: Remove branch summary from shell context**

In `frontend/src/app/shell/AppShellContext.tsx`:

- remove `BranchListResponse` import
- remove this field from `AppShellContextValue`:

```ts
branchSummary: BranchListResponse | null;
```

- [ ] **Step 5: Run the shell regression**

Run:

```powershell
npm run test:e2e -- tests/e2e/product-app.spec.js -g "does not require heavy branch summary"
```

Expected: PASS.

- [ ] **Step 6: Run stale branch param regression**

Run:

```powershell
npm run test:e2e -- tests/e2e/product-app.spec.js -g "normalizes stale branch params"
```

Expected: PASS. This proves branch param normalization still works using project state alone.

- [ ] **Step 7: Commit**

```powershell
git add frontend/src/app/shell/AppShell.tsx frontend/src/app/shell/AppShellContext.tsx tests/e2e/product-app.spec.js
git commit -m "perf: keep branch summary out of app shell"
```

---

### Task 4: Keep Backend Contracts Stable

**Files:**

- Test: `tests/test_variant_api.py`
- Modify docs only if the test reveals a real contract drift.

- [ ] **Step 1: Run workbook workflow API tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_variant_api.py -k "workbook_workflow_create_branch or job"
```

Expected: PASS. The backend still starts jobs asynchronously and returns `JobDetail`.

- [ ] **Step 2: Run branch workflow tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_branch_service.py tests/test_io_flows.py
```

Expected: PASS.

- [ ] **Step 3: Inspect docs only if behavior wording changed**

Run:

```powershell
rg -n "create dev branch|Create Branch|background job|workbook workflow|branch summary" docs
```

Expected: no route contract changes. If user-facing docs imply create-branch blocks until completion in the same page action, update `docs/user-guide.md`.

- [ ] **Step 4: Commit docs if needed**

If docs changed:

```powershell
git add docs/user-guide.md docs/contracts.md docs/testing.md
git commit -m "docs: clarify workbook workflow job handling"
```

If no docs changed, skip this commit.

---

### Task 5: Product Build And Final Verification

**Files:**

- No planned code files beyond previous tasks.

- [ ] **Step 1: Typecheck/build frontend**

Run:

```powershell
npm run build:app
```

Expected: PASS.

- [ ] **Step 2: Run product e2e smoke**

Run:

```powershell
npm run test:e2e -- tests/e2e/product-app.spec.js
```

Expected: PASS.

- [ ] **Step 3: Run focused backend workflow regression**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_tdd_branch_cycle.py tests/test_variant_api.py -k "workbook_workflow_create_branch or job or branch_cycle"
```

Expected: PASS.

- [ ] **Step 4: Run large workflow smoke as acceptance evidence**

Run with explicit local workbook paths supplied by the operator, not committed to the repo:

```powershell
.\.venv\Scripts\python.exe scripts\run_branch_cycle_smoke.py --reset --runtime-root data\branch_cycle_smoke_big --release-workbook <path-to-release.xlsx> --dev-workbook <path-to-dev.xlsx> --content-progress-interval 10000 --max-content-seconds 0
```

Expected: PASS. Record:

```text
release bulk seed elapsed
bootstrap workbook batch elapsed
dev branch bootstrap elapsed
content mutation workbook batch elapsed
dev content mutation elapsed
```

- [ ] **Step 5: Manual product acceptance**

Start the app normally, create a dev branch with a 200k workbook, and verify:

- the panel shows `Job #...` with `running`
- no `preview timeout` error appears while the job is still running
- after backend success, the panel renders the success summary
- reopening `/app/dev` does not depend on `/api/projects/{project_id}/branches?lang=...`
- `dev/<version>` appears with the bootstrapped entry count from project state

- [ ] **Step 6: Check for private local paths**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_private_paths.py
```

Expected: pytest PASS. Do not spell private local usernames or desktop paths in the plan, tests, docs, or committed scripts.

- [ ] **Step 7: Final status**

Run:

```powershell
git status --short
```

Expected: only intentional tracked changes, plus any pre-existing untracked local profiling scripts.

---

## Self-Review

Spec coverage:

- False frontend timeout is covered by Task 1 and Task 2.
- Shell-level card/loading is covered by Task 3.
- Backend contract stability is covered by Task 4.
- Large workbook acceptance is covered by Task 5.

Patch avoidance:

- The plan does not increase the timeout limit.
- The plan does not add a route-specific catch block.
- The plan moves workbook UI to a durable job lifecycle model and removes the shell dependency on heavy branch summary data.

Residual risk:

- Backend create-branch can still take minutes for 200k workbooks. That is acceptable for this plan if the product presents it as a background job.
- `/api/projects/{project_id}/branches?lang=...` remains expensive. This plan removes it from shell startup; a later plan can optimize the branch summary read model if a page needs that comparison summary interactively.
