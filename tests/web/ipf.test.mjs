import assert from "node:assert/strict";
import test from "node:test";

import {
  expandRecords,
  fitIpf,
  readControlTable,
  weightsToRows,
} from "../../src/synthpopcan/web/ipf.mjs";

test("fits two one-way margins and exports weight rows", () => {
  const seedRows = [
    { id: "1", age: "young", sex: "F" },
    { id: "2", age: "young", sex: "M" },
    { id: "3", age: "old", sex: "F" },
    { id: "4", age: "old", sex: "M" },
  ];
  const controls = readControlTable([
    { margin: "age", dimensions: "age", age: "young", sex: "", count: "60" },
    { margin: "age", dimensions: "age", age: "old", sex: "", count: "40" },
    { margin: "sex", dimensions: "sex", age: "", sex: "F", count: "50" },
    { margin: "sex", dimensions: "sex", age: "", sex: "M", count: "50" },
  ]);

  const result = fitIpf(seedRows, controls.margins, { tolerance: 1e-9 });

  assert.equal(result.converged, true);
  assert.deepEqual(
    result.weights.map((weight) => Math.round(weight)),
    [30, 30, 20, 20],
  );
  assert.deepEqual(weightsToRows(seedRows, result.weights), [
    { seed_id: "1", weight: "30" },
    { seed_id: "2", weight: "30" },
    { seed_id: "3", weight: "20" },
    { seed_id: "4", weight: "20" },
  ]);
});

test("expands fitted weights into synthetic records", () => {
  const rows = expandRecords(
    [
      { id: "a", age: "young" },
      { id: "b", age: "old" },
    ],
    [1.2, 2.8],
  );

  assert.deepEqual(rows, [
    { synthetic_id: "1", seed_id: "a", age: "young" },
    { synthetic_id: "2", seed_id: "b", age: "old" },
    { synthetic_id: "3", seed_id: "b", age: "old" },
    { synthetic_id: "4", seed_id: "b", age: "old" },
  ]);
});
