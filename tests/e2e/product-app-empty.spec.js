const { test, expect } = require("./test");

const { startManagedServer, stopManagedServer } = require("./support/server");

test("redirects empty runtime to /app/project and can create the first project", async ({ page }) => {
  const server = await startManagedServer({ runtimePrefix: "momo-p2-empty-" });

  try {
    await page.goto(`${server.baseUrl}/app`);
    await expect(page).toHaveURL(/\/app\/project(\?.*)?$/);
    await expect(page.getByTestId("project-page")).toBeVisible();

    await page.getByLabel("Project name").fill("First Project");
    await page.getByLabel("Translation columns").fill("fr, en");
    await page.getByLabel("Remark columns").fill("context");
    await page.getByTestId("project-create-button").click();

    await expect(page).toHaveURL(/\/app\/overview\?/);
    await expect(page.getByTestId("overview-page")).toBeVisible();
    await expect(page.getByTestId("shell-project-select")).toHaveValue("1");
  } finally {
    await stopManagedServer(server);
  }
});
