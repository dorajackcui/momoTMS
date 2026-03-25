const path = require("path");
const { test, expect } = require("@playwright/test");

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

async function createProject(page, name) {
  await page.goto("/app/project");
  await expect(page.getByTestId("project-page")).toBeVisible();
  await page.getByLabel("Project name").fill(name);
  await page.getByLabel("Translation columns").fill("fr, en");
  await page.getByLabel("Remark columns").fill("context");
  await page.getByTestId("project-create-button").click();
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
        mark_as_candidate_release: true,
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

test("keeps first-project import apply target local until a dev branch is entered", async ({
  page,
}) => {
  await page.goto("/app");
  await expect(page).toHaveURL(/\/app\/overview\?/);

  await createProject(page, "Fresh Project");
  await expect(page).toHaveURL(/\/app\/overview\?/);
  await expect(page.getByTestId("shell-project-select")).toHaveValue("2");

  await page.goto("/app/intake?project=2&lang=fr&branch=rel%2Fcurrent");
  await expect(page.getByTestId("intake-page")).toBeVisible();
  await page.getByTestId("intake-folder-input").setInputFiles(importDir);
  await expect(page.getByTestId("intake-import-dialog")).toBeVisible();
  await page.getByTestId("intake-confirm-import").click();

  await expect(page).toHaveURL(/\/app\/branches\?.*project=2.*tab=apply/);
  await expect(page.getByLabel("Target branch")).toHaveValue("");
  await expect(
    page.getByRole("button", { name: "Apply import batch" }),
  ).toBeDisabled();

  await page.getByLabel("Target branch").fill("dev/2.4.3");
  await expect(
    page.getByRole("button", { name: "Apply import batch" }),
  ).toBeEnabled();
  await page.getByRole("button", { name: "Apply import batch" }).click();

  await expect(page).toHaveURL(/\/app\/runs\?.*job=/);
  await expect(page.getByTestId("runs-page")).toContainText("Branch Mutation");
});

test("loads the rebuilt product app and exercises the new six-surface workflow", async ({
  page,
}) => {
  const seenApiPaths = new Set();

  page.on("request", (request) => {
    const parsed = new URL(request.url());
    if (parsed.pathname.startsWith("/api/")) {
      seenApiPaths.add(parsed.pathname);
    }
  });

  await page.goto("/app");
  await expect(page).toHaveURL(/\/app\/overview\?/);
  await expect(page.getByTestId("overview-page")).toBeVisible();

  await createProject(page, "Fresh Project");
  await expect(page).toHaveURL(/\/app\/overview\?/);
  await expect(page.getByTestId("shell-project-select")).toHaveValue("2");

  await page.getByTestId("shell-project-select").selectOption("1");
  await expect(page).toHaveURL(/project=1/);

  await page.goto("/app/intake?project=1&lang=fr&branch=rel%2Fcurrent");
  await expect(page.getByTestId("intake-page")).toBeVisible();
  await page.getByTestId("intake-folder-input").setInputFiles(importDir);
  await expect(page.getByTestId("intake-import-dialog")).toBeVisible();
  await page.getByTestId("intake-confirm-import").click();

  await expect(page).toHaveURL(/\/app\/branches\?.*tab=apply/);
  await page.getByLabel("Target branch").fill("dev/2.4.3");
  await page.getByRole("button", { name: "Apply import batch" }).click();

  await expect(page).toHaveURL(/\/app\/runs\?.*job=/);
  await expect(page.getByTestId("runs-page")).toContainText("Branch Mutation");

  await page.goto("/app/overview?project=1&lang=fr&branch=dev%2F2.4.3");
  await expect(page.getByTestId("overview-page")).toContainText("dev.mutable");
  await page.getByRole("button", { name: "dev.mutable" }).click();
  await expect(page.getByText("Variant history", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "dev.mutable" })).toBeVisible();
  await page.getByRole("button", { name: "Close" }).click();

  await page.goto("/app/branches?project=1&lang=fr&branch=dev%2F2.4.3&tab=compare");
  await expect(page.getByTestId("branches-page")).toBeVisible();
  await expect(page.getByText("rel.locked.changed")).toBeVisible();

  await page.getByRole("button", { name: "Queue" }).click();
  await expect(page.getByText("dev.new.entry")).toBeVisible();

  await page.getByRole("button", { name: "Lookup" }).click();
  await page.getByLabel("Business key").fill("rel.locked.same");
  await page.getByRole("button", { name: "Lookup key" }).click();
  await expect(page.getByRole("cell", { name: "rel.locked.same" }).first()).toBeVisible();

  await page.getByRole("button", { name: "Trash / Restore" }).click();
  await page.getByLabel("Delete business keys").fill("dev.new.entry");
  await page.getByRole("button", { name: "Delete from branch" }).click();

  await expect(page).toHaveURL(/\/app\/runs\?.*job=/);
  await page.goto("/app/variants?project=1&lang=fr&branch=dev%2F2.4.3");
  await page.getByLabel("Business key lookup").fill("dev.new.entry");
  await page.getByTestId("variants-lookup-button").click();
  await expect(page.getByTestId("variants-page")).toContainText("variant #");
  await page.getByRole("button", { name: "Restore variant" }).click();

  await expect(page).toHaveURL(/\/app\/runs\?.*job=/);
  await page.getByLabel("Fill folder").setInputFiles(fillDir);
  await expect(page.getByTestId("runs-page")).toContainText("Fill Upload Folder");

  await page.getByLabel("QA folder").setInputFiles(fillDir);
  await expect(page.getByTestId("runs-page")).toContainText("Qa Upload Folder");

  await page.goto("/app/branches?project=1&lang=fr&branch=dev%2F2.4.3&tab=replace");
  await page.getByRole("button", { name: "Preview replace" }).click();
  await expect(page.getByText("source_branch_ref")).toBeVisible();
  await page.getByRole("button", { name: "Execute replace" }).click();
  await expect(page).toHaveURL(/\/app\/runs\?.*job=/);
  await expect(page.getByTestId("runs-page")).toContainText("Branch Replace Execute");

  expect(
    [...seenApiPaths].some(
      (pathName) =>
        pathName === "/api/state" ||
        pathName.startsWith("/api/strings") ||
        pathName.startsWith("/api/scopes/") ||
        pathName.startsWith("/api/dev-versions"),
    ),
  ).toBeFalsy();
  expect(
    [...seenApiPaths].some(
      (pathName) =>
        pathName.startsWith("/api/projects/") &&
        pathName.includes("/branches"),
    ),
  ).toBeTruthy();
});

test("normalizes stale branch params before branch-scoped pages query data", async ({
  page,
}) => {
  await page.goto("/app/overview?project=1&lang=fr&branch=dev%2F9.9.9");

  await expect(page).toHaveURL(/branch=rel%2Fcurrent/);
  await expect(page.getByTestId("overview-page")).toBeVisible();
  await expect(page.getByText("Failed to load shell data")).toHaveCount(0);
});

test("keeps the intake preview open when the import job finishes as failed", async ({
  page,
}) => {
  await page.route("**/api/projects/1/imports/upload-folder/preview", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        upload_session_id: "fake-session",
        schema: {
          schema_id: 1,
          project_id: 1,
          fixed_columns: {
            business_key: "business_key",
            source: "source",
          },
          translation_columns: ["fr", "en"],
          remark_columns: ["context"],
          translation_pivots: {
            fr: null,
            en: null,
          },
          created_at: "2026-03-25T00:00:00Z",
        },
        file_count: 1,
        sheet_count: 1,
        sheet_previews: [
          {
            sheet_key: "sheet-1",
            file_path: "bundle/messages.xlsx",
            derived_file_name: "messages.xlsx",
            sheet_name: "Sheet1",
            available_headers: ["business_key", "source", "fr"],
            suggested_mapping: {
              business_key: "business_key",
              source: "source",
              translation_columns: { fr: "fr" },
              remark_columns: {},
            },
            missing_targets: [],
            auto_match_ready: true,
          },
        ],
      }),
    });
  });
  await page.route("**/api/projects/1/imports/upload-folder", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify(
        buildJobDetail({
          status: "running",
        }),
      ),
    });
  });
  await page.route("**/api/projects/1/jobs/999", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify(
        buildJobDetail({
          status: "failed",
          error_message: "Synthetic import failure",
          finished_at: "2026-03-25T00:00:01Z",
        }),
      ),
    });
  });

  await page.goto("/app/intake?project=1&lang=fr&branch=rel%2Fcurrent");
  await expect(page.getByTestId("intake-page")).toBeVisible();
  await page.getByTestId("intake-folder-input").setInputFiles(importDir);
  await expect(page.getByTestId("intake-import-dialog")).toBeVisible();
  await page.getByTestId("intake-confirm-import").click();

  await expect(page).toHaveURL(/\/app\/intake\?/);
  await expect(page.getByTestId("intake-import-dialog")).toBeVisible();
  await expect(page.getByText("Synthetic import failure")).toBeVisible();
});

test("resets compare and queue pagination when filters change", async ({
  page,
  request,
}) => {
  await seedDevBranch(request);

  const compareRequests = [];
  const queueRequests = [];

  await page.route("**/api/projects/1/branches/compare**", async (route) => {
    const url = new URL(route.request().url());
    compareRequests.push({
      page: url.searchParams.get("page"),
      search: url.searchParams.get("search"),
    });
    const label = url.searchParams.get("search") || `compare-page-${url.searchParams.get("page") || "1"}`;
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        base_branch_ref: "rel/current",
        target_branch_ref: "dev/2.4.3",
        status_counts: {},
        rows: [
          {
            business_key: label,
            state: "target_only",
            priority_status: "needs_translation",
            diff_categories: ["source_changed"],
            base: null,
            target: {
              source: "Target source",
              file_name: "messages.xlsx",
              translations: { fr: label },
              remarks: {},
            },
          },
        ],
        priority_rows: [],
        total_rows: 60,
        total_priority_rows: 0,
        page: Number(url.searchParams.get("page") || "1"),
        page_size: 25,
      }),
    });
  });
  await page.route("**/api/projects/1/branches/queue**", async (route) => {
    const url = new URL(route.request().url());
    queueRequests.push({
      page: url.searchParams.get("page"),
      status: url.searchParams.getAll("priority_status").join(","),
    });
    const label =
      url.searchParams.getAll("priority_status").join(",") ||
      `queue-page-${url.searchParams.get("page") || "1"}`;
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        target_branch_ref: "dev/2.4.3",
        lang: "fr",
        status_counts: {},
        rows: [
          {
            business_key: label,
            file_name: "messages.xlsx",
            source: "Queue source",
            target_text: label,
            state: "target_only",
            priority_status: "needs_translation",
            diff_categories: ["source_changed"],
          },
        ],
        total_rows: 60,
        page: Number(url.searchParams.get("page") || "1"),
        page_size: 25,
      }),
    });
  });

  await page.goto("/app/branches?project=1&lang=fr&branch=dev%2F2.4.3&tab=compare");
  await expect(page.getByText("compare-page-1")).toBeVisible();

  await page.getByRole("button", { name: "Next" }).click();
  await expect(page.getByText("compare-page-2")).toBeVisible();

  await page.getByLabel("Search").fill("alpha");
  await expect.poll(() => compareRequests.at(-1)?.page).toBe("1");
  await expect.poll(() => compareRequests.at(-1)?.search).toBe("alpha");
  await expect(page.getByText("alpha")).toBeVisible();

  await page.getByRole("button", { name: "Queue" }).click();
  await expect(page.getByText("queue-page-1")).toBeVisible();

  await page.getByRole("button", { name: "Next" }).click();
  await expect(page.getByText("queue-page-2")).toBeVisible();

  await page.getByLabel("Priority").selectOption("needs_translation");
  await expect.poll(() => queueRequests.at(-1)?.page).toBe("1");
  await expect.poll(() => queueRequests.at(-1)?.status).toBe("needs_translation");
  await expect(page.getByText("needs_translation")).toBeVisible();
});
