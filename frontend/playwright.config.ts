import { defineConfig, devices } from "@playwright/test";

import { browserEnvironment } from "./e2e/environment";

export default defineConfig({
  testDir: "./e2e",
  outputDir: "./test-results",
  fullyParallel: false,
  workers: 1,
  timeout: 30_000,
  expect: { timeout: 5_000 },
  forbidOnly: true,
  retries: 0,
  reporter: "list",
  use: {
    baseURL: browserEnvironment.frontendUrl,
    headless: true,
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
    video: "off",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
