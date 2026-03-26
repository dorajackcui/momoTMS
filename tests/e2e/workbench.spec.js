const { test, expect } = require("./test");

test("workbench endpoint is gone in p1", async ({ request }) => {
  const response = await request.get("/workbench");
  expect(response.status()).toBe(410);
  const payload = await response.json();
  expect(payload.detail).toContain("workbench removed");
});
