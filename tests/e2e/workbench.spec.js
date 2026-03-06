const { test, expect } = require("@playwright/test");

test.beforeEach(async ({ request }) => {
  const response = await request.post("/api/demo/reset");
  expect(response.ok()).toBeTruthy();
});

test("loads the workbench and shows seeded branch heads", async ({ page }) => {
  await page.goto("/workbench");

  await expect(page.getByTestId("sample-select")).toBeVisible();
  await expect(page.getByTestId("branch-dev")).toContainText("snapshot_id");
  await expect(page.getByTestId("branch-release")).toContainText("demo_seed");
  await expect(page.getByTestId("branch-master")).toContainText("demo_seed");
  await expect(page.getByTestId("jobs-list")).toContainText("No jobs yet.");
});

test("imports the sample and updates dev", async ({ page }) => {
  await page.goto("/workbench");

  await page.getByTestId("import-button").click();
  await expect(page.getByTestId("import-result")).toContainText("import_batch_id");

  await page.getByTestId("update-dev-button").click();
  await expect(page.getByTestId("jobs-list")).toContainText("update_dev");
  await expect(page.getByTestId("branch-dev")).toContainText("update_dev");
});

test("runs active and passive release hotfix", async ({ page }) => {
  await page.goto("/workbench");

  await page.getByTestId("active-hotfix-button").click();
  await expect(page.getByTestId("jobs-list")).toContainText("active_hotfix");
  await expect(page.getByTestId("branch-release")).toContainText("active_single");

  await page.getByTestId("passive-hotfix-button").click();
  await expect(page.getByTestId("jobs-list")).toContainText("passive_hotfix");
  await expect(page.getByTestId("branch-release")).toContainText("passive_single");
});

test("previews and executes promote after updating dev", async ({ page }) => {
  await page.goto("/workbench");

  await page.getByTestId("update-dev-button").click();
  await expect(page.getByTestId("jobs-list")).toContainText("update_dev");

  await page.getByTestId("promote-preview-button").click();
  await expect(page.getByTestId("promote-preview")).toContainText("added_count");
  await expect(page.getByTestId("promote-preview")).toContainText("conflict_src_changed_count");

  await page.getByTestId("promote-execute-button").click();
  await expect(page.getByTestId("jobs-list")).toContainText("promote_execute");
  await expect(page.getByTestId("branch-release")).toContainText("promote");
});

test("archives release into master and deletes keys", async ({ page }) => {
  await page.goto("/workbench");

  await page.getByTestId("archive-button").click();
  await expect(page.getByTestId("jobs-list")).toContainText("archive_release");
  await expect(page.getByTestId("branch-master")).toContainText("archive_release");

  await page.getByTestId("delete-button").click();
  await expect(page.getByTestId("jobs-list")).toContainText("delete_keys");
});

test("runs fill and qa and shows job details", async ({ page }) => {
  await page.goto("/workbench");

  await page.getByTestId("fill-button").click();
  await expect(page.getByTestId("verification-result")).toContainText("filled_count");
  await expect(page.getByTestId("job-detail")).toContainText("Download artifact");

  await page.getByTestId("qa-button").click();
  await expect(page.getByTestId("verification-result")).toContainText("issue_count");
  await expect(page.getByTestId("jobs-list")).toContainText("qa_report");
});
