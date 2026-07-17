import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { expect, test } from "@playwright/test";

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const linkedPackage = JSON.parse(
  readFileSync(
    path.join(
      repoRoot,
      "src/synthpopcan/models/demo-linked-household-person-package.json",
    ),
    "utf8",
  ),
);

async function readHorizontalLayout(page) {
  return page.evaluate(() => {
    const elements = [
      document.documentElement,
      document.body,
      ...document.querySelectorAll("body *"),
    ];
    const describe = (element) => {
      const id = element.id ? `#${element.id}` : "";
      const classes = [...element.classList]
        .slice(0, 3)
        .map((name) => `.${name}`)
        .join("");
      return `${element.tagName.toLowerCase()}${id}${classes} (client=${element.clientWidth}; scroll=${element.scrollWidth})`;
    };
    return {
      viewportWidth: window.innerWidth,
      documentScrollWidth: document.documentElement.scrollWidth,
      scrollContainers: elements
        .filter((element) => element.scrollWidth > element.clientWidth)
        .slice(0, 10)
        .map(describe),
    };
  });
}

test("SCN-WEB-001 runs durable demo IPF and recovers results after refresh", async ({
  page,
}) => {
  const consoleErrors = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  await page.route("**/api/models", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: '{"models":[]}',
    }),
  );
  await page.goto("/");
  await expect(page).toHaveTitle("SynthPopCan");
  await expect(page.getByRole("heading", { name: "Runs" })).toBeVisible();
  await expect(page.getByRole("button", { name: "New run" })).toHaveCount(1);
  await page.getByRole("button", { name: /Use demo age\/sex files/ }).click();
  await expect(page.locator("#seed-upload-status")).toContainText(
    "demo-age-sex-seed.csv",
  );
  await page.getByRole("button", { name: "Upload and continue" }).click();
  await expect(page.getByRole("heading", { name: "Configure the fit" })).toBeVisible();
  await expect(
    page.getByText("Compact fitted weights — one row per seed profile."),
  ).toBeVisible();
  await expect(page.locator("#ipf-max-iterations")).toBeHidden();
  await page.getByRole("button", { name: "Check inputs" }).click();
  await expect(page.getByRole("heading", { name: "Preflight" })).toBeVisible();
  await expect(page.locator("#preflight-results")).toContainText("4");
  await expect(page.locator("#preflight-results")).toContainText("age, sex");
  await page.getByRole("button", { name: "Start run" }).click();
  await expect(page.getByRole("heading", { name: "Results" })).toBeVisible({
    timeout: 15_000,
  });
  await expect(page.locator("#fit-diagnostics")).toContainText("Converged");
  await expect(page.locator("#weights-preview")).toContainText("weight");
  await expect(page.locator("#weights-preview tbody tr")).toHaveCount(4);
  await expect(page.getByRole("link", { name: "Download weights.csv" })).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Download fit-report.json" }),
  ).toBeVisible();
  await expect(page.locator("#reproduction-command")).toContainText(
    "synthpopcan ipf fit",
  );
  await expect(page.locator(".run-list-item")).toHaveCount(1);

  await page.setViewportSize({ width: 375, height: 812 });
  await page.reload();
  await expect(page.getByRole("heading", { name: "Results" })).toBeVisible();
  await expect(page.locator("#weights-preview tbody tr")).toHaveCount(4);
  const layout = await readHorizontalLayout(page);
  expect(layout.documentScrollWidth, JSON.stringify(layout)).toBeLessThanOrEqual(
    layout.viewportWidth,
  );
  expect(consoleErrors).toEqual([]);
});

test("durable IPF preflight blocks incompatible inputs", async ({ page }) => {
  await page.route("**/api/models", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: '{"models":[]}',
    }),
  );
  await page.goto("/");
  await page.getByRole("button", { name: "New run" }).click();
  await page.locator("#ipf-seed-file").setInputFiles({
    name: "seed.csv",
    mimeType: "text/csv",
    buffer: Buffer.from("id,age\n1,young\n"),
  });
  await page.locator("#ipf-controls-file").setInputFiles({
    name: "controls.csv",
    mimeType: "text/csv",
    buffer: Buffer.from("margin,dimensions,age,count\nage,age,old,1\n"),
  });
  await page.getByRole("button", { name: "Upload and continue" }).click();
  await page.getByRole("button", { name: "Check inputs" }).click();
  await expect(page.locator("#workbench-message")).toContainText(
    "missing control categories",
  );
  await expect(page.getByRole("button", { name: "Start run" })).toBeDisabled();
});

test("active durable IPF run can be cancelled", async ({ page }) => {
  await page.route("**/api/models", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: '{"models":[]}',
    }),
  );
  await page.goto("/");
  await page.getByRole("button", { name: "New run" }).click();
  await page.getByRole("button", { name: /Use demo age\/sex files/ }).click();
  await page.getByRole("button", { name: "Upload and continue" }).click();
  await page.getByRole("button", { name: "Check inputs" }).click();
  await page.getByRole("button", { name: "Start run" }).click();
  const cancel = page.getByRole("button", { name: "Cancel run" });
  await cancel.click();
  await expect(page.locator("#run-status")).toContainText(/Cancelled|Cancelling/, {
    timeout: 10_000,
  });
});

test("SCN-WEB-002 inspects and generates from a linked model package", async ({
  page,
}) => {
  const consoleErrors = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  let installed = false;
  await page.route("**/api/models/downloadable-linked-model/fetch", async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 250));
    installed = true;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ model: linkedPackage }),
    });
  });
  await page.route("**/api/models", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        models: [
          {
            id: "downloadable-linked-model",
            name: "Downloadable linked model",
            geography: "Demo geography",
            description: "A model downloaded on first use.",
            installed,
            size_bytes: 1_009_496,
            release_status: "publishable_candidate",
            provenance: "Synthetic browser test package",
            privacy: "No raw rows",
          },
          {
            id: "oversized-linked-model",
            name: "Oversized linked model",
            geography: "Canada",
            description: "Too large for browser memory.",
            installed: false,
            browser_compatible: false,
          },
        ],
      }),
    }),
  );

  await page.goto("/");
  await page.getByText("Legacy browser tools").click();
  await page.getByRole("button", { name: /Generate from existing model/ }).click();
  await expect(page.getByRole("button", { name: "Generate rows" })).toBeDisabled();
  await expect(page.locator("#model-rows")).toBeDisabled();
  await expect(page.locator("#premade-model")).toContainText("download required");
  await expect(
    page.locator('#premade-model option[value="oversized-linked-model"]'),
  ).toHaveJSProperty("disabled", true);
  await expect(page.locator("#premade-model")).toContainText("CLI only");
  await page.locator("#premade-model").selectOption("downloadable-linked-model");
  await page.getByRole("button", { name: "Use premade model" }).click();
  await expect(page.locator("#model-download-status")).toBeVisible();
  await expect(page.locator("#model-download-status")).toContainText(
    "986 KB compressed",
  );
  await expect(page.locator("#model-download-status")).toBeHidden();
  await expect(page.locator("#model-inspect-result")).toContainText(
    "Linked household/person package",
  );
  await expect(page.locator("#model-ready-status")).toContainText("Ready:");
  await expect(page.getByRole("button", { name: "Generate rows" })).toBeEnabled();
  await expect(page.locator("#model-rows")).toBeEnabled();
  await expect(page.locator("#model-row-label-text")).toHaveText("Households");
  await expect(page.locator("#premade-model")).not.toContainText("download required");
  await page.locator("#model-rows").fill("4");
  await page.locator("#model-conditions").fill("geo=QC");
  await page.getByRole("button", { name: "Generate rows" }).click();
  await expect(page.locator("#model-result")).toContainText("Generated 4 household");
  await expect(page.locator("#model-result")).toContainText("Validation summary");
  await expect(
    page.getByRole("link", { name: "Download synthpopcan-households.csv" }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Download synthpopcan-persons.csv" }),
  ).toBeVisible();
  await expect(page.locator("#model-result")).toContainText(
    "synthpopcan models generate",
  );
  await expect(page.locator("#model-result")).toContainText(
    "# Generate a linked population directory",
  );
  expect(consoleErrors).toEqual([]);
});

test("SCN-WEB-003 prepares a small-area run and CLI handoff", async ({ page }) => {
  const consoleErrors = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  await page.route("**/api/models", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        models: [
          {
            id: "montreal-cma-2016-all-fields",
            name: "Montreal CMA 2016 broad linked package",
            geography: "Montreal CMA (CMA 462)",
            description: "Published linked package",
            installed: false,
            distribution: "download",
            census_vintage: "2016 Census",
            release_status: "publishable_candidate",
            release_version: "v0.2.1",
            provenance: "Statistics Canada 2016 Census hierarchical PUMF.",
            privacy: "No raw rows or source identifiers.",
            generation_limits: "Use the CLI for large outputs.",
            known_limitations: "Requires small-area calibration.",
          },
        ],
      }),
    }),
  );
  await page.route("**/api/small-area/estimate", (route) => {
    const request = route.request().postDataJSON();
    expect(request.geographyDimension).toBe("ct");
    expect(request.candidateHouseholds).toBe(20_000);
    expect(request.controlsCsv).toContain("household_size_group");
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        controlDimensions: ["ct", "household_size_group"],
        estimate: {
          target_geographies: 951,
          target_households: 1_830_000,
          estimated_persons: 4_062_600,
          estimated_total_output_rows: 5_892_600,
          candidate_households: 20_000,
          calibration_pool_size: 10_000,
          recommended_surface: "cli_or_python_api",
          guidance: [
            "Calibration will fit 10,000 candidate households for each target geography.",
            "Use the CLI or Python API for large linked CSV outputs.",
          ],
        },
      }),
    });
  });

  await page.goto("/");
  await page.getByText("Legacy browser tools").click();
  await page.getByRole("button", { name: /Prepare a small-area synthesis/ }).click();
  await page
    .locator("#small-area-premade-model")
    .selectOption("montreal-cma-2016-all-fields");
  await page.locator("#small-area-controls-file").setInputFiles({
    name: "montreal-ct-controls.csv",
    mimeType: "text/csv",
    buffer: Buffer.from(
      'margin,dimensions,ct,household_size_group,count\nsize,"ct,household_size_group",001,1,10\n',
    ),
  });
  await page.locator("#small-area-candidate-households").fill("20000");
  await page.locator("#small-area-pool-size").fill("10000");
  await page.locator("#small-area-subsample-seed").fill("7");
  await page.getByRole("button", { name: "Estimate and prepare" }).click();

  const result = page.locator("#small-area-result");
  await expect(result).toContainText("Use the CLI for this run size");
  await expect(result).toContainText("1,830,000");
  await expect(result).toContainText("5,892,600");
  await expect(result).toContainText("Continue in the CLI");
  await result.locator("summary").click();
  await expect(result).toContainText(
    "synthpopcan models fetch 'montreal-cma-2016-all-fields'",
  );
  await expect(result).toContainText("synthpopcan geo estimate");
  await expect(result).toContainText("synthpopcan geo synthesize");
  await expect(result).toContainText("--max-household-size 5");
  await expect(result).toContainText(
    "--household-size-group-column household_size_group",
  );
  await expect(result).toContainText("--random-seed 13");
  await expect(result).toContainText("--subsample-seed 7");
  await expect(result).toContainText("# Recheck output scale");
  expect(consoleErrors).toEqual([]);
});

test("model catalogue failure leaves both workflows usable", async ({ page }) => {
  const consoleErrors = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  await page.route("**/api/models", (route) =>
    route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({ error: "catalogue unavailable" }),
    }),
  );

  await page.goto("/");
  await expect(page.locator("#premade-model")).toContainText(
    "Premade models unavailable",
  );
  await expect(page.locator("#small-area-premade-model")).toContainText(
    "Premade models unavailable",
  );
  expect(consoleErrors.filter((message) => message.includes("ReferenceError"))).toEqual(
    [],
  );
});
