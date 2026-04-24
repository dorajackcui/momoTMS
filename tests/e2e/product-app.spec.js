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

test("Dev create branch uses workbook panel with preview and execute", async ({
  page,
}) => {
  let previewCalled = false;
  let executePayload = null;

  await page.route("**/api/projects/1/workbooks/intake/preview", async (route) => {
    previewCalled = true;
    await route.fulfill({
      json: {
        upload_session_id: "session-for-create-branch",
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
    executePayload = route.request().postDataJSON();
    await route.fulfill({
      json: buildJobDetail({
        job_id: 900,
        job_type: "workbook_create_branch",
        status: "running",
      }),
    });
  });

  await page.route("**/api/projects/1/jobs/900", async (route) => {
    await route.fulfill({
      json: buildJobDetail({
        job_id: 900,
        job_type: "workbook_create_branch",
        status: "success",
        summary: { workbook_batch_id: 321 },
        finished_at: "2026-03-25T00:00:01Z",
      }),
    });
  });

  await page.goto("/app/dev?project=1&lang=fr");
  await page.getByRole("button", { name: /Create Branch/ }).click();
  await page.getByLabel("Version number").fill("2.4.9");
  await page.locator('input[type="file"]').setInputFiles(importDir);
  await page.getByRole("button", { name: "Check Workbook" }).click();

  await expect.poll(() => previewCalled).toBeTruthy();
  await expect(page.getByRole("button", { name: "Create Branch" }).last()).toBeVisible();

  await page.getByRole("button", { name: "Create Branch" }).last().click();
  await expect.poll(() => executePayload).not.toBeNull();
  expect(executePayload.upload_session_id).toBe("session-for-create-branch");
  expect(executePayload.workflow_kind).toBe("create_branch");
});

test("Release edit shows workbook mutation type selector", async ({
  page,
}) => {
  await page.goto("/app/release?project=1&lang=fr");
  await page.getByRole("button", { name: "Edit" }).click();

  await expect(page.getByText("Mutation type")).toBeVisible();
  await expect(page.getByText("Content")).toBeVisible();
  await expect(page.getByText("Range")).toBeVisible();
  await expect(page.getByText("Upload workbook")).toBeVisible();

  // Old UI elements should not be present
  await expect(page.locator("textarea")).toHaveCount(0);
  await expect(page.getByText("Input method")).toHaveCount(0);
  await expect(page.getByText("Direct")).toHaveCount(0);
  await expect(page.getByText("Import batch")).toHaveCount(0);
});

test("Workspace reflects state and branch filters in URL and API params", async ({
  page,
  request,
}) => {
  await seedDevBranch(request);

  const variantRequests = [];
  await page.route("**/api/projects/1/variants?*", async (route) => {
    const url = new URL(route.request().url());
    variantRequests.push({
      state: url.searchParams.get("state"),
      branchRefs: url.searchParams.getAll("branch_ref"),
    });
    await route.continue();
  });

  await page.goto("/app/workspace?project=1&lang=fr&state=all");
  await expect(page.getByTestId("product-app")).toBeVisible();
  await expect.poll(() => variantRequests.some((item) => item.state === "all")).toBeTruthy();

  await page.getByLabel(/Branch:/).selectOption("rel/current");
  await expect.poll(() => new URL(page.url()).searchParams.get("branch")).toBe("rel/current");
  await expect
    .poll(() => variantRequests.some((item) => item.branchRefs.includes("rel/current")))
    .toBeTruthy();
});

test("Release trash shows workbook upload panel and calls correct API", async ({
  page,
}) => {
  let trashPreviewPayload = null;

  await page.route("**/api/projects/1/workbooks/intake/preview", async (route) => {
    trashPreviewPayload = route.request().postDataJSON();
    await route.fulfill({
      json: {
        upload_session_id: "session-for-trash",
        workflow_kind: "branch_trash",
        mutation_type: null,
        file_count: 1,
        sheet_count: 1,
        missing_required_headers: [],
        sampled_issue_count: 0,
        sheet_previews: [],
      },
    });
  });

  await page.goto("/app/release?project=1&lang=fr");
  await page.getByRole("button", { name: "Trash" }).click();

  await expect(page.getByText("Upload key workbook")).toBeVisible();
  await expect(page.getByText("Delete From Branch")).toBeVisible();
  await expect(page.getByText("Trash orphan variants")).toBeVisible();

  // Old UI elements should not be present
  await expect(page.locator("textarea")).toHaveCount(0);
  await expect(page.getByText("Preview unbind")).toHaveCount(0);
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

test("Dev create branch workbook panel shows error on execute failure", async ({
  page,
}) => {
  await page.route("**/api/projects/1/workbooks/intake/preview", async (route) => {
    await route.fulfill({
      json: {
        upload_session_id: "session-that-will-fail",
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
    await route.fulfill({
      json: buildJobDetail({
        job_id: 901,
        job_type: "workbook_create_branch",
        status: "running",
      }),
    });
  });
  await page.route("**/api/projects/1/jobs/901", async (route) => {
    await route.fulfill({
      json: buildJobDetail({
        job_id: 901,
        job_type: "workbook_create_branch",
        status: "failed",
        error_message: "workbook import failed for test",
        finished_at: "2026-03-25T00:00:01Z",
      }),
    });
  });

  await page.goto("/app/dev?project=1&lang=fr");
  await page.getByRole("button", { name: /Create Branch/ }).click();
  await page.getByLabel("Version number").fill("2.4.8");
  await page.locator('input[type="file"]').setInputFiles(importDir);
  await page.getByRole("button", { name: "Check Workbook" }).click();

  await expect(page.getByRole("button", { name: "Create Branch" }).last()).toBeVisible();
  await page.getByRole("button", { name: "Create Branch" }).last().click();
  await expect(page.getByText(/workbook import failed for test/)).toBeVisible();
});
