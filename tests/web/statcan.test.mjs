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
      suitability: "review",
    },
  ]);
});

test("ranks population estimates above rate tables and treats sex as gender", () => {
  const rows = [
    {
      productId: "13100022",
      cansimId: "13-10-0022",
      cubeTitleEn: "Age-standardized survival rate by sex, population aged 45 and over",
      cubeEndDate: "2003-01-01T05:00:00Z",
    },
    {
      productId: "17100005",
      cansimId: "17-10-0005",
      cubeTitleEn: "Population estimates on July 1, by age and gender",
      cubeEndDate: "2025-01-01T05:00:00Z",
    },
  ];

  assert.deepEqual(searchWdsInventoryRows(rows, "population age sex", 5), [
    {
      productId: "17100005",
      cansimId: "17-10-0005",
      title: "Population estimates on July 1, by age and gender",
      startDate: "",
      endDate: "2025-01-01",
      suitability: "population-count",
    },
    {
      productId: "13100022",
      cansimId: "13-10-0022",
      title: "Age-standardized survival rate by sex, population aged 45 and over",
      startDate: "",
      endDate: "2003-01-01",
      suitability: "caution",
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

test("rejects WDS download URLs outside the trusted StatCan HTTPS host", async () => {
  const untrustedUrls = [
    "javascript:alert(1)",
    "http://www150.statcan.gc.ca/n1/tbl/csv/13100006-eng.zip",
    "https://example.com/13100006-eng.zip",
    "https://www150.statcan.gc.ca.example.com/13100006-eng.zip",
    "https://user@www150.statcan.gc.ca/13100006-eng.zip",
    "https://www150.statcan.gc.ca:8443/13100006-eng.zip",
  ];

  for (const object of untrustedUrls) {
    await assert.rejects(
      fetchWdsDownloadUrl("13100006", {
        fetchImpl: async () => ({
          ok: true,
          json: async () => ({ status: "SUCCESS", object }),
        }),
      }),
      /trusted www150\.statcan\.gc\.ca HTTPS host/,
    );
  }
});

test("rejects malformed WDS download URLs", async () => {
  await assert.rejects(
    fetchWdsDownloadUrl("13100006", {
      fetchImpl: async () => ({
        ok: true,
        json: async () => ({ status: "SUCCESS", object: "not a URL" }),
      }),
    }),
    /invalid download URL/,
  );
});
