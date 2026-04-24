const { test, expect } = require("./test");

const { startManagedServer, stopManagedServer } = require("./support/server");

test("creates the first project from the Hub in an empty runtime", async ({ page }) => {
  const server = await startManagedServer({ runtimePrefix: "momo-p2-empty-" });

  try {
    await page.goto(`${server.baseUrl}/app`);
    await expect(page).toHaveURL(/\/app(\?.*)?$/);
    await expect(page.getByText("No projects")).toBeVisible();

    await page.getByRole("button", { name: /Create Project/ }).click();
    await page.getByLabel("Project name").fill("Empty Runtime Project");
    await page.getByLabel(/Translation columns/).fill("fr, en");
    await page.getByLabel(/Remark columns/).fill("context");
    await page.getByRole("button", { name: /^Create$/ }).click();

    await expect(page).toHaveURL(/\/app\/workspace\?.*project=/);
    await expect(page.getByText("Empty Runtime Project")).toBeVisible();
  } finally {
    await stopManagedServer(server);
  }
});
