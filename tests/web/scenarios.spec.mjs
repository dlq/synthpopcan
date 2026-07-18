import { expect, test } from "@playwright/test";

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
  await expect(page.locator("#primary-preview")).toContainText("weight");
  await expect(page.locator("#primary-preview tbody tr")).toHaveCount(4);
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
  await expect(page.locator("#primary-preview tbody tr")).toHaveCount(4);
  const layout = await readHorizontalLayout(page);
  expect(layout.documentScrollWidth, JSON.stringify(layout)).toBeLessThanOrEqual(
    layout.viewportWidth,
  );
  expect(consoleErrors).toEqual([]);
});

test("a new draft wins over a delayed initial run-history response", async ({
  page,
}) => {
  let detailRequested;
  const requestStarted = new Promise((resolve) => {
    detailRequested = resolve;
  });
  await page.route("**/api/runs/*", async (route) => {
    detailRequested();
    await new Promise((resolve) => setTimeout(resolve, 500));
    await route.continue();
  });
  await page.goto("/");
  await requestStarted;
  await page.getByRole("button", { name: "New run" }).click();
  await expect(page.locator("#ipf-seed-file")).toBeVisible();
  await page.waitForTimeout(750);
  await expect(page.locator("#ipf-seed-file")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Results" })).toBeHidden();
});

test("a new draft preserves a delayed initial model catalogue", async ({ page }) => {
  let catalogueRequested;
  let releaseCatalogue;
  const requested = new Promise((resolve) => {
    catalogueRequested = resolve;
  });
  const release = new Promise((resolve) => {
    releaseCatalogue = resolve;
  });
  await page.route("**/api/models", async (route) => {
    catalogueRequested();
    await release;
    await route.continue();
  });

  await page.goto("/");
  await requested;
  await page.getByRole("button", { name: "New run" }).click();
  await page
    .getByRole("button", { name: "Generate from a prepared model", exact: true })
    .click();
  releaseCatalogue();

  await expect(
    page.locator('#run-model-select option[value="demo-linked-household-person"]'),
  ).toHaveCount(1);
  await page.locator("#run-model-select").selectOption("demo-linked-household-person");
  await expect(page.locator("#run-model-select")).toHaveValue(
    "demo-linked-household-person",
  );
});

test("edited IPF settings win over a delayed preflight response", async ({ page }) => {
  let preflightStarted;
  let releasePreflight;
  const started = new Promise((resolve) => {
    preflightStarted = resolve;
  });
  const release = new Promise((resolve) => {
    releasePreflight = resolve;
  });
  await page.route("**/api/preflight", async (route) => {
    preflightStarted();
    await release;
    await route.continue();
  });
  await page.goto("/");
  await page.getByRole("button", { name: "New run" }).click();
  await page.getByRole("button", { name: /Use demo age\/sex files/ }).click();
  await page.getByRole("button", { name: "Upload and continue" }).click();
  await page.getByText("Advanced IPF settings").click();
  await page.getByRole("button", { name: "Check inputs" }).click();
  await started;
  await page.locator("#ipf-weight-field").fill("WEIGHT");
  releasePreflight();

  await expect(page.locator("#workbench-message")).toContainText("Inputs changed");
  await page.waitForTimeout(250);
  await expect(page.getByRole("heading", { name: "Configure the fit" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Preflight" })).toBeHidden();
  await expect(page.locator("#start-run")).toBeDisabled();
});

test("edited model settings win over a delayed preflight response", async ({
  page,
}) => {
  let preflightStarted;
  let releasePreflight;
  const started = new Promise((resolve) => {
    preflightStarted = resolve;
  });
  const release = new Promise((resolve) => {
    releasePreflight = resolve;
  });
  await page.route("**/api/preflight", async (route) => {
    preflightStarted();
    await release;
    await route.continue();
  });
  await page.goto("/");
  await page.getByRole("button", { name: "New run" }).click();
  await page
    .getByRole("button", { name: "Generate from a prepared model", exact: true })
    .click();
  await page.locator("#run-model-select").selectOption("demo-linked-household-person");
  await page.getByRole("button", { name: "Check model and scale" }).click();
  await started;
  await page.locator("#run-model-households").fill("11");
  releasePreflight();

  await expect(page.locator("#workbench-message")).toContainText("Inputs changed");
  await page.waitForTimeout(250);
  await expect(
    page.getByRole("heading", { name: "Generate from a prepared model" }),
  ).toBeVisible();
  await expect(page.getByRole("heading", { name: "Preflight" })).toBeHidden();
  await expect(page.locator("#start-run")).toBeDisabled();
  await expect(
    page.getByRole("button", { name: "Check model and scale" }),
  ).toBeEnabled();
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
  await page.goto("/");
  await page.getByRole("button", { name: "New run" }).click();
  await page
    .getByRole("button", { name: "Generate from a prepared model", exact: true })
    .click();
  await page.locator("#run-model-select").selectOption("demo-linked-household-person");
  await page.locator("#run-model-households").fill("4");
  await page.locator("#run-model-conditions").fill("geo=Demo North");
  await page.getByRole("button", { name: "Check model and scale" }).click();
  await expect(page.getByRole("heading", { name: "Preflight" })).toBeVisible();
  await expect(page.locator("#preflight-results")).toContainText(
    "Publishable candidate",
  );
  await expect(page.locator("#preflight-results")).toContainText(
    /safe synthetic demo/i,
  );
  await page.getByRole("button", { name: "Start run" }).click();
  await expect(page.getByRole("heading", { name: "Results" })).toBeVisible({
    timeout: 15_000,
  });
  await expect(page.locator("#fit-diagnostics")).toContainText("Generated households");
  await expect(page.locator("#fit-diagnostics")).toContainText("Passed");
  await expect(page.locator("#primary-preview tbody tr")).toHaveCount(4);
  await expect(page.locator("#secondary-preview tbody tr")).not.toHaveCount(0);
  await expect(
    page.getByRole("link", { name: "Download households.csv" }),
  ).toBeVisible();
  await expect(page.getByRole("link", { name: "Download persons.csv" })).toBeVisible();
  await expect(page.locator("#reproduction-command")).toContainText(
    "synthpopcan models generate",
  );
  expect(consoleErrors).toEqual([]);
});

test("downloadable catalogue models install without returning their payload", async ({
  page,
}) => {
  let installed = false;
  const model = () => ({
    id: "large-model",
    name: "Large model",
    geography: "Canada",
    distribution: "download",
    installed,
  });
  await page.route("**/api/models", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ models: [model()] }),
    }),
  );
  await page.route("**/api/models/large-model/install", (route) => {
    installed = true;
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ model: model() }),
    });
  });

  await page.goto("/");
  await page.getByRole("button", { name: "New run" }).click();
  await page
    .getByRole("button", { name: "Generate from a prepared model", exact: true })
    .click();
  await page.locator("#run-model-select").selectOption("large-model");
  await expect(
    page.getByRole("button", { name: "Download selected model" }),
  ).toBeEnabled();
  await page.getByRole("button", { name: "Download selected model" }).click();
  await expect(page.locator("#run-model-catalogue-status")).toContainText(
    "downloaded, verified",
  );
  await expect(page.locator("#run-model-select")).toHaveValue("large-model");
  await expect(
    page.getByRole("button", { name: "Remove downloaded model" }),
  ).toBeEnabled();
});

test("SCN-WEB-003 runs durable linked small-area synthesis", async ({ page }) => {
  const consoleErrors = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  let firstPreflightStarted;
  let releaseFirstPreflight;
  let holdFirstPreflight = true;
  const preflightStarted = new Promise((resolve) => {
    firstPreflightStarted = resolve;
  });
  const releasePreflight = new Promise((resolve) => {
    releaseFirstPreflight = resolve;
  });
  await page.route("**/api/preflight", async (route) => {
    if (holdFirstPreflight) {
      holdFirstPreflight = false;
      firstPreflightStarted();
      await releasePreflight;
    }
    await route.continue();
  });
  await page.goto("/");
  await page.getByText("Small-area workflow").click();
  await page.getByRole("button", { name: /Prepare a small-area synthesis/ }).click();
  await page
    .locator("#small-area-premade-model")
    .selectOption("demo-linked-household-person");
  await page.locator("#small-area-controls-file").setInputFiles({
    name: "demo-tract-controls.csv",
    mimeType: "text/csv",
    buffer: Buffer.from(
      "margin,dimensions,tract,tenure,count\n" +
        'tenure,"tract,tenure",001,owner,2\n' +
        'tenure,"tract,tenure",001,renter,1\n' +
        'tenure,"tract,tenure",002,owner,2\n' +
        'tenure,"tract,tenure",002,renter,1\n',
    ),
  });
  await page.locator("#small-area-geo-dimension").fill("tract");
  await page.locator("#small-area-candidate-households").fill("20");
  await page.locator("#small-area-pool-size").fill("20");
  await page.locator("#small-area-subsample-seed").fill("7");
  await page.getByRole("button", { name: "Estimate and prepare" }).click();
  await preflightStarted;
  await page.locator("#small-area-candidate-households").fill("21");
  releaseFirstPreflight();
  await expect(page.locator("#small-area-result")).toContainText("Inputs changed");
  await expect(
    page.getByRole("button", { name: "Start durable small-area run" }),
  ).toHaveCount(0);
  await page.locator("#small-area-candidate-households").fill("20");
  await page.getByRole("button", { name: "Estimate and prepare" }).click();

  const result = page.locator("#small-area-result");
  await expect(result).toContainText("Target geographies2");
  await result.getByRole("button", { name: "Start durable small-area run" }).click();
  await expect(page.getByRole("heading", { name: "Results" })).toBeVisible({
    timeout: 15_000,
  });
  await expect(page.locator("#fit-diagnostics")).toContainText("Assigned households");
  await expect(page.locator("#fit-diagnostics")).toContainText("Non-converged");
  await expect(page.locator("#primary-preview tbody tr")).toHaveCount(6);
  await expect(page.locator("#secondary-preview tbody tr")).not.toHaveCount(0);
  await expect(page.getByRole("link", { name: "Download report.json" })).toBeVisible();
  await expect(page.locator("#reproduction-command")).toContainText(
    "synthpopcan geo synthesize",
  );
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
  await page.getByRole("button", { name: "New run" }).click();
  await page
    .getByRole("button", { name: "Generate from a prepared model", exact: true })
    .click();
  await expect(page.locator("#run-model-select")).toContainText(
    "Premade models unavailable",
  );
  await expect(page.locator("#small-area-premade-model")).toContainText(
    "Premade models unavailable",
  );
  expect(consoleErrors.filter((message) => message.includes("ReferenceError"))).toEqual(
    [],
  );
});
