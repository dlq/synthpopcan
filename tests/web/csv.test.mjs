import assert from "node:assert/strict";
import test from "node:test";

import { parseCsv, stringifyCsv } from "../../src/synthpopcan/web/csv.mjs";

test("parses quoted csv values and preserves headers", () => {
  const rows = parseCsv('id,name,count\n1,"Montréal, QC",2\n');

  assert.deepEqual(rows, [{ id: "1", name: "Montréal, QC", count: "2" }]);
});

test("stringifies rows with stable columns and quoting", () => {
  const csv = stringifyCsv([{ id: "1", name: "Montréal, QC", count: "2" }]);

  assert.equal(csv, 'id,name,count\n1,"Montréal, QC",2\n');
});
