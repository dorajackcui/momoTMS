const path = require("path");
const { test, expect } = require("@playwright/test");

test.beforeEach(async ({ request }) => {
  const response = await request.post("/api/demo/reset");
  expect(response.ok()).toBeTruthy();
});

test("loads the product app and runs the core operator flow", async ({ page }) => {
  const importDir = path.join(process.cwd(), "data", "demo_samples", "core-cycle", "import_bundle");
  const fillDir = path.join(process.cwd(), "data", "demo_samples", "core-cycle", "fill_source");

  await page.goto("/app/projects/new");
  await expect(page.getByTestId("project-create-page")).toBeVisible();
  await page.getByTestId("project-name-input").fill("Fresh Project");
  await page.getByTestId("project-translation-columns").fill("fr, en");
  await page.getByTestId("project-remark-columns").fill("context");
  await page.getByTestId("project-create-button").click();

  await expect(page).toHaveURL(/\/app\/imports$/);
  await expect(page.getByTestId("product-app")).toContainText("Product App");
  await expect(page.getByTestId("app-project-select")).toHaveValue("2");
  await page.getByTestId("app-import-folder").setInputFiles(importDir);
  await expect(page.getByTestId("app-import-modal")).toBeVisible();
  await page.getByTestId("app-confirm-import").click();

  await page.getByTestId("app-dev-version-input").fill("2.2.3");
  await page.getByTestId("app-run-dev-import").click();
  await expect(page.getByTestId("app-jobs-list")).toContainText("dev_import");

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
  await page.getByTestId("app-promote-execute").click();
  await expect(page.getByTestId("app-jobs-list")).toContainText("promote_execute");

  await page.getByTestId("app-fill-folder").setInputFiles(fillDir);
  await expect(page.getByTestId("app-job-detail")).toContainText("filled_count");

  await page.getByTestId("app-qa-folder").setInputFiles(fillDir);
  await expect(page.getByTestId("app-job-detail")).toContainText("issue_count");
});
