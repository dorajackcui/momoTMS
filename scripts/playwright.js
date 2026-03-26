const fs = require("fs");
const path = require("path");
const { spawnSync } = require("child_process");

const repoRoot = path.resolve(__dirname, "..");
const playwrightBrowsersPath =
  process.env.PLAYWRIGHT_BROWSERS_PATH || path.join(repoRoot, ".playwright");
const buildIndexPath = path.join(
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
const playwrightTestCli = path.join(
  repoRoot,
  "node_modules",
  "@playwright",
  "test",
  "cli.js",
);
const playwrightCli = path.join(repoRoot, "node_modules", "playwright", "cli.js");
const browsersManifestPath = path.join(
  repoRoot,
  "node_modules",
  "playwright-core",
  "browsers.json",
);

function fail(message) {
  console.error(message);
  process.exit(1);
}

function ensureNodeDependencies() {
  if (!fs.existsSync(playwrightTestCli) || !fs.existsSync(playwrightCli)) {
    fail("Playwright dependencies are missing. Run `npm install` first.");
  }
}

function ensureLocalPython() {
  if (!fs.existsSync(venvPython)) {
    fail(
      "Local Python runtime is missing. Create the project virtualenv before running E2E.\n" +
        "Expected: .venv/Scripts/python.exe or .venv/bin/python",
    );
  }
}

function ensureProductBuild() {
  if (!fs.existsSync(buildIndexPath)) {
    fail(
      "Product app build is missing. Run `npm run build:app` before `npm run test:e2e`.",
    );
  }
}

function loadBrowserManifest() {
  return JSON.parse(fs.readFileSync(browsersManifestPath, "utf8"));
}

function browserInstallDir(rootDir, browserName) {
  const manifest = loadBrowserManifest();
  const browser = manifest.browsers.find((item) => item.name === browserName);
  if (!browser) {
    return null;
  }
  const dirName =
    browser.name === "chromium-headless-shell"
      ? `chromium_headless_shell-${browser.revision}`
      : `${browser.name}-${browser.revision}`;
  return path.join(rootDir, dirName);
}

function defaultSharedBrowserCache() {
  if (process.platform === "win32") {
    return path.join(
      process.env.LOCALAPPDATA || path.join(process.env.USERPROFILE || "", "AppData", "Local"),
      "ms-playwright",
    );
  }
  if (process.platform === "darwin") {
    return path.join(process.env.HOME || "", "Library", "Caches", "ms-playwright");
  }
  return path.join(process.env.HOME || "", ".cache", "ms-playwright");
}

function hasRequiredChromiumBrowsers(rootDir) {
  const chromiumDir = browserInstallDir(rootDir, "chromium");
  const shellDir = browserInstallDir(rootDir, "chromium-headless-shell");
  return Boolean(
    chromiumDir &&
      shellDir &&
      fs.existsSync(chromiumDir) &&
      fs.existsSync(shellDir),
  );
}

function hydrateRepoBrowserCacheFromSharedInstall() {
  const sharedCache = defaultSharedBrowserCache();
  if (!fs.existsSync(sharedCache)) {
    return false;
  }
  fs.mkdirSync(playwrightBrowsersPath, { recursive: true });
  const browserNames = [
    "chromium",
    "chromium-headless-shell",
    "ffmpeg",
    "winldd",
  ];
  let copiedAny = false;
  for (const browserName of browserNames) {
    const sourceDir = browserInstallDir(sharedCache, browserName);
    const targetDir = browserInstallDir(playwrightBrowsersPath, browserName);
    if (!sourceDir || !targetDir || !fs.existsSync(sourceDir) || fs.existsSync(targetDir)) {
      continue;
    }
    fs.cpSync(sourceDir, targetDir, { recursive: true });
    copiedAny = true;
  }
  return copiedAny;
}

function ensureChromiumBrowsersInstalled() {
  if (hasRequiredChromiumBrowsers(playwrightBrowsersPath)) {
    return;
  }
  hydrateRepoBrowserCacheFromSharedInstall();
  if (hasRequiredChromiumBrowsers(playwrightBrowsersPath)) {
    return;
  }
  fail(
    "Playwright Chromium browsers are not installed in the repo-local cache.\n" +
      "Run `npm run test:e2e:install` first.",
  );
}

function runPlaywrightCli(cliPath, args) {
  const result = spawnSync(process.execPath, [cliPath, ...args], {
    cwd: repoRoot,
    env: {
      ...process.env,
      PLAYWRIGHT_BROWSERS_PATH: playwrightBrowsersPath,
    },
    stdio: "inherit",
  });
  if (result.error) {
    throw result.error;
  }
  process.exit(result.status ?? 1);
}

function main() {
  const [command, ...args] = process.argv.slice(2);
  ensureNodeDependencies();

  if (command === "install") {
    if (args.includes("--help") || args.includes("-h")) {
      runPlaywrightCli(playwrightCli, ["install", ...args]);
      return;
    }
    hydrateRepoBrowserCacheFromSharedInstall();
    if (hasRequiredChromiumBrowsers(playwrightBrowsersPath)) {
      console.log(`Playwright Chromium browsers are ready in ${playwrightBrowsersPath}.`);
      process.exit(0);
    }
    runPlaywrightCli(playwrightCli, ["install", "chromium", ...args]);
    return;
  }

  if (command === "test") {
    ensureChromiumBrowsersInstalled();
    if (!process.env.PLAYWRIGHT_BASE_URL) {
      ensureLocalPython();
      ensureProductBuild();
    }
    runPlaywrightCli(playwrightTestCli, ["test", ...args]);
    return;
  }

  fail("Unknown Playwright command. Use `test` or `install`.");
}

main();
