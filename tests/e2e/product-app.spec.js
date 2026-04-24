const path = require("path");
const { test, expect } = require("./test");

const importDir = path.join(
  process.cwd(),
  "data",
  "demo_samples",
  "core-cycle",
  "import_bundle",
);
const fillDir = path.join(
  process.cwd(),
  "data",
  "demo_samples",
  "core-cycle",
  "fill_source",
);

test.beforeEach(async ({ request }) => {
  const response = await request.post("/api/demo/reset");
  expect(response.ok()).toBeTruthy();
});

async function waitForJob(request, startedDetail, projectId = 1) {
  let current = startedDetail;
  for (let attempt = 0; attempt < 120; attempt += 1) {
    if (current.job.status !== "running") {
      return current;
    }
    await new Promise((resolve) => setTimeout(resolve, 50));
    const response = await request.get(
      `/api/projects/${projectId}/jobs/${current.job.job_id}`,
    );
    expect(response.ok()).toBeTruthy();
    current = await response.json();
  }
  throw new Error(`job #${startedDetail.job.job_id} did not finish in time`);
}

async function expectBranchParam(page, expectedBranch) {
  await expect.poll(() => {
    const branch = new URL(page.url()).searchParams.get("branch");
    return branch === null ? null : branch;
  }).toBe(expectedBranch);
}

async function createImportBatch(request, projectId = 1) {
  const response = await request.post(`/api/projects/${projectId}/imports/directory`, {
    data: { input_dir: importDir },
  });
  expect(response.ok()).toBeTruthy();
  const startedDetail = await response.json();
  const completedDetail = await waitForJob(request, startedDetail, projectId);
  expect(completedDetail.job.status).toBe("success");
  return Number(completedDetail.job.summary.import_batch_id);
}

async function applyImportBatch(
  request,
  { projectId = 1, branchRef = "dev/2.4.3", importBatchId },
) {
  const response = await request.post(`/api/projects/${projectId}/branches/mutations`, {
    data: {
      branch_ref: branchRef,
      input: {
        kind: "import_batch",
        import_batch_id: importBatchId,
      },
    },
  });
  expect(response.ok()).toBeTruthy();
  const startedDetail = await response.json();
  const completedDetail = await waitForJob(request, startedDetail, projectId);
  expect(completedDetail.job.status).toBe("success");
  return completedDetail;
}

async function seedDevBranch(request, branchRef = "dev/2.4.3", projectId = 1) {
  const importBatchId = await createImportBatch(request, projectId);
  await applyImportBatch(request, { projectId, branchRef, importBatchId });
}

async function createPivotProject(request, name) {
  const response = await request.post("/api/projects", {
    data: {
      name,
      translation_columns: ["fr", "en"],
      remark_columns: ["context"],
      pivot_language: "en",
      pivoted_languages: ["fr"],
    },
  });
  expect(response.ok()).toBeTruthy();
  return response.json();
}

async function applyDirectMutation(
  request,
  {
    projectId,
    branchRef = "dev/2.4.3",
    businessKey,
    source,
    translationsByLang,
    remarksByKey = {},
    fileName,
  },
) {
  const response = await request.post(`/api/projects/${projectId}/branches/mutations`, {
    data: {
      branch_ref: branchRef,
      input: {
        kind: "direct",
        changes: [
          {
            business_key: businessKey,
            ...(source === undefined ? {} : { source }),
            ...(fileName === undefined ? {} : { file_name: fileName }),
            translations_by_lang: translationsByLang,
            remarks_by_key: remarksByKey,
          },
        ],
      },
    },
  });
  expect(response.ok()).toBeTruthy();
  const detail = await response.json();
  expect(detail.job.status).toBe("success");
  return detail;
}

function buildJobDetail(overrides = {}) {
  return {
    job: {
      job_id: 999,
      project_id: 1,
      job_type: "import_upload_folder",
      status: "running",
      input: {},
      summary: {},
      report_path: null,
      artifact_path: null,
      error_message: null,
      created_at: "2026-03-25T00:00:00Z",
      finished_at: null,
      ...overrides,
    },
    report: {
      summary: {},
      rows: [],
    },
  };
}

// TODO: redesign — the intake page (/app/intake) and project page (/app/project) no longer exist.
// Create-project is now done via HubPage (/app) and import upload is done via Dev page (/app/dev).
// The old test IDs (intake-page, intake-folder-input, intake-import-dialog, project-page,
// project-create-button, shell-project-select) are no longer rendered.
test.skip("keeps first-project import apply target local until a dev branch is entered", async ({
  page,
}) => {
  // Previously used /app/project and /app/intake which no longer exist.
  // Replaced by HubPage (/app) create flow and Dev page (/app/dev) import flow.
  await page.goto("/app");
  await expect(page).toHaveURL(/\/app\/workspace\?/);
  await expectBranchParam(page, null);
});

// TODO: redesign — this test exercised the old six-surface workflow:
// overview (/app/overview), intake (/app/intake), branches (/app/branches with tab=scope/replace),
// variants (/app/variants), and variant drawer (Restore variant button).
// All of these pages and UI elements are removed. The new workflow uses:
// Hub (/app), Workspace (/app/workspace), Dev (/app/dev), Runs (/app/runs).
// shell-project-select no longer exists in AppShell.
// tab=scope and tab=replace query params are removed (Dev page uses local view state).
test.skip("loads the rebuilt product app and exercises the new six-surface workflow", async ({
  page,
  request,
}) => {
  // Previously covered: project select, intake upload, branch scope/lookup/replace,
  // variants workspace restore. Needs full redesign for new UI.
  void page, request;
});

// TODO: redesign — the /app/overview route is gone; workspace is now at /app/workspace.
// The overview-branch-select test ID no longer exists. WorkspacePage does not render
// a branch selector in the same pattern. This test needs to be redesigned against
// the new WorkspacePage branch filtering UX.
test.skip("overview branch filter clears canonical branch state for project-wide mode", async ({
  page,
  request,
}) => {
  await seedDevBranch(request);
  // Previously navigated to /app/overview and checked overview-branch-select.
  // That selector and page no longer exist.
  void page;
});

// TODO: redesign — the /app/variants route is gone. Variant browsing is now in
// WorkspacePage (/app/workspace). The variants-page, variants-results-list test IDs,
// variants-review-button, and per-row article cards no longer exist in the new UI.
test.skip("reviews changed pivot variants from the variants workspace", async ({
  page,
  request,
}) => {
  // Previously used /app/variants with variants-page, variants-results-list,
  // and per-card checkboxes. Needs redesign for WorkspacePage grid.
  void page, request;
});

test("normalizes stale branch params before branch-scoped pages query data", async ({
  page,
}) => {
  // /app/overview → /app/workspace (workspace is the branch-scoped entry page)
  await page.goto("/app/workspace?project=1&lang=fr&branch=dev%2F9.9.9");

  await expect(page).toHaveURL(/branch=rel%2Fcurrent/);
  await expect(page.getByTestId("product-app")).toBeVisible();
  await expect(page.getByText("Failed to load shell data")).toHaveCount(0);
});

// TODO: redesign — the /app/intake route no longer exists. Import upload is now
// part of the Dev page (/app/dev) via the Create Branch flow. The intake-page,
// intake-folder-input, intake-import-dialog, and intake-confirm-import test IDs
// are no longer rendered anywhere.
test.skip("keeps the intake preview open when the import job finishes as failed", async ({
  page,
}) => {
  // Previously mocked /api/projects/1/imports/upload-folder/preview and tested
  // that the intake dialog stays open on failure. Needs redesign for Dev page upload flow.
  void page;
});
