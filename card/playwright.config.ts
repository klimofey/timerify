import { defineConfig } from "@playwright/test";
import { BASE_URL } from "./e2e/constants";

export default defineConfig({
  testDir: "./e2e",
  globalSetup: "./e2e/global-setup.ts",
  globalTeardown: "./e2e/global-teardown.ts",
  // One Home Assistant, and tests that change its states: they run one after the other.
  workers: 1,
  fullyParallel: false,
  // A test that needs longer, a restart of Home Assistant, raises its own timeout.
  timeout: 60_000,
  expect: { timeout: 10_000 },
  use: {
    baseURL: BASE_URL,
    // Not the zone of the server (UTC), so that a test can tell the browser's clock from the
    // server's; the clock times the tests expect are computed in it with `Intl`.
    timezoneId: "America/New_York",
    trace: "retain-on-failure",
  },
  projects: [
    { name: "e2e", testIgnore: /screenshots/ },
    { name: "screenshots", testMatch: /screenshots\.spec/ },
  ],
});
