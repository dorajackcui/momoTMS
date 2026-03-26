const {
  clearServerState,
  readServerState,
  stopManagedServer,
} = require("./support/server");

module.exports = async function globalTeardown() {
  const state = readServerState();
  await stopManagedServer(state);
  clearServerState();
};
