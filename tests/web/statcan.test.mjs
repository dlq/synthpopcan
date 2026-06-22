import assert from "node:assert/strict";
import test from "node:test";

import {
  fetchWdsDownloadUrl,
  searchWdsInventoryRows,
  summarizeWdsMetadata,
} from "../../src/synthpopcan/web/statcan.mjs";

test("searches WDS inventory rows by all query terms", () => {
  const rows = [
    {
      productId: "98100001",
      cansimId: "98-10-0001",
      cubeTitleEn: "Population by age and sex",
      cubeStartDate: "2021-01-01",
      cubeEndDate: "2021-01-01",
    },
    {
      productId: "14100001",
      cansimId: "14-10-0001",
      cubeTitleEn: "Labour force characteristics",
      cubeStartDate: "2024-01-01",
      cubeEndDate: "2024-01-01",
    },
  ];

  assert.deepEqual(searchWdsInventoryRows(rows, "population sex", 5), [
    {
      productId: "98100001",
      cansimId: "98-10-0001",
      title: "Population by age and sex",
      startDate: "2021-01-01",
      endDate: "2021-01-01",
    },
  ]);
});

test("summarizes WDS metadata dimensions for IPF setup", () => {
  const summary = summarizeWdsMetadata({
    productId: 98100001,
    cubeTitleEn: "Population by age and sex",
    cubeStartDate: "2021-01-01",
    cubeEndDate: "2021-01-01",
    dimension: [
      { dimensionNameEn: "Geography" },
      { dimensionNameEn: "Age group" },
      { dimensionNameEn: "Sex" },
    ],
  });

  assert.deepEqual(summary, {
    productId: "98100001",
    title: "Population by age and sex",
    dateRange: "2021-01-01",
    dimensions: ["Geography", "Age group", "Sex"],
    hint: "This looks plausible for IPF if your seed has matching geography, age group, and sex columns.",
    suggestedControlColumns: ["Geography", "Age group", "Sex"],
  });
});

test("fetches a WDS download URL from the product endpoint", async () => {
  const calls = [];
  const url = await fetchWdsDownloadUrl("13100006", {
    fetchImpl: async (requestedUrl) => {
      calls.push(requestedUrl);
      return {
        ok: true,
        json: async () => ({
          status: "SUCCESS",
          object: "https://www150.statcan.gc.ca/n1/tbl/csv/13100006-eng.zip",
        }),
      };
    },
  });

  assert.deepEqual(calls, [
    "https://www150.statcan.gc.ca/t1/wds/rest/getFullTableDownloadCSV/13100006/en",
  ]);
  assert.equal(url, "https://www150.statcan.gc.ca/n1/tbl/csv/13100006-eng.zip");
});
