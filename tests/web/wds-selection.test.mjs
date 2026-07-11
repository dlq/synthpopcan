import assert from "node:assert/strict";
import test from "node:test";

import {
  ageCategoriesForScheme,
  buildWdsSelectionManifest,
  detailedCategories,
  filterWdsControlRows,
  summarizeWdsSelection,
} from "../../src/synthpopcan/web/wds-selection.mjs";

test("builds non-overlapping gender and age selections", () => {
  assert.deepEqual(detailedCategories(["Total - gender", "Men+", "Women+"]), [
    "Men+",
    "Women+",
  ]);
  const ages = ["All ages", "0 to 4 years", "0 years", "1 year", "5 to 9 years"];
  assert.deepEqual(ageCategoriesForScheme(ages, "single-year"), ["0 years", "1 year"]);
  assert.deepEqual(ageCategoriesForScheme(ages, "five-year"), [
    "0 to 4 years",
    "5 to 9 years",
  ]);
});

test("filters WDS controls and estimates expanded rows", () => {
  const rows = [
    { GEO: "Canada", Gender: "Men+", "Age group": "0 years", count: "100" },
    { GEO: "Yukon", Gender: "Men+", "Age group": "0 years", count: "11" },
    { GEO: "Yukon", Gender: "Women+", "Age group": "0 years", count: "12" },
  ];
  const selected = filterWdsControlRows(rows, {
    GEO: ["Yukon"],
    Gender: ["Men+", "Women+"],
    "Age group": ["0 years"],
  });
  assert.equal(selected.length, 2);
  assert.deepEqual(summarizeWdsSelection(selected), {
    cells: 2,
    estimatedTotal: 23,
  });
});

test("writes the CLI-compatible selection manifest", () => {
  assert.deepEqual(
    buildWdsSelectionManifest({
      productId: "17100005",
      referencePeriod: "2025",
      categories: { GEO: ["Yukon"] },
    }),
    {
      schema_version: "synthpopcan-wds-selection-v1",
      product_id: "17100005",
      reference_period: "2025",
      categories: { GEO: ["Yukon"] },
    },
  );
});
