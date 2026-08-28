import { defineConfig } from "@playwright/test";

const workspace = `/tmp/synthpopcan-e2e-runs-${process.pid}`;
const port = Number(process.env.SYNTHPOPCAN_E2E_PORT ?? "18765");
if (!Number.isInteger(port) || port < 1024 || port > 65535) {
  throw new Error("SYNTHPOPCAN_E2E_PORT must be an integer from 1024 to 65535");
}
const baseURL = `http://127.0.0.1:${port}`;

export default defineConfig({
  testDir: "tests/web",
  testMatch: "scenarios.spec.mjs",
  fullyParallel: false,
  reporter: "line",
  use: {
    baseURL,
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
  webServer: {
    command:
      `UV_CACHE_DIR=/tmp/synthpopcan-uv-cache uv run synthpopcan serve --host 127.0.0.1 --port ${port} --no-open --workspace ${workspace}`,
    url: baseURL,
    reuseExistingServer: false,
  },
});
