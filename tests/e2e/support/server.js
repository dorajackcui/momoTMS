const fs = require("fs");
const http = require("http");
const net = require("net");
const os = require("os");
const path = require("path");
const { spawn, spawnSync } = require("child_process");

const repoRoot = path.resolve(__dirname, "..", "..", "..");
const resultsDir = path.join(repoRoot, "test-results");
const stateFilePath = path.join(resultsDir, "playwright-server.json");
const productBuildPath = path.join(
  repoRoot,
  "app",
  "static",
  "product-app",
  "index.html",
);
const venvPython = path.join(
  repoRoot,
  ".venv",
  process.platform === "win32" ? "Scripts" : "bin",
  process.platform === "win32" ? "python.exe" : "python",
);

function getManagedBaseUrl() {
  return process.env.PLAYWRIGHT_BASE_URL || readServerState()?.baseUrl || "http://127.0.0.1:8000";
}

function ensureLocalServerPrereqs() {
  if (!fs.existsSync(productBuildPath)) {
    throw new Error(
      "Product app build is missing. Run `npm run build:app` before `npm run test:e2e`.",
    );
  }
  if (!fs.existsSync(venvPython)) {
    throw new Error(
      "Local Python runtime is missing. Create `.venv` before running Playwright.",
    );
  }
}

function writeServerState(state) {
  fs.mkdirSync(resultsDir, { recursive: true });
  fs.writeFileSync(stateFilePath, JSON.stringify(state, null, 2));
}

function readServerState() {
  if (!fs.existsSync(stateFilePath)) {
    return null;
  }
  return JSON.parse(fs.readFileSync(stateFilePath, "utf8"));
}

function clearServerState() {
  if (fs.existsSync(stateFilePath)) {
    fs.rmSync(stateFilePath, { force: true });
  }
}

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
      server.close((error) => {
        if (error) {
          reject(error);
          return;
        }
        resolve(address.port);
      });
    });
  });
}

async function waitForServer(baseUrl) {
  for (let attempt = 0; attempt < 60; attempt += 1) {
    try {
      const statusCode = await new Promise((resolve, reject) => {
        const request = http.get(new URL("/api/projects", baseUrl), (response) => {
          response.resume();
          resolve(response.statusCode || 0);
        });
        request.on("error", reject);
      });
      if (statusCode >= 200 && statusCode < 300) {
        return;
      }
    } catch {
      // server is still booting
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  throw new Error(`server did not become ready: ${baseUrl}`);
}

function formatLogs(logs) {
  if (logs.length === 0) {
    return "";
  }
  return `\nServer output:\n${logs.join("")}`;
}

function processExists(pid) {
  if (!pid) {
    return false;
  }
  try {
    process.kill(pid, 0);
    return true;
  } catch (error) {
    return false;
  }
}

async function waitForProcessExit(pid, timeoutMs = 5_000) {
  const deadline = Date.now() + timeoutMs;
  while (processExists(pid)) {
    if (Date.now() >= deadline) {
      break;
    }
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
}

async function stopManagedServer(state) {
  if (!state) {
    return;
  }
  if (!state.attached && state.pid && processExists(state.pid)) {
    if (process.platform === "win32") {
      spawnSync("taskkill", ["/PID", String(state.pid), "/T", "/F"], {
        stdio: "ignore",
      });
    } else {
      try {
        process.kill(state.pid, "SIGTERM");
      } catch {
        // process already exited
      }
    }
    await waitForProcessExit(state.pid);
  }
  if (state.runtimeRoot) {
    fs.rmSync(state.runtimeRoot, { recursive: true, force: true });
  }
}

async function cleanupRecordedServer() {
  const state = readServerState();
  if (!state) {
    return;
  }
  await stopManagedServer(state);
  clearServerState();
}

async function startManagedServer(options = {}) {
  ensureLocalServerPrereqs();
  const runtimeRoot =
    options.runtimeRoot ||
    fs.mkdtempSync(path.join(os.tmpdir(), options.runtimePrefix || "momo-playwright-"));
  const port = options.port || (await getFreePort());
  const baseUrl = options.baseUrl || `http://127.0.0.1:${port}`;
  const logPath =
    options.logPath ||
    path.join(runtimeRoot, options.logFileName || "playwright-server.log");
  const logs = [];
  const child = spawn(
    venvPython,
    ["-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", String(port)],
    {
      cwd: repoRoot,
      env: {
        ...process.env,
        MOMO_TMS_DB_PATH: path.join(runtimeRoot, "data", "tms.db"),
        MOMO_TMS_JOBS_DIR: path.join(runtimeRoot, "jobs"),
        MOMO_TMS_DEMO_ROOT: path.join(runtimeRoot, "demo_samples"),
      },
      stdio: ["ignore", "pipe", "pipe"],
    },
  );

  const appendLog = (chunk) => {
    const text = chunk.toString();
    logs.push(text);
    fs.mkdirSync(path.dirname(logPath), { recursive: true });
    fs.appendFileSync(logPath, text);
  };
  child.stdout.on("data", appendLog);
  child.stderr.on("data", appendLog);

  const exitPromise = new Promise((_, reject) => {
    child.once("exit", (code, signal) => {
      reject(
        new Error(
          `managed server exited before becoming ready (code=${code}, signal=${signal})${formatLogs(logs)}`,
        ),
      );
    });
  });

  try {
    await Promise.race([waitForServer(baseUrl), exitPromise]);
  } catch (error) {
    await stopManagedServer({ pid: child.pid, runtimeRoot, attached: false });
    throw error;
  }

  return {
    attached: false,
    baseUrl,
    logPath,
    pid: child.pid,
    runtimeRoot,
  };
}

module.exports = {
  cleanupRecordedServer,
  clearServerState,
  getManagedBaseUrl,
  readServerState,
  startManagedServer,
  stopManagedServer,
  writeServerState,
};
