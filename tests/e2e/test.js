const { test: base, expect } = require("@playwright/test");

const { getManagedBaseUrl } = require("./support/server");

const test = base.extend({
  baseURL: async ({}, use) => {
    await use(getManagedBaseUrl());
  },
});

module.exports = { test, expect };
