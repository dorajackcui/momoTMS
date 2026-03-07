const fs = require("fs");
const net = require("net");
const os = require("os");
const path = require("path");
const { spawn } = require("child_process");
const { test, expect } = require("@playwright/test");

async function getFreePort() {
  return await new Promise((resolve, reject) => {
    const server = net.createServer();
    server.on("error", reject);
    server.listen(0, "127.0.0.1", () => {
      const address = server.address();
      if (!address || typeof address === "string") {
        server.close(() => reject(new Error("failed to allocate port")));
        return;
      }
      const { port } = address;
      server.close((error) => {
        if (error) {
          reject(error);
          return;
        }
        resolve(port);
      });
    });
  });
}

async function waitForServer(request, baseUrl) {
  for (let attempt = 0; attempt < 40; attempt += 1) {
    try {
      const response = await request.get(`${baseUrl}/api/projects`);
      if (response.ok()) {
        return;
      }
    } catch {
      // server not ready yet
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  throw new Error(`server did not become ready: ${baseUrl}`);
}

async function stopServer(server) {
  if (server.exitCode !== null) {
    return;
  }
  server.kill("SIGKILL");
  if (server.exitCode === null) {
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
}

test("shows no-project empty state and can create the first project", async ({ page, request }) => {
  const runtimeRoot = fs.mkdtempSync(path.join(os.tmpdir(), "momo-p2-empty-"));
  const port = await getFreePort();
  const baseUrl = `http://127.0.0.1:${port}`;
  const server = spawn(
    path.join(process.cwd(), ".venv", "bin", "python"),
    ["-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", String(port)],
    {
      cwd: process.cwd(),
      env: {
        ...process.env,
        MOMO_TMS_DB_PATH: path.join(runtimeRoot, "data", "tms.db"),
        MOMO_TMS_JOBS_DIR: path.join(runtimeRoot, "jobs"),
        MOMO_TMS_DEMO_ROOT: path.join(runtimeRoot, "demo_samples"),
      },
      stdio: "pipe",
    },
  );

  try {
    await waitForServer(request, baseUrl);
    await page.goto(`${baseUrl}/app`);
    await expect(page.getByTestId("app-empty-state")).toBeVisible();
    await expect(page.getByTestId("app-empty-state")).toContainText("No projects are available yet");

    await page.getByTestId("app-empty-create-project").click();
    await expect(page).toHaveURL(`${baseUrl}/app/projects/new`);
    await page.getByTestId("project-name-input").fill("First Project");
    await page.getByTestId("project-translation-columns").fill("fr, en");
    await page.getByTestId("project-remark-columns").fill("context");
    await page.getByTestId("project-create-button").click();

    await expect(page).toHaveURL(`${baseUrl}/app/imports`);
    await expect(page.getByTestId("imports-page")).toContainText("No import batches yet");
    await expect(page.getByTestId("app-jobs-list")).toContainText("No jobs yet");
  } finally {
    await stopServer(server);
  }
});
