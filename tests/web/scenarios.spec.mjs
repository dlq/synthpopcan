import path from "node:path";
import { fileURLToPath } from "node:url";

import { expect, test } from "@playwright/test";

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");

test("SCN-WEB-001 runs demo IPF and exposes the weights artifact", async ({ page }) => {
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
  await expect(page.getByRole("heading", { name: "Choose a workflow" })).toBeVisible();
  await page.getByRole("button", { name: /Use demo age\/sex files/ }).click();
  await expect(page.locator("#ipf-result")).toContainText(
    "Demo seed and controls are loaded",
  );
  await page.getByRole("button", { name: "Run IPF" }).click();
  await expect(page.locator("#ipf-result")).toContainText("IPF converged");
  await expect(
    page.getByRole("link", { name: "Download synthpopcan-ipf-weights.csv" }),
  ).toBeVisible();
  await expect(page.getByText("Preview: synthpopcan-ipf-weights.csv")).toBeVisible();
  await page.setViewportSize({ width: 320, height: 844 });
  await page.reload();
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth),
  ).toBe(false);
  expect(consoleErrors).toEqual([]);
});

test("SCN-WEB-002 inspects and generates from a linked model package", async ({
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
  await page.getByRole("button", { name: /Generate from existing model/ }).click();
  await page
    .locator("#model-file")
    .setInputFiles(
      path.join(
        repoRoot,
        "src/synthpopcan/models/demo-linked-household-person-package.json",
      ),
    );
  await page.getByRole("button", { name: "Inspect selected model" }).click();
  await expect(page.locator("#model-inspect-result")).toContainText(
    "Linked household/person package",
  );
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
  expect(consoleErrors).toEqual([]);
});
