const path = require("path");
const { test, expect } = require("@playwright/test");

test.beforeEach(async ({ request }) => {
  const response = await request.post("/api/demo/reset");
  expect(response.ok()).toBeTruthy();
});

test("uploads real folders and validates the variant workbench flow", async ({ page }) => {
  const importDir = path.join(process.cwd(), "data", "demo_samples", "core-cycle", "import_bundle");
  const fillDir = path.join(process.cwd(), "data", "demo_samples", "core-cycle", "fill_source");

  await page.goto("/variant-workbench");

  await expect(page.getByTestId("project-summary")).toContainText("Demo Project");
  await expect(page.getByTestId("variant-workbench-status")).toContainText("Deprecated internal validation page");
  await page.getByTestId("import-folder").setInputFiles(importDir);
  await page.getByTestId("upload-import-button").click();
  await expect(page.getByTestId("import-mapping-modal")).toBeVisible();
  await page.getByTestId("confirm-import-mapping").click();
  await expect(page.getByTestId("import-result")).toContainText("import_batch_id");

  await page.getByTestId("dev-version").fill("2.2.3");
  await page.getByTestId("dev-import-button").click();
  await expect(page.getByTestId("jobs-list")).toContainText("dev_import");

  await page.getByTestId("compare-button").click();
  await expect(page.getByTestId("branch-compare")).toContainText("rel.locked.changed");
  await expect(page.getByTestId("translation-queue")).toContainText("dev.new.entry");

  await page.getByTestId("master-key").fill("rel.locked.same");
  await page.getByTestId("master-key-button").click();
  await expect(page.getByTestId("master-result")).toContainText("rel.locked.same");
  await expect(page.getByTestId("master-result")).toContainText("rel/current");

  await page.getByTestId("promote-version").fill("2.2.3");
  await page.getByTestId("promote-preview-button").click();
  await expect(page.getByTestId("promote-preview")).toContainText("target_key_count");
  await page.getByTestId("promote-execute-button").click();
  await expect(page.getByTestId("jobs-list")).toContainText("promote_execute");

  await page.getByTestId("fill-folder").setInputFiles(fillDir);
  await page.getByTestId("fill-button").click();
  await expect(page.getByTestId("verification-result")).toContainText("filled_count");

  await page.getByTestId("qa-folder").setInputFiles(fillDir);
  await page.getByTestId("qa-button").click();
  await expect(page.getByTestId("verification-result")).toContainText("issue_count");
});
