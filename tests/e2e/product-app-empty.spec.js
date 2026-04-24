const { test, expect } = require("./test");

const { startManagedServer, stopManagedServer } = require("./support/server");

// TODO: redesign — the /app/project route no longer exists; project creation is now
// done via HubPage at /app (the root app route). The project-page and project-create-button
// test IDs are gone; HubPage uses a "+ Create Project" button (no testid).
// The overview-page and shell-project-select test IDs are also removed.
// This test needs to be redesigned against the new HubPage create-project flow.
test.skip("redirects empty runtime to /app/project and can create the first project", async ({ page }) => {
  const server = await startManagedServer({ runtimePrefix: "momo-p2-empty-" });

  try {
    // Previously: redirected to /app/project; now an empty runtime stays at /app (HubPage).
    await page.goto(`${server.baseUrl}/app`);
    await expect(page).toHaveURL(/\/app(\?.*)?$/);

    // Previously used project-page, project-create-button, overview-page,
    // and shell-project-select test IDs which no longer exist.
  } finally {
    await stopManagedServer(server);
  }
});
