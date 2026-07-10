import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "tests/web",
  testMatch: "scenarios.spec.mjs",
  fullyParallel: false,
  reporter: "line",
  use: {
    baseURL: "http://127.0.0.1:8765",
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
  webServer: {
    command:
      "python3 -m http.server 8765 --bind 127.0.0.1 --directory src/synthpopcan/web",
    url: "http://127.0.0.1:8765",
    reuseExistingServer: true,
  },
});
