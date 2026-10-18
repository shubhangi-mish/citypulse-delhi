import { defineConfig } from "@playwright/test";

// Point E2E_BASE_URL at an ISOLATED stack (separate FalkorDB graph) — never the production graph.
export default defineConfig({
  testDir: "./e2e",
  timeout: 120_000,
  expect: { timeout: 20_000 },
  use: { baseURL: process.env.E2E_BASE_URL || "http://localhost:3200", viewport: { width: 1360, height: 900 }, trace: "retain-on-failure" },
  reporter: [["list"]],
});
