const {
  cleanupRecordedServer,
  writeServerState,
  startManagedServer,
} = require("./support/server");
const path = require("path");

module.exports = async function globalSetup() {
  await cleanupRecordedServer();

  if (process.env.PLAYWRIGHT_BASE_URL) {
    writeServerState({
      attached: true,
      baseUrl: process.env.PLAYWRIGHT_BASE_URL,
    });
    return;
  }

  const state = await startManagedServer({
    logPath: path.join(process.cwd(), "test-results", "playwright-server.log"),
  });
  process.env.PLAYWRIGHT_BASE_URL = state.baseUrl;
  writeServerState(state);
};
