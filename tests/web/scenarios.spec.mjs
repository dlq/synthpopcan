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

test("SCN-WEB-001 runs demo IPF and exposes expanded synthetic records", async ({
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
  await page.route("**/api/wds/seed-controls", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        seedCsv: "id,GEO,Gender,Age group\nseed-1,Canada,Men+,0 years\n",
        controlsCsv:
          'margin,dimensions,GEO,Gender,Age group,count\nwds,"GEO,Gender,Age group",Canada,Men+,0 years,100\nwds,"GEO,Gender,Age group",Yukon,Men+,0 years,11\nwds,"GEO,Gender,Age group",Yukon,Women+,0 years,12\nwds,"GEO,Gender,Age group",Yukon,Total - gender,All ages,50\n',
        dimensions: ["GEO", "Gender", "Age group"],
        countColumn: "VALUE",
        csvMember: "17100005.csv",
        referencePeriod: "2025",
        categories: {
          GEO: ["Canada", "Yukon"],
          Gender: ["Total - gender", "Men+", "Women+"],
          "Age group": ["All ages", "0 years"],
        },
        estimatedTotal: 173,
        unitRows: [
          { GEO: "Canada", Gender: "Men+", "Age group": "0 years", unit: "Persons" },
          { GEO: "Yukon", Gender: "Men+", "Age group": "0 years", unit: "Persons" },
          { GEO: "Yukon", Gender: "Women+", "Age group": "0 years", unit: "Persons" },
          {
            GEO: "Yukon",
            Gender: "Total - gender",
            "Age group": "All ages",
            unit: "Persons",
          },
        ],
      }),
    }),
  );

  await page.goto("/");
  await expect(page).toHaveTitle("SynthPopCan");
  await expect(page.getByRole("heading", { name: "Choose a workflow" })).toBeVisible();
  const demoSetupTab = page.getByRole("button", {
    name: "Use a demo or make templates",
  });
  const statcanSetupTab = page.getByRole("button", {
    name: "Generate from a StatCan table",
  });
  await expect(demoSetupTab).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByRole("button", { name: "Search", exact: true })).toBeHidden();
  await page.locator("#starter-dimensions").fill("age, household_size");
  await statcanSetupTab.click();
  await expect(statcanSetupTab).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByRole("button", { name: "Search", exact: true })).toBeVisible();
  const stagedResultOrder = await page
    .locator("#setup-statcan-panel > [id]")
    .evaluateAll((elements) => elements.map((element) => element.id));
  expect(stagedResultOrder).toEqual([
    "wds-search-form",
    "wds-search-result",
    "wds-explain-form",
    "wds-metadata-result",
    "wds-refinement",
    "wds-generated-result",
  ]);
  await page.locator("#wds-search-query").fill("population households");
  await page.getByRole("button", { name: "Use 17100005" }).click();
  await expect(page.getByRole("region", { name: "Refine WDS table" })).toBeVisible();
  await page.locator("#wds-filter-geo").selectOption("Yukon");
  await expect(page.locator("#wds-selection-estimate")).toContainText(
    "about 23 expanded records",
  );
  await page.getByRole("button", { name: "Generate selected IPF files" }).click();
  await expect(
    page.getByRole("link", { name: "Download synthpopcan-wds-selection.json" }),
  ).toBeVisible();
  await expect(page.locator("#wds-generated-result")).toContainText(
    "synthpopcan controls from-wds",
  );
  await expect(page.locator("#wds-generated-result")).toContainText(
    "# Rebuild normalized controls",
  );
  await page.setViewportSize({ width: 768, height: 900 });
  const refinementLayout = await readHorizontalLayout(page);
  expect(
    refinementLayout.documentScrollWidth,
    JSON.stringify(refinementLayout),
  ).toBeLessThanOrEqual(refinementLayout.viewportWidth);
  await page.setViewportSize({ width: 1280, height: 900 });
  await demoSetupTab.click();
  await expect(page.locator("#starter-dimensions")).toHaveValue("age, household_size");
  await statcanSetupTab.click();
  await expect(page.locator("#wds-search-query")).toHaveValue("population households");
  await demoSetupTab.click();
  await page.getByRole("button", { name: /Use demo age\/sex files/ }).click();
  await expect(page.locator("#ipf-result")).toContainText(
    "Demo seed and controls are loaded",
  );
  await expect(page.locator("#ipf-seed-file")).toHaveClass(/file-ready/);
  await expect(page.locator("#ipf-controls-file")).toHaveClass(/file-ready/);
  await expect(page.locator("#ipf-output-kind")).toHaveValue("expanded");
  await expect(page.locator("#ipf-output-hint")).toContainText(
    "One integerized row per synthetic record",
  );
  await page.getByRole("button", { name: "Run IPF" }).click();
  await expect(page.locator("#ipf-result")).toContainText("IPF converged");
  await expect(
    page.getByRole("link", { name: "Download synthpopcan-ipf-expanded.csv" }),
  ).toBeVisible();
  await expect(page.getByText("Preview: synthpopcan-ipf-expanded.csv")).toBeVisible();
  await expect(page.locator("#ipf-result")).toContainText("synthetic_id");
  await expect(page.locator("#ipf-result")).toContainText("Continue in the CLI");
  await expect(page.locator("#ipf-result .cli-follow-up")).not.toHaveAttribute("open");
  await expect(page.locator("#ipf-result")).toContainText(
    "reproduce or continue this workflow",
  );
  await expect(page.locator("#ipf-result")).toContainText(
    "synthpopcan ipf check-inputs",
  );
  await expect(page.locator("#ipf-result")).toContainText(
    "# Fit one compact IPF weight per seed row",
  );
  await page.setViewportSize({ width: 768, height: 900 });
  await page.reload();
  const layout = await readHorizontalLayout(page);
  expect(layout.documentScrollWidth, JSON.stringify(layout)).toBeLessThanOrEqual(
    layout.viewportWidth,
  );
  expect(consoleErrors).toEqual([]);
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
        ],
      }),
    }),
  );

  await page.goto("/");
  await page.getByRole("button", { name: /Generate from existing model/ }).click();
  await expect(page.getByRole("button", { name: "Generate rows" })).toBeDisabled();
  await expect(page.locator("#model-rows")).toBeDisabled();
  await expect(page.locator("#premade-model")).toContainText("download required");
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
    "synthpopcan tree generate-from-package",
  );
  await expect(page.locator("#model-result")).toContainText(
    "# Generate linked household and person CSVs",
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
  await expect(result).toContainText("synthpopcan geo estimate-run");
  await expect(result).toContainText("synthpopcan geo synthesize-from-package");
  await expect(result).toContainText("--max-household-size 5");
  await expect(result).toContainText(
    "--household-size-group-column household_size_group",
  );
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
