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

async function createProject(page, name) {
  await page.goto("/app/project");
  await expect(page.getByTestId("project-page")).toBeVisible();
  await expect(page.getByTestId("project-page")).not.toContainText("candidate");
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

test("keeps first-project import apply target local until a dev branch is entered", async ({
  page,
}) => {
  await page.goto("/app");
  await expect(page).toHaveURL(/\/app\/overview\?/);
  await expectBranchParam(page, null);

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
  request,
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
  await expect(page.getByTestId("overview-page")).not.toContainText("candidate");
  await expectBranchParam(page, null);

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
  const startedJobId = Number(new URL(page.url()).searchParams.get("job"));
  await waitForJob(
    request,
    {
      job: {
        job_id: startedJobId,
        status: "running",
      },
    },
    1,
  );

  await page.goto("/app/overview?project=1&lang=fr&branch=dev%2F2.4.3");
  await expect(page.getByTestId("overview-page")).toContainText("dev.mutable");
  await page.getByRole("button", { name: "dev.mutable" }).click();
  await expect(page.getByText("Variant history", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "dev.mutable" })).toBeVisible();
  await page.getByRole("button", { name: "Close" }).click();

  await page.goto("/app/branches?project=1&lang=fr&branch=dev%2F2.4.3&tab=scope");
  await expect(page.getByTestId("branches-page")).toBeVisible();
  await expect(page.getByRole("button", { name: "Scope" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Lookup" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Apply" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Replace" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Trash / Restore" })).toBeVisible();

  await page.getByRole("button", { name: "Lookup" }).click();
  await page.getByRole("combobox", { name: "Scope" }).selectOption("rel/current");
  await page.getByRole("textbox", { name: "Business key Lookup key" }).fill(
    "rel.locked.same",
  );
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
  await expect(page.getByText("preview_kind")).toBeVisible();
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

test("overview branch filter clears canonical branch state for project-wide mode", async ({
  page,
  request,
}) => {
  await seedDevBranch(request);

  await page.goto("/app/overview?project=1&lang=fr");
  await expect(page.getByTestId("overview-page")).toBeVisible();
  await expect(page.getByText("Project-wide variant workspace")).toBeVisible();
  await expect(page.getByTestId("overview-branch-select")).toHaveValue("__all__");
  await expectBranchParam(page, null);

  await page.getByTestId("overview-branch-select").selectOption("dev/2.4.3");
  await expectBranchParam(page, "dev/2.4.3");
  await expect(page.getByTestId("overview-branch-select")).toHaveValue("dev/2.4.3");

  await page.getByTestId("overview-branch-select").selectOption("__all__");
  await expectBranchParam(page, null);
  await expect(page.getByTestId("overview-branch-select")).toHaveValue("__all__");

  await page.reload();
  await expect(page.getByTestId("overview-page")).toBeVisible();
  await expect(page.getByText("Project-wide variant workspace")).toBeVisible();
  await expect(page.getByTestId("overview-branch-select")).toHaveValue("__all__");
  await expectBranchParam(page, null);
});

test("reviews changed pivot variants from the variants workspace", async ({
  page,
  request,
}) => {
  const project = await createPivotProject(request, "Pivot E2E Project");
  const projectId = Number(project.project_id);

  await applyDirectMutation(request, {
    projectId,
    businessKey: "pivot.e2e",
    source: "Hello",
    fileName: "pivot.xlsx",
    translationsByLang: {
      en: "Hello",
      fr: "Bonjour",
    },
    remarksByKey: {
      context: "pivot e2e",
    },
  });
  await applyDirectMutation(request, {
    projectId,
    businessKey: "pivot.e2e",
    translationsByLang: {
      en: "Hello from dev",
    },
  });

  await page.goto(`/app/variants?project=${projectId}&lang=fr&branch=dev%2F2.4.3`);
  await expect(page.getByTestId("variants-page")).toBeVisible();

  const resultCard = page
    .getByTestId("variants-results-list")
    .locator("article")
    .filter({ hasText: "pivot.e2e" });
  await expect(resultCard).toContainText("changed");
  await expect(resultCard).toContainText("dev/2.4.3");

  await page.getByLabel("Select pivot.e2e").check();
  await page.getByTestId("variants-review-button").click();

  await expect(page).toHaveURL(/\/app\/runs\?.*job=/);
  await expect(page.getByTestId("runs-page")).toBeVisible();

  await page.goto(`/app/variants?project=${projectId}&lang=fr&branch=dev%2F2.4.3`);
  await expect(page.getByTestId("variants-page")).toBeVisible();
  const reviewedCard = page
    .getByTestId("variants-results-list")
    .locator("article")
    .filter({ hasText: "pivot.e2e" });
  await expect(reviewedCard).toContainText("reviewed");
  await expect(reviewedCard).toContainText("changed by -");
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
          pivot_language: null,
          pivoted_languages: [],
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

