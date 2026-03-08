const path = require("path");
const { test, expect } = require("@playwright/test");

test.beforeEach(async ({ request }) => {
  const response = await request.post("/api/demo/reset");
  expect(response.ok()).toBeTruthy();
});

test("loads the product app, resets project-scoped UI on switch, and exercises jobs plus inspection", async ({ page }) => {
  const importDir = path.join(process.cwd(), "data", "demo_samples", "core-cycle", "import_bundle");
  const fillDir = path.join(process.cwd(), "data", "demo_samples", "core-cycle", "fill_source");
  const seenApiPaths = new Set();

  page.on("request", (request) => {
    const parsed = new URL(request.url());
    if (parsed.pathname.startsWith("/api/")) {
      seenApiPaths.add(parsed.pathname);
    }
  });

  await page.goto("/app/overview");
  await expect(page.getByTestId("product-app")).toContainText("Operator Console");

  await page.getByTestId("nav-project-new").click();
  await expect(page.getByTestId("project-create-page")).toBeVisible();
  await page.getByTestId("project-name-input").fill("Fresh Project");
  await page.getByTestId("project-translation-columns").fill("fr, en");
  await page.getByTestId("project-remark-columns").fill("context");
  await page.getByTestId("project-create-button").click();

  await expect(page).toHaveURL(/\/app\/imports$/);
  await expect(page.getByTestId("app-project-select")).toHaveValue("2");
  await expect(page.getByTestId("imports-page")).toContainText("No import batches yet");
  await expect(page.getByTestId("app-jobs-list")).toContainText("No jobs yet");

  await page.getByTestId("app-project-select").selectOption("1");
  await expect(page).toHaveURL(/\/app\/overview$/);
  await expect(page.getByTestId("overview-page")).toBeVisible();

  await page.getByTestId("app-project-select").selectOption("2");
  await expect(page).toHaveURL(/\/app\/overview$/);
  await page.getByTestId("nav-imports").click();
  await expect(page.getByTestId("imports-page")).toContainText("No import batches yet");

  await page.getByTestId("app-import-folder").setInputFiles(importDir);
  await expect(page.getByTestId("app-import-modal")).toBeVisible();
  await page.getByTestId("app-confirm-import").click();
  await expect(page.getByTestId("app-import-batches")).toContainText("batch #");
  await expect(page.getByTestId("app-job-detail")).toContainText("persist_import");
  await expect(page.getByTestId("app-job-report-link")).toBeVisible();

  await page.getByTestId("app-dev-version-input").fill("2.2.3");
  await page.getByTestId("app-run-dev-import").click();
  await expect(page.getByTestId("app-jobs-list")).toContainText("dev_import");
  await expect(page.getByTestId("app-job-detail")).toContainText("bind_dev_scope");

  await page.goto("/app/compare");
  await page.getByTestId("app-base-scope").selectOption("rel/current");
  await page.getByTestId("app-target-scope").selectOption("dev/2.2.3");
  await expect(page.getByTestId("compare-table")).toContainText("rel.locked.changed");

  await page.goto("/app/queue");
  await page.getByTestId("app-queue-target").selectOption("dev/2.2.3");
  await expect(page.getByTestId("queue-table")).toContainText("dev.new.entry");

  await page.goto("/app/master");
  await page.getByTestId("app-master-key").fill("rel.locked.same");
  await page.getByTestId("master-key-button").click();
  await expect(page.getByTestId("master-table")).toContainText("rel.locked.same");

  await page.goto("/app/imports");
  await page.getByTestId("app-promote-preview").click();
  await expect(page.getByText("promote preview")).toBeVisible();
  await page.getByTestId("app-promote-execute").click();
  await expect(page.getByTestId("app-job-detail")).toContainText("promote_rebind");

  await page.getByTestId("app-fill-folder").setInputFiles(fillDir);
  await expect(page.getByTestId("app-job-detail")).toContainText("fill_export");
  await expect(page.getByTestId("app-job-artifact-link")).toBeVisible();

  await page.getByTestId("app-qa-folder").setInputFiles(fillDir);
  await expect(page.getByTestId("app-job-detail")).toContainText("qa_scan");

  await page.getByTestId("nav-inspection").click();
  await expect(page).toHaveURL(/\/app\/inspection$/);
  await expect(page.getByTestId("app-orphan-list")).toBeVisible();
  await page.getByTestId("app-inspection-key").fill("rel.locked.same");
  await page.getByTestId("app-inspection-lookup").click();
  await expect(page.getByTestId("app-inspection-detail")).toContainText("variant #");
  await expect(page.getByTestId("app-inspection-detail")).toContainText("rel/current");
  await expect(page.getByTestId("app-inspection-detail")).toContainText("bindings");

  expect(
    [...seenApiPaths].some((pathName) => pathName === "/api/state" || pathName.startsWith("/api/strings")),
  ).toBeFalsy();
});
