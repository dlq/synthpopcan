import assert from "node:assert/strict";
import test from "node:test";

import { parseCsv } from "../../src/synthpopcan/web/csv.mjs";
import {
  buildSeedRowsFromControlRows,
  chooseWdsDataCsvEntry,
  normalizeWdsRows,
  resolveWdsDimensions,
  snapshotWdsRows,
  suggestWdsColumns,
} from "../../src/synthpopcan/web/wds-normalize.mjs";
import { readZipEntries } from "../../src/synthpopcan/web/zip.mjs";

test("normalizes WDS rows into controls and compatible seed rows", () => {
  const rows = parseCsv(
    "GEO,Age group,Sex,VALUE,STATUS\n" +
      "Canada,0 to 4 years,Female,100,\n" +
      "Canada,0 to 4 years,Male,105,\n",
  );

  const controls = normalizeWdsRows(rows, {
    dimensions: ["GEO", "Age group", "Sex"],
    countColumn: "VALUE",
    marginName: "population",
  });
  const seed = buildSeedRowsFromControlRows(controls);

  assert.deepEqual(controls, [
    {
      margin: "population",
      dimensions: "GEO,Age group,Sex",
      GEO: "Canada",
      "Age group": "0 to 4 years",
      Sex: "Female",
      count: "100",
    },
    {
      margin: "population",
      dimensions: "GEO,Age group,Sex",
      GEO: "Canada",
      "Age group": "0 to 4 years",
      Sex: "Male",
      count: "105",
    },
  ]);
  assert.deepEqual(seed, [
    { id: "seed-1", GEO: "Canada", "Age group": "0 to 4 years", Sex: "Female" },
    { id: "seed-2", GEO: "Canada", "Age group": "0 to 4 years", Sex: "Male" },
  ]);
});

test("reports original WDS row numbers after skipped blank counts", () => {
  const rows = parseCsv(
    "GEO,Sex,VALUE\n" + "Canada,Female,\n" + "Canada,Male,not-a-number\n",
  );

  assert.throws(
    () =>
      normalizeWdsRows(rows, {
        dimensions: ["GEO", "Sex"],
        countColumn: "VALUE",
        marginName: "population",
      }),
    /WDS row 3 has invalid count/,
  );
});

test("suggests WDS dimensions and value column", () => {
  const rows = parseCsv(
    "GEO,Age group,Sex,VALUE,STATUS\nCanada,0 to 4 years,Female,100,\n",
  );

  assert.deepEqual(suggestWdsColumns(rows), {
    dimensions: ["GEO", "Age group", "Sex"],
    countColumn: "VALUE",
  });
});

test("reads stored CSV entries from a ZIP file", async () => {
  const zipBytes = buildStoredZip("table.csv", "A,B\nx,1\n");

  const entries = await readZipEntries(zipBytes);

  assert.deepEqual(entries, [{ name: "table.csv", text: "A,B\nx,1\n" }]);
});

test("chooses the data CSV instead of the metadata CSV", () => {
  const entries = [
    { name: "13100005_MetaData.csv", text: "Cube Title,Product Id\nExample,1\n" },
    {
      name: "13100005.csv",
      text: "REF_DATE,GEO,Sex,VALUE\n1979,Canada,Female,100\n",
    },
  ];

  assert.deepEqual(chooseWdsDataCsvEntry(entries), entries[1]);
});

test("resolves readable WDS dimension labels to CSV column names", () => {
  const rows = parseCsv("REF_DATE,GEO,Sex,VALUE\n2021,Canada,Female,100\n");

  assert.deepEqual(resolveWdsDimensions(rows, ["Geography", "Sex"]), ["GEO", "Sex"]);
});

test("uses latest reference period by default for WDS snapshots", () => {
  const rows = parseCsv(
    "REF_DATE,GEO,Sex,VALUE\n" +
      "1979,Canada,Female,100\n" +
      "1980,Canada,Female,110\n" +
      "1980,Canada,Male,112\n",
  );

  assert.deepEqual(snapshotWdsRows(rows, ["GEO", "Sex"]), {
    rows: [
      { REF_DATE: "1980", GEO: "Canada", Sex: "Female", VALUE: "110" },
      { REF_DATE: "1980", GEO: "Canada", Sex: "Male", VALUE: "112" },
    ],
    referencePeriod: "1980",
  });
});

function buildStoredZip(name, text) {
  const encoder = new TextEncoder();
  const nameBytes = encoder.encode(name);
  const data = encoder.encode(text);
  const crc = crc32(data);
  const local = new Uint8Array(30 + nameBytes.length + data.length);
  const view = new DataView(local.buffer);
  view.setUint32(0, 0x04034b50, true);
  view.setUint16(4, 20, true);
  view.setUint16(8, 0, true);
  view.setUint32(14, crc, true);
  view.setUint32(18, data.length, true);
  view.setUint32(22, data.length, true);
  view.setUint16(26, nameBytes.length, true);
  local.set(nameBytes, 30);
  local.set(data, 30 + nameBytes.length);

  const central = new Uint8Array(46 + nameBytes.length);
  const centralView = new DataView(central.buffer);
  centralView.setUint32(0, 0x02014b50, true);
  centralView.setUint16(4, 20, true);
  centralView.setUint16(6, 20, true);
  centralView.setUint16(10, 0, true);
  centralView.setUint32(16, crc, true);
  centralView.setUint32(20, data.length, true);
  centralView.setUint32(24, data.length, true);
  centralView.setUint16(28, nameBytes.length, true);
  centralView.setUint32(42, 0, true);
  central.set(nameBytes, 46);

  const end = new Uint8Array(22);
  const endView = new DataView(end.buffer);
  endView.setUint32(0, 0x06054b50, true);
  endView.setUint16(8, 1, true);
  endView.setUint16(10, 1, true);
  endView.setUint32(12, central.length, true);
  endView.setUint32(16, local.length, true);

  return concatBytes(local, central, end).buffer;
}

function concatBytes(...arrays) {
  const total = arrays.reduce((sum, array) => sum + array.length, 0);
  const output = new Uint8Array(total);
  let offset = 0;
  arrays.forEach((array) => {
    output.set(array, offset);
    offset += array.length;
  });
  return output;
}

function crc32(bytes) {
  let crc = 0xffffffff;
  for (const byte of bytes) {
    crc ^= byte;
    for (let bit = 0; bit < 8; bit += 1) {
      crc = crc & 1 ? 0xedb88320 ^ (crc >>> 1) : crc >>> 1;
    }
  }
  return (crc ^ 0xffffffff) >>> 0;
}
