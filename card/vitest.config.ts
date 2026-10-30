import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "happy-dom",
    include: ["test/**/*.test.ts"],
    setupFiles: ["test/setup.ts"],
    // The scenarios compute expected clock times in this zone, whatever the machine's.
    env: { TZ: "America/New_York" },
  },
});
