const { test, expect } = require("@playwright/test");

test.beforeEach(async ({ request }) => {
  const response = await request.post("/api/demo/reset");
  expect(response.ok()).toBeTruthy();
});

test("loads the new workbench state", async ({ page }) => {
  await page.goto("/workbench");

  await expect(page.getByTestId("sample-select")).toBeVisible();
  await expect(page.getByTestId("project-summary")).toContainText("Demo Project");
  await expect(page.getByTestId("string-list")).toContainText("common.welcome");
  await expect(page.getByTestId("jobs-list")).toContainText("No jobs yet.");
});

test("imports sample excel, runs dev import, previews and executes promote", async ({ page }) => {
  await page.goto("/workbench");

  await page.getByTestId("import-sample-button").click();
  await expect(page.getByTestId("import-result")).toContainText("import_batch_id");

  await page.getByTestId("dev-import-button").click();
  await expect(page.getByTestId("jobs-list")).toContainText("dev_import");
  await expect(page.getByTestId("dev-versions-list")).toContainText("2.2.3");

  await page.getByTestId("promote-preview-button").click();
  await expect(page.getByTestId("promote-preview")).toContainText("target_key_count");
  await expect(page.getByTestId("promote-preview")).toContainText("cleanup_dev_membership_count");

  await page.getByTestId("promote-execute-button").click();
  await expect(page.getByTestId("jobs-list")).toContainText("promote_execute");
});

test("runs hotfix, trash, fill and qa", async ({ page, request }) => {
  await page.goto("/workbench");

  await page.getByTestId("active-target").fill("  Bienvenue UI  ");
  await page.getByTestId("active-hotfix-button").click();
  await expect(page.getByTestId("jobs-list")).toContainText("rel_hotfix_active");
  const activeHotfixResponse = await request.get("/api/strings/common.welcome");
  expect(activeHotfixResponse.ok()).toBeTruthy();
  const activeHotfixPayload = await activeHotfixResponse.json();
  expect(activeHotfixPayload.translations.fr).toBe("  Bienvenue UI  ");

  await page.getByTestId("passive-hotfix-button").click();
  await expect(page.getByTestId("jobs-list")).toContainText("rel_hotfix_passive");

  await page.getByTestId("trash-delete-button").click();
  await expect(page.getByTestId("jobs-list")).toContainText("trash_delete");

  await page.getByTestId("trash-restore-button").click();
  await expect(page.getByTestId("jobs-list")).toContainText("trash_restore");

  await page.getByTestId("fill-button").click();
  await expect(page.getByTestId("verification-result")).toContainText("filled_count");

  await page.getByTestId("qa-button").click();
  await expect(page.getByTestId("verification-result")).toContainText("issue_count");
});
