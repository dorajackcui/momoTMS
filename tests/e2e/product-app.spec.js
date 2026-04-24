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

test("Dev create branch waits for the import job before bootstrap preview", async ({
  page,
}) => {
  let jobPolls = 0;
  let bootstrapPayload = null;

  await page.route("**/api/projects/1/imports/upload-folder/preview", async (route) => {
    await route.fulfill({
      json: {
        upload_session_id: "session-for-create-branch",
        file_count: 1,
        sheet_count: 1,
        sheet_previews: [],
      },
    });
  });
  await page.route("**/api/projects/1/imports/upload-folder", async (route) => {
    await route.fulfill({
      json: buildJobDetail({
        job_id: 900,
        job_type: "import_upload_folder",
        status: "running",
      }),
    });
  });
  await page.route("**/api/projects/1/jobs/900", async (route) => {
    jobPolls += 1;
    await route.fulfill({
      json: buildJobDetail({
        job_id: 900,
        job_type: "import_upload_folder",
        status: "success",
        summary: { import_batch_id: 321 },
        finished_at: "2026-03-25T00:00:01Z",
      }),
    });
  });
  await page.route("**/api/projects/1/branches/bootstrap/preview", async (route) => {
    bootstrapPayload = route.request().postDataJSON();
    await route.fulfill({
      json: {
        preview_kind: "effect_forecast",
        workflow_kind: "branch_bootstrap",
        request_echo: bootstrapPayload,
        summary: { processed_count: 1 },
        rows: [{ status: "CREATED_AND_BOUND_VARIANT" }],
      },
    });
  });

  await page.goto("/app/dev?project=1&lang=fr");
  await page.getByRole("button", { name: /Create Branch/ }).click();
  await page.getByLabel("Version number").fill("2.4.9");
  await page.locator('input[type="file"]').setInputFiles(importDir);
  await page.getByRole("button", { name: "Preview Upload" }).click();
  await page.getByRole("button", { name: "Next: Preview Bootstrap" }).click();

  await expect(page.getByRole("heading", { name: /Bootstrap Preview/ })).toBeVisible();
  expect(jobPolls).toBeGreaterThan(0);
  expect(bootstrapPayload.import_batch_id).toBe(321);
});

test("Release direct edit maps TSV columns into mutation preview payload", async ({
  page,
}) => {
  let previewPayload = null;

  await page.route("**/api/projects/1/branches/mutations/preview", async (route) => {
    previewPayload = route.request().postDataJSON();
    await route.fulfill({
      json: {
        preview_kind: "effect_forecast",
        workflow_kind: "branch_mutation",
        request_echo: previewPayload,
        summary: { processed_count: 1 },
        rows: [{ status: "UPDATED_BOUND_VARIANT" }],
      },
    });
  });

  await page.goto("/app/release?project=1&lang=fr");
  await page.getByRole("button", { name: "Edit" }).click();
  await page.locator("textarea").fill(
    [
      "business_key\tsource\tfr\tremark:context\tfile_name",
      "common.welcome\tWelcome {0}\tBienvenue!\tReviewed\twelcome.xlsx",
    ].join("\n"),
  );
  await page.getByRole("button", { name: "Preview" }).click();

  await expect.poll(() => previewPayload).not.toBeNull();
  const change = previewPayload.input.changes[0];
  expect(change.translations_by_lang).toEqual({ fr: "Bienvenue!" });
  expect(change.remarks_by_key).toEqual({ context: "Reviewed" });
  expect(change.file_name).toBe("welcome.xlsx");
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

test("Release trash requires preview before execute", async ({
  page,
}) => {
  let unbindCalls = 0;

  await page.route("**/api/projects/1/variants/trash/delete", async (route) => {
    unbindCalls += 1;
    await route.fulfill({
      json: buildJobDetail({
        job_type: "trash_delete",
        status: "success",
        summary: { removed_binding_count: 1 },
        finished_at: "2026-03-25T00:00:01Z",
      }),
    });
  });

  await page.goto("/app/release?project=1&lang=fr");
  await page.getByRole("button", { name: "Trash" }).click();
  await page.locator("textarea").first().fill("common.welcome");
  await expect(page.getByRole("button", { name: "Execute unbind" })).toHaveCount(0);
  await page.getByRole("button", { name: "Preview unbind" }).click();
  await expect(page.getByRole("button", { name: "Execute unbind" })).toBeVisible();
  expect(unbindCalls).toBe(0);

  await page.getByRole("button", { name: "Execute unbind" }).click();
  await expect.poll(() => unbindCalls).toBe(1);
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

test("Dev create branch keeps upload preview visible when import job fails", async ({
  page,
}) => {
  await page.route("**/api/projects/1/imports/upload-folder/preview", async (route) => {
    await route.fulfill({
      json: {
        upload_session_id: "session-that-will-fail",
        file_count: 1,
        sheet_count: 1,
        sheet_previews: [],
      },
    });
  });
  await page.route("**/api/projects/1/imports/upload-folder", async (route) => {
    await route.fulfill({
      json: buildJobDetail({
        job_id: 901,
        job_type: "import_upload_folder",
        status: "running",
      }),
    });
  });
  await page.route("**/api/projects/1/jobs/901", async (route) => {
    await route.fulfill({
      json: buildJobDetail({
        job_id: 901,
        job_type: "import_upload_folder",
        status: "failed",
        error_message: "import failed for test",
        finished_at: "2026-03-25T00:00:01Z",
      }),
    });
  });

  await page.goto("/app/dev?project=1&lang=fr");
  await page.getByRole("button", { name: /Create Branch/ }).click();
  await page.getByLabel("Version number").fill("2.4.8");
  await page.locator('input[type="file"]').setInputFiles(importDir);
  await page.getByRole("button", { name: "Preview Upload" }).click();
  await page.getByRole("button", { name: "Next: Preview Bootstrap" }).click();

  await expect(page.getByText(/import failed for test/)).toBeVisible();
  await expect(page.getByRole("button", { name: "Next: Preview Bootstrap" })).toBeVisible();
});
