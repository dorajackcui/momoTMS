/** @type {import('@playwright/test').PlaywrightTestConfig} */
module.exports = {
  testDir: "./tests/e2e",
  globalSetup: "./tests/e2e/global-setup.js",
  globalTeardown: "./tests/e2e/global-teardown.js",
  workers: 1,
  timeout: 60_000,
  expect: {
    timeout: 10_000,
  },
  use: {
    trace: "on-first-retry",
  },
  reporter: [["list"]],
};
