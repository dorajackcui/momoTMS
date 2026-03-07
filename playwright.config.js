/** @type {import('@playwright/test').PlaywrightTestConfig} */
module.exports = {
  testDir: "./tests/e2e",
  workers: 1,
  timeout: 60_000,
  expect: {
    timeout: 10_000,
  },
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:8000",
    trace: "on-first-retry",
  },
  reporter: [["list"]],
};
