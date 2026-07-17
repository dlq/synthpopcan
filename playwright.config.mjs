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
      "UV_CACHE_DIR=/tmp/synthpopcan-uv-cache uv run synthpopcan serve --host 127.0.0.1 --port 8765 --no-open --workspace /tmp/synthpopcan-e2e-runs",
    url: "http://127.0.0.1:8765",
    reuseExistingServer: true,
  },
});
